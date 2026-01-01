"""
Usage:
  python scripts/update_schedule_and_odds.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Dict, List, Optional

import polars as pl
from nflreadpy import load_schedules

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


def build_game_id(row: Dict, week: int, home: str, away: str) -> Optional[str]:
    if row.get("game_id"):
        return str(row["game_id"])
    if week is None or home is None or away is None:
        return None
    return f"{row.get('season')}_{str(week).zfill(2)}_{away}_{home}"


def load_schedule_rows(seasons: List[int]) -> pl.DataFrame:
    try:
        df = load_schedules(seasons=seasons)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"Failed to load schedules from nflreadpy: {exc}")

    if not isinstance(df, pl.DataFrame):
        try:
            df = pl.DataFrame(df)
        except Exception as exc:  # noqa: BLE001
            sys.exit(f"Could not convert schedules to polars DataFrame: {exc}")
    return df


def main() -> None:
    seasons = load_seasons()
    season_set = set(seasons)
    schedule_df = load_schedule_rows(seasons)

    seasons_payload: Dict[str, Dict[str, List[Dict]]] = {}
    odds_entries: List[Dict] = []

    for season in seasons:
        seasons_payload[str(season)] = {"games": []}

    for row in schedule_df.iter_rows(named=True):
        season_val = row.get("season")
        try:
            season_num = int(season_val)
        except (TypeError, ValueError):
            continue
        if season_num not in season_set:
            continue

        week_num = to_number(row.get("week"))
        week_int = int(week_num) if week_num is not None else None
        if week_int is None:
            continue

        home_team = normalize_team(row.get("home_team"))
        away_team = normalize_team(row.get("away_team"))
        if not home_team or not away_team:
            continue

        game_id = build_game_id(row, week_int, home_team, away_team)
        if not game_id:
            continue

        seasons_payload[str(season_num)]["games"].append(
            {"game_id": game_id, "week": week_int, "home": home_team, "away": away_team}
        )

        spread_val = to_number(row.get("spread_line"))
        total_val = to_number(row.get("total_line"))
        if spread_val is None and total_val is None:
            continue
        odds_entries.append(
            {
                "season": season_num,
                "week": week_int,
                "game_id": game_id,
                "spread": spread_val if spread_val is not None else None,
                "total": total_val if total_val is not None else None,
                "source": "nflverse",
                "updated_at": now_iso(),
            }
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

    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SCHEDULE_PATH.write_text(json.dumps(schedule_payload, indent=2) + "\n")
        ODDS_PATH.write_text(json.dumps(odds_payload, indent=2) + "\n")
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"Failed to write output files: {exc}")

    print(f"Wrote {SCHEDULE_PATH} and {ODDS_PATH}")


if __name__ == "__main__":
    main()
