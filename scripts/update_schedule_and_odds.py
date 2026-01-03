"""
Usage:
  python scripts/update_schedule_and_odds.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Dict, List, Optional

import polars as pl
from nflreadpy import load_schedules

# Static division mapping used for offline schedule reconstruction
DIVISIONS: dict[str, list[str]] = {
    "AFC East": ["BUF", "MIA", "NE", "NYJ"],
    "AFC North": ["BAL", "CIN", "CLE", "PIT"],
    "AFC South": ["HOU", "IND", "JAX", "TEN"],
    "AFC West": ["DEN", "KC", "LAC", "LV"],
    "NFC East": ["DAL", "NYG", "PHI", "WAS"],
    "NFC North": ["CHI", "DET", "GB", "MIN"],
    "NFC South": ["ATL", "CAR", "NO", "TB"],
    "NFC West": ["ARI", "LA", "SEA", "SF"],
}

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
EPA_PATH = DATA_DIR / "epa.json"
SCHEDULE_PATH = DATA_DIR / "schedule.json"
ODDS_PATH = DATA_DIR / "odds.json"
SOURCE_LABEL = "nflverse-data schedules/games via nflreadpy"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_seasons() -> List[int]:
    try:
        with EPA_PATH.open() as f:
            payload = json.load(f)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"Failed to read {EPA_PATH}: {exc}")

    seasons: List[int] = []
    for season_key in (payload.get("seasons") or {}):
        try:
            seasons.append(int(season_key))
        except (TypeError, ValueError):
            continue
    if not seasons:
        sys.exit("No seasons found in data/epa.json")
    return sorted(set(seasons))


def to_number(value) -> Optional[float]:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(num):
        return None
    return num


def normalize_team(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text or None


def parse_home_away_from_game_id(game_id: str) -> tuple[Optional[str], Optional[str]]:
    parts = str(game_id).split("_")
    if len(parts) != 4:
        return None, None
    # nflverse game_ids look like 2025_01_AWAY_HOME
    _, _, away, home = parts
    return normalize_team(home), normalize_team(away)


def build_game_id(row: Dict, week_token: str, home: str, away: str) -> Optional[str]:
    if row.get("game_id"):
        return str(row["game_id"])
    if not week_token or home is None or away is None:
        return None
    return f"{row.get('season')}_{week_token}_{away}_{home}"


def parse_week(value) -> Optional[tuple[object, str]]:
    """
    Returns (week_out, week_token)
      - week_out: int for regular season weeks, or str like 'WC'/'DIV'/'CONF'/'SB'
      - week_token: '01'..'18' for regular season, or 'WC'/'DIV'/'CONF'/'SB' for playoffs
    """
    num = to_number(value)
    if num is not None:
        wk = int(num)
        if wk <= 0:
            return None
        return wk, str(wk).zfill(2)

    if value is None:
        return None
    raw = str(value).strip().upper()
    if not raw:
        return None

    # Canonicalize common playoff tokens
    if raw in {"WC", "WILDCARD", "WILD CARD"}:
        return "WC", "WC"
    if raw in {"DIV", "DIVISIONAL"}:
        return "DIV", "DIV"
    if raw in {"CONF", "CONFERENCE", "CHAMP", "CONFERENCE CHAMPIONSHIP"}:
        return "CONF", "CONF"
    if raw in {"SB", "SUPER BOWL", "SUPERBOWL"}:
        return "SB", "SB"
    return None


def load_schedule_rows(seasons: List[int]) -> pl.DataFrame:
    # Load per-season to avoid “partial” results when requesting many seasons at once.
    frames: list[pl.DataFrame] = []
    for season in seasons:
        try:
            df = load_schedules(seasons=[season])
        except Exception as exc:  # noqa: BLE001
            sys.exit(f"Failed to load schedules for {season} from nflreadpy: {exc}")

        if not isinstance(df, pl.DataFrame):
            try:
                df = pl.DataFrame(df)
            except Exception as exc:  # noqa: BLE001
                sys.exit(f"Could not convert schedules({season}) to polars DataFrame: {exc}")
        frames.append(df)

    if not frames:
        return pl.DataFrame()
    return pl.concat(frames, how="vertical_relaxed")


def build_schedule_from_epa(latest_season: int, final_week: int) -> pl.DataFrame:
    """Offline fallback that reconstructs schedule rows from data/epa.json.

    This walks the per-team EPA entries to extract unique game_ids for the
    latest season, infers home/away from the id format, and synthesizes Week 18
    divisional rematches when the second head-to-head meeting is missing.
    """

    try:
        with EPA_PATH.open() as f:
            epa_payload = json.load(f)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"Failed to read {EPA_PATH} while building offline schedule: {exc}")

    games = epa_payload.get("seasons", {}).get(str(latest_season), {}).get("games", [])
    if not games:
        sys.exit(f"No EPA games found for {latest_season}; cannot synthesize schedule.json")

    unique_games: dict[str, dict] = {}
    for row in games:
        game_id = str(row.get("game_id") or "").strip()
        if not game_id or game_id in unique_games:
            continue
        unique_games[game_id] = row

    rows: list[dict] = []
    division_map = {team: name for name, teams in DIVISIONS.items() for team in teams}
    divisional_counts: dict[tuple[str, str], int] = defaultdict(int)
    divisional_first_host: dict[tuple[str, str], str] = {}

    for game_id, row in unique_games.items():
        home_team, away_team = parse_home_away_from_game_id(game_id)
        if not home_team or not away_team:
            continue

        week_val = row.get("week")
        try:
            week_num = int(week_val)
        except (TypeError, ValueError):
            continue

        rows.append(
            {
                "season": latest_season,
                "week": week_num,
                "home_team": home_team,
                "away_team": away_team,
            }
        )

        if division_map.get(home_team) == division_map.get(away_team):
            key = tuple(sorted([home_team, away_team]))
            divisional_counts[key] += 1
            divisional_first_host.setdefault(key, home_team)

    # Add missing divisional rematches into the final regular-season week with flipped home/away
    for division, teams in DIVISIONS.items():
        for idx, team_a in enumerate(teams):
            for team_b in teams[idx + 1 :]:
                key = tuple(sorted([team_a, team_b]))
                if divisional_counts.get(key, 0) >= 2:
                    continue
                first_home = divisional_first_host.get(key)
                if not first_home:
                    continue
                if first_home == team_a:
                    home_team, away_team = team_b, team_a
                else:
                    home_team, away_team = team_a, team_b

                rows.append(
                    {
                        "season": latest_season,
                        "week": final_week,
                        "home_team": home_team,
                        "away_team": away_team,
                    }
                )

    return pl.DataFrame(rows)


def main() -> None:
    seasons = load_seasons()
    latest_season = max(seasons)
    final_week = 18 if latest_season >= 2021 else 17

    # Only need schedules for the current season to show future weeks (like Week 18).
    # Past seasons already render from epa.json’s per-game rows.
    target_seasons = [latest_season]
    season_set = set(target_seasons)
    try:
        schedule_df = load_schedule_rows(target_seasons)
    except SystemExit as exc:
        print(f"nflreadpy failed, reconstructing schedule from EPA data: {exc}", file=sys.stderr)
        schedule_df = build_schedule_from_epa(latest_season, final_week)

    seasons_payload: Dict[str, Dict[str, List[Dict]]] = {}
    odds_entries: List[Dict] = []

    for season in target_seasons:
        seasons_payload[str(season)] = {"games": []}

    # Dedupe protection (some sources can duplicate rows)
    seen_ids_by_season: dict[int, set[str]] = defaultdict(set)

    def add_schedule_rows(df: pl.DataFrame, source_label: str) -> int:
        added = 0
        for row in df.iter_rows(named=True):
            season_val = row.get("season")
            try:
                season_num = int(season_val)
            except (TypeError, ValueError):
                continue
            if season_num not in season_set:
                continue

            parsed = parse_week(row.get("week"))
            if parsed is None:
                continue
            week_out, week_token = parsed

            home_team = normalize_team(row.get("home_team") or row.get("home"))
            away_team = normalize_team(row.get("away_team") or row.get("away"))
            if not home_team or not away_team:
                continue

            game_id = build_game_id(row, week_token, home_team, away_team)
            if not game_id:
                continue

            if game_id in seen_ids_by_season[season_num]:
                continue
            seen_ids_by_season[season_num].add(game_id)

            seasons_payload[str(season_num)]["games"].append(
                {
                    "game_id": game_id,
                    "week": week_out,
                    "home": home_team,
                    "away": away_team,
                    # Preserve helpful context if present (matchups.html can use it)
                    "season_type": (str(row.get("season_type") or "").strip().upper() or None),
                    "game_type": (str(row.get("game_type") or "").strip().upper() or None),
                }
            )
            added += 1

            spread_val = to_number(row.get("spread_line"))
            total_val = to_number(row.get("total_line"))
            if spread_val is None and total_val is None:
                continue
            odds_entries.append(
                {
                    "season": season_num,
                    "week": week_out,
                    "game_id": game_id,
                    "spread": spread_val if spread_val is not None else None,
                    "total": total_val if total_val is not None else None,
                    "source": source_label,
                    "updated_at": now_iso(),
                }
            )
        return added

    add_schedule_rows(schedule_df, "nflverse")

    def count_final_week_games() -> int:
        games = seasons_payload.get(str(latest_season), {}).get("games", [])
        return sum(1 for g in games if g.get("week") == final_week)

    final_week_count = count_final_week_games()
    if final_week_count < 16:
        print(
            f"Schedule for {latest_season} week {final_week} has {final_week_count} games; attempting EPA fallback",
            file=sys.stderr,
        )
        fallback_df = build_schedule_from_epa(latest_season, final_week)
        add_schedule_rows(fallback_df, "epa-fallback")
        final_week_count = count_final_week_games()

    if final_week_count != 16:
        sys.exit(
            f"Schedule incomplete for {latest_season} week {final_week}: got {final_week_count} games after fallback"
        )

    schedule_payload = {
        "generated_at": now_iso(),
        "source": SOURCE_LABEL,
        "seasons": seasons_payload,
    }

    odds_payload = {
        "generated_at": now_iso(),
        "source": SOURCE_LABEL,
        "odds": odds_entries,
    }

    preserve_existing_odds = False
    existing_odds_text = None
    if not odds_entries and ODDS_PATH.exists():
        try:
            existing_odds_text = ODDS_PATH.read_text()
            preserve_existing_odds = True
            print("No new odds found; preserving existing odds.json")
        except Exception:  # noqa: BLE001
            preserve_existing_odds = False

    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SCHEDULE_PATH.write_text(json.dumps(schedule_payload, indent=2) + "\n")
        if preserve_existing_odds and existing_odds_text is not None:
            ODDS_PATH.write_text(existing_odds_text)
        else:
            ODDS_PATH.write_text(json.dumps(odds_payload, indent=2) + "\n")
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"Failed to write output files: {exc}")

    print(f"{latest_season} week {final_week} games: {final_week_count}")
    print(f"Wrote {SCHEDULE_PATH} and {ODDS_PATH}")


if __name__ == "__main__":
    main()
