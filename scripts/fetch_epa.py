from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import pandas as pd

from .epa_od_fetcher import PbpFilters, build_team_epa


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download nflverse play-by-play data (via nflreadpy) and compute per-team EPA/play."
    )
    parser.add_argument("--season", type=int, required=True, help="Season year (e.g., 2025)")
    parser.add_argument("--week-start", type=int, default=None, dest="week_start")
    parser.add_argument("--week-end", type=int, default=None, dest="week_end")
    parser.add_argument("--min-wp", type=float, default=None, dest="min_wp")
    parser.add_argument("--max-wp", type=float, default=None, dest="max_wp")
    parser.add_argument("--include-playoffs", action="store_true", default=False, dest="include_playoffs")
    parser.add_argument("--output", type=str, default=None)
    return parser.parse_args()


def _resolve_output_path(season: int, output_arg: Optional[str]) -> Path:
    repo_root = Path(__file__).resolve().parents[1]

    if output_arg:
        out = Path(output_arg)
        if not out.is_absolute():
            out = repo_root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        return out

    data_dir = repo_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / f"team_epa_{season}.csv"


def main() -> None:
    args = parse_args()

    filters = PbpFilters(
        week_start=args.week_start,
        week_end=args.week_end,
        min_wp=args.min_wp,
        max_wp=args.max_wp,
        include_playoffs=args.include_playoffs,
    )

    df: pd.DataFrame = build_team_epa(args.season, filters)

    required = {"team", "EPA_off_per_play", "EPA_def_per_play"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Computed team EPA missing columns: {sorted(missing)}")

    out_path = _resolve_output_path(args.season, args.output)
    df.to_csv(out_path, index=False)
    print(f"Saved team EPA CSV: {out_path}")


if __name__ == "__main__":
    main()
