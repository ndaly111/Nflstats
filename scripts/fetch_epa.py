from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import pandas as pd

from .db_storage import DB_PATH, save_team_epa_snapshot, save_team_game_epa
from .epa_od_fetcher import (
    PbpFilters,
    apply_filters,
    compute_team_epa,
    compute_team_game_epa,
    load_pbp_pandas,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download nflverse play-by-play data (via nflreadpy) and write weekly "
            "per-team EPA/play snapshots into the SQLite cache."
        )
    )
    parser.add_argument("--season", type=int, required=True, help="Season year (e.g., 2025)")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="Path to SQLite cache")
    parser.add_argument("--week-start", type=int, default=None, dest="week_start")
    parser.add_argument("--week-end", type=int, default=None, dest="week_end")
    parser.add_argument("--min-wp", type=float, default=None, dest="min_wp")
    parser.add_argument("--max-wp", type=float, default=None, dest="max_wp")
    parser.add_argument("--include-playoffs", action="store_true", default=False, dest="include_playoffs")
    return parser.parse_args()


def _resolve_weeks(pbp: pd.DataFrame, start: Optional[int], end: Optional[int]) -> list[int]:
    available_weeks = pd.to_numeric(pbp.get("week"), errors="coerce").dropna().astype(int)
    if available_weeks.empty:
        raise SystemExit("Play-by-play data is missing week numbers; cannot build weekly snapshots.")

    latest = int(available_weeks.max())
    first = int(available_weeks.min())

    target_start = start or first
    target_end = end or latest

    if target_start < first:
        target_start = first
    if target_end > latest:
        target_end = latest

    if target_start > target_end:
        raise SystemExit(f"Requested week range {target_start}–{target_end} is invalid for this dataset.")

    return [w for w in sorted(set(available_weeks.tolist())) if target_start <= w <= target_end]


def main() -> None:
    args = parse_args()
    season = args.season
    filters = PbpFilters(
        week_start=None,
        week_end=None,
        min_wp=args.min_wp,
        max_wp=args.max_wp,
        include_playoffs=args.include_playoffs,
    )

    print(f"Fetching play-by-play data for {season} ...")
    pbp = load_pbp_pandas(season)

    weeks_to_build = _resolve_weeks(pbp, args.week_start, args.week_end)
    print(f"Building team EPA snapshots for weeks {weeks_to_build[0]}–{weeks_to_build[-1]} ...")

    for week_num in weeks_to_build:
        week_filters = PbpFilters(
            week_start=week_num,
            week_end=week_num,
            min_wp=filters.min_wp,
            max_wp=filters.max_wp,
            include_playoffs=filters.include_playoffs,
        )
        filtered_week = apply_filters(pbp, week_filters)
        weekly_epa = compute_team_epa(filtered_week)
        if weekly_epa.empty:
            raise SystemExit(f"Computed empty EPA snapshot for week {week_num}; cannot store in DB.")

        save_team_epa_snapshot(weekly_epa, season, week_num, db_path=args.db)
        team_games = compute_team_game_epa(filtered_week, week=week_num)
        if not team_games.empty:
            save_team_game_epa(team_games, season, week_num, db_path=args.db)
        print(f"Stored team EPA for week {week_num} in SQLite database: {args.db}")

    print("All requested weeks stored in SQLite cache ✅")


if __name__ == "__main__":
    main()
