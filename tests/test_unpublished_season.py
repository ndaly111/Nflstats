"""Tests for the "nflverse hasn't published this season yet" handling.

The nightly refresh died on 2026-09-01 because this repo rolled the season over
on September 1 while nflverse rolls over on the Thursday after Labor Day, so it
spent nine days asking for a season upstream refused to serve. These tests pin
both halves of the fix: the shared season rule, and the skip path that covers
the shorter gap between kickoff and the first published play-by-play file.

nflreadpy is only needed at download time, so a stub module is enough to import
the fetcher when the real dependency is absent.
"""
import sys
import types
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

sys.modules.setdefault("nflreadpy", types.ModuleType("nflreadpy"))

from scripts import epa_od_fetcher, fetch_epa  # noqa: E402
from scripts.db_storage import init_db  # noqa: E402
from scripts.epa_od_fetcher import (  # noqa: E402
    SeasonNotPublishedError,
    _looks_unpublished,
    load_pbp_pandas,
)
from scripts.season import current_nfl_season, season_opener  # noqa: E402

# load_pbp_pandas checks for required columns before it checks emptiness, so an
# "empty season" frame still has to carry the schema.
EMPTY_PBP = pd.DataFrame(columns=["epa", "posteam", "defteam", "week"])


class _FakePolarsFrame:
    def __init__(self, df):
        self._df = df

    def to_pandas(self):
        return self._df


def _stub_download(monkeypatch, df=None, exc=None):
    """Replace nflreadpy.load_pbp with a canned response; returns the call log."""
    calls = []

    def _load(seasons):
        calls.append(seasons)
        if exc is not None:
            raise exc
        return _FakePolarsFrame(df)

    monkeypatch.setattr(epa_od_fetcher.nfl, "load_pbp", _load, raising=False)
    return calls


# --- the season rule -------------------------------------------------------

@pytest.mark.parametrize(
    "year,expected",
    [(2025, date(2025, 9, 4)), (2026, date(2026, 9, 10)), (2027, date(2027, 9, 9))],
)
def test_season_opener_is_the_thursday_after_labor_day(year, expected):
    assert season_opener(year) == expected
    assert expected.weekday() == 3  # Thursday


@pytest.mark.parametrize(
    "today,expected",
    [
        (date(2026, 9, 4), 2025),   # the nine-day gap that broke the pipeline
        (date(2026, 9, 9), 2025),   # day before kickoff
        (date(2026, 9, 10), 2026),  # kickoff
        (date(2027, 1, 15), 2026),  # deep into the playoffs
        (datetime(2026, 9, 10, tzinfo=timezone.utc), 2026),
    ],
)
def test_current_nfl_season_tracks_kickoff_not_the_calendar(today, expected):
    assert current_nfl_season(today) == expected


def test_our_season_rule_agrees_with_nflreadpy():
    """Guards against drift; skipped when nflreadpy isn't installed."""
    nfl = pytest.importorskip("nflreadpy")
    if not hasattr(nfl, "get_current_season"):
        pytest.skip("installed nflreadpy has no get_current_season()")
    assert current_nfl_season() == nfl.get_current_season()


# --- classifying the download failure --------------------------------------

def test_future_season_is_rejected_before_any_download(monkeypatch):
    calls = _stub_download(monkeypatch, df=EMPTY_PBP)
    with pytest.raises(SeasonNotPublishedError):
        load_pbp_pandas(current_nfl_season() + 1)
    assert calls == []


def test_looks_unpublished_distinguishes_missing_data_from_flaky_networks():
    assert _looks_unpublished(RuntimeError("HTTP 404 while fetching release asset"))
    assert _looks_unpublished(FileNotFoundError("No such file or directory"))
    assert _looks_unpublished(ValueError("Season must be between 1999 and 2025"))
    assert not _looks_unpublished(RuntimeError("Connection reset by peer"))


def test_empty_frame_for_current_season_is_not_published(monkeypatch):
    _stub_download(monkeypatch, df=EMPTY_PBP)
    with pytest.raises(SeasonNotPublishedError):
        load_pbp_pandas(current_nfl_season())


def test_empty_frame_for_a_past_season_stays_a_hard_error(monkeypatch):
    _stub_download(monkeypatch, df=EMPTY_PBP)
    with pytest.raises(RuntimeError) as excinfo:
        load_pbp_pandas(2015)
    assert not isinstance(excinfo.value, SeasonNotPublishedError)


def test_missing_file_does_not_burn_retries(monkeypatch):
    calls = _stub_download(monkeypatch, exc=RuntimeError("404 Client Error: Not Found"))
    with pytest.raises(SeasonNotPublishedError):
        load_pbp_pandas(current_nfl_season())
    assert len(calls) == 1


def test_transient_error_still_retries_and_stays_a_hard_error(monkeypatch):
    calls = _stub_download(monkeypatch, exc=RuntimeError("Connection reset by peer"))
    monkeypatch.setattr(epa_od_fetcher.time, "sleep", lambda _seconds: None)
    with pytest.raises(RuntimeError) as excinfo:
        load_pbp_pandas(current_nfl_season())
    assert not isinstance(excinfo.value, SeasonNotPublishedError)
    assert len(calls) == 3


# --- the fetch_epa skip path -----------------------------------------------

def _arrange_fetch(monkeypatch, tmp_path, season, extra_argv=()):
    db = tmp_path / "epa.sqlite"
    monkeypatch.setattr(
        sys, "argv", ["fetch_epa", "--season", str(season), "--db", str(db), *extra_argv]
    )

    def _unpublished(_season):
        raise SeasonNotPublishedError(f"nflverse has no play-by-play file for {_season} yet")

    monkeypatch.setattr(fetch_epa, "load_pbp_pandas", _unpublished)
    return db


def _seed_week(db, season, week):
    conn = init_db(db)
    conn.execute(
        """
        INSERT INTO team_epa_weekly
            (season, week, team, off_epa_sum, off_plays, def_epa_sum, def_plays,
             EPA_off_per_play, EPA_def_per_play)
        VALUES (?, ?, 'ARI', 1.0, 10, -1.0, 10, 0.1, -0.1)
        """,
        (season, week),
    )
    conn.commit()
    conn.close()


def test_skip_flag_exits_cleanly_when_nothing_is_cached(monkeypatch, tmp_path, capsys):
    _arrange_fetch(monkeypatch, tmp_path, 2026, ["--skip-if-unpublished"])
    fetch_epa.main()
    assert "[skip]" in capsys.readouterr().out


def test_without_the_flag_an_unpublished_season_still_fails(monkeypatch, tmp_path):
    _arrange_fetch(monkeypatch, tmp_path, 2026)
    with pytest.raises(SeasonNotPublishedError):
        fetch_epa.main()


def test_skip_flag_refuses_to_mask_a_regression(monkeypatch, tmp_path):
    """Once a season has cached weeks, vanished data is a bug, not a preseason gap."""
    db = _arrange_fetch(monkeypatch, tmp_path, 2026, ["--skip-if-unpublished"])
    _seed_week(db, 2026, 1)
    with pytest.raises(SystemExit) as excinfo:
        fetch_epa.main()
    assert "regression" in str(excinfo.value)
