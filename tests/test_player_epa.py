"""Tests for per-player EPA aggregation.

Roles are named for what the player did on the play (passing / rushing /
receiving), not for a position, because play-by-play tells us the action and
never the depth chart. A quarterback's designed runs land in rushing, which is
correct: that is what he did.
"""
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

sys.modules.setdefault("nflreadpy", types.ModuleType("nflreadpy"))

from scripts.player_epa import compute_player_epa  # noqa: E402

BASE = {
    "epa": 0.0,
    "posteam": "BUF",
    "play_type": "pass",
    "passer_player_id": None,
    "passer_player_name": None,
    "rusher_player_id": None,
    "rusher_player_name": None,
    "receiver_player_id": None,
    "receiver_player_name": None,
    "qb_scramble": 0,
    "qb_kneel": 0,
    "qb_spike": 0,
    "sack": 0,
}


def frame(*rows):
    return pd.DataFrame([{**BASE, **r} for r in rows])


def lookup(result, player_id, role):
    hit = result[(result.player_id == player_id) & (result.role == role)]
    assert len(hit) <= 1, f"duplicate rows for {player_id}/{role}"
    return hit.iloc[0] if len(hit) else None


def test_completed_pass_credits_passer_and_receiver():
    out = compute_player_epa(frame({
        "epa": 1.5, "passer_player_id": "QB1", "passer_player_name": "J.Allen",
        "receiver_player_id": "WR1", "receiver_player_name": "K.Coleman",
    }), week=3)
    assert lookup(out, "QB1", "passing").epa_sum == pytest.approx(1.5)
    assert lookup(out, "WR1", "receiving").epa_sum == pytest.approx(1.5)
    assert lookup(out, "QB1", "rushing") is None


def test_sack_counts_as_a_dropback_against_the_passer():
    out = compute_player_epa(frame({
        "epa": -2.0, "sack": 1,
        "passer_player_id": "QB1", "passer_player_name": "J.Allen",
    }), week=1)
    row = lookup(out, "QB1", "passing")
    assert row.epa_sum == pytest.approx(-2.0)
    assert row.plays == 1


def test_scramble_credits_the_quarterback_as_a_dropback_not_a_rush():
    """Scrambles carry the QB in the rusher columns and leave passer blank."""
    out = compute_player_epa(frame({
        "epa": 0.8, "play_type": "run", "qb_scramble": 1,
        "rusher_player_id": "QB1", "rusher_player_name": "J.Allen",
    }), week=1)
    assert lookup(out, "QB1", "passing").epa_sum == pytest.approx(0.8)
    assert lookup(out, "QB1", "rushing") is None


def test_designed_run_credits_the_rusher():
    out = compute_player_epa(frame({
        "epa": 0.4, "play_type": "run",
        "rusher_player_id": "RB1", "rusher_player_name": "J.Cook",
    }), week=1)
    assert lookup(out, "RB1", "rushing").epa_sum == pytest.approx(0.4)


def test_incompletion_still_counts_as_a_target():
    out = compute_player_epa(frame({
        "epa": -0.6,
        "passer_player_id": "QB1", "passer_player_name": "J.Allen",
        "receiver_player_id": "WR1", "receiver_player_name": "K.Coleman",
    }), week=1)
    assert lookup(out, "WR1", "receiving").plays == 1


def test_throwaway_charges_the_passer_but_creates_no_receiving_row():
    out = compute_player_epa(frame({
        "epa": -0.5, "passer_player_id": "QB1", "passer_player_name": "J.Allen",
    }), week=1)
    assert lookup(out, "QB1", "passing").plays == 1
    assert out[out.role == "receiving"].empty


def test_kneels_and_spikes_are_excluded():
    out = compute_player_epa(frame(
        {"epa": -1.0, "play_type": "run", "qb_kneel": 1,
         "rusher_player_id": "QB1", "rusher_player_name": "J.Allen"},
        {"epa": -0.9, "qb_spike": 1,
         "passer_player_id": "QB1", "passer_player_name": "J.Allen"},
    ), week=1)
    assert out.empty


def test_penalty_no_plays_are_ignored():
    out = compute_player_epa(frame({
        "epa": 0.3, "play_type": "no_play", "qb_scramble": 1,
        "rusher_player_id": "QB1", "rusher_player_name": "J.Allen",
    }), week=1)
    assert out.empty


def test_repeated_plays_aggregate_into_one_row_per_player_and_role():
    out = compute_player_epa(frame(
        {"epa": 1.0, "passer_player_id": "QB1", "passer_player_name": "J.Allen",
         "receiver_player_id": "WR1", "receiver_player_name": "K.Coleman"},
        {"epa": -0.25, "passer_player_id": "QB1", "passer_player_name": "J.Allen",
         "receiver_player_id": "WR1", "receiver_player_name": "K.Coleman"},
        {"epa": 0.5, "play_type": "run",
         "rusher_player_id": "RB1", "rusher_player_name": "J.Cook"},
    ), week=7)
    qb = lookup(out, "QB1", "passing")
    assert qb.plays == 2 and qb.epa_sum == pytest.approx(0.75)
    assert lookup(out, "WR1", "receiving").plays == 2
    assert lookup(out, "RB1", "rushing").plays == 1
    assert set(out.week) == {7}


def test_players_are_split_by_team_not_merged_across_them():
    out = compute_player_epa(frame(
        {"epa": 1.0, "posteam": "BUF", "passer_player_id": "QB1", "passer_player_name": "J.Allen"},
        {"epa": 2.0, "posteam": "MIA", "passer_player_id": "QB2", "passer_player_name": "T.Tagovailoa"},
    ), week=1)
    assert set(out.team) == {"BUF", "MIA"}


def test_plays_without_epa_are_dropped():
    out = compute_player_epa(frame({
        "epa": None, "passer_player_id": "QB1", "passer_player_name": "J.Allen",
    }), week=1)
    assert out.empty
