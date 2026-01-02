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


def main() -> None:
    seasons = load_seasons()
    latest_season = max(seasons)

    # Only need schedules for the current season to show future weeks (like Week 18).
    # Past seasons already render from epa.json’s per-game rows.
    target_seasons = [latest_season]
    season_set = set(target_seasons)
    schedule_df = load_schedule_rows(target_seasons)

    seasons_payload: Dict[str, Dict[str, List[Dict]]] = {}
    odds_entries: List[Dict] = []

    for season in target_seasons:
        seasons_payload[str(season)] = {"games": []}

    # Dedupe protection (some sources can duplicate rows)
    seen_ids_by_season: dict[int, set[str]] = defaultdict(set)

    for row in schedule_df.iter_rows(named=True):
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
                "source": "nflverse",
                "updated_at": now_iso(),
            }
        )

    # Fail fast if schedule is clearly incomplete (prevents committing “4 games only”)
    wk18_games = [g for g in seasons_payload.get(str(latest_season), {}).get("games", []) if g.get("week") == 18]
    if len(wk18_games) and len(wk18_games) < 16:
        sys.exit(
            f"Schedule looks incomplete for {latest_season} week 18: got {len(wk18_games)} games. "
            "Refusing to write schedule.json/odds.json."
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
