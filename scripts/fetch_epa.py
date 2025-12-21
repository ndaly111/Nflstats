"""
Command-line script to download play-by-play data for a given NFL season,
filter it by week range, win probability and season type, and compute
per‑team offensive and defensive EPA statistics.

This module uses the helper functions from ``epa_od_fetcher`` to download
play‑by‑play data and compute team EPA values.  The resulting per‑team
statistics are saved into a CSV file under the ``data/`` directory as
``team_epa_<season>.csv``.  Subsequent plotting scripts can consume
this CSV to generate visualisations.

Usage (from the repository root):

    python -m scripts.fetch_epa --season 2025 --week-start 1 --week-end 6 \
        --min-wp 0.10 --max-wp 0.90 --include-playoffs

The optional arguments allow you to restrict the data to a particular
week range (inclusive) and win probability window, and to include
postseason plays if desired.
"""

import argparse
from pathlib import Path
from typing import Optional

import pandas as pd

try:
    # When executed as: python -m scripts.fetch_epa
    from .epa_od_fetcher import download_pbp, compute_team_epa
except ImportError:  # pragma: no cover
    try:
        # Fallback for different module layout
        from epa_od_fetcher import download_pbp, compute_team_epa
    except ImportError:  # pragma: no cover
        # Allow `python scripts/fetch_epa.py` when helpers live at repo root.
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from epa_od_fetcher import download_pbp, compute_team_epa


def parse_args() -> argparse.Namespace:
    """Define and parse command‑line arguments."""
    parser = argparse.ArgumentParser(
        description="Download NFL play‑by‑play data and compute team EPA stats.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--season",
        type=int,
        required=True,
        help="Season year to download (e.g. 2025)",
    )
    parser.add_argument(
        "--week-start",
        type=int,
        default=None,
        dest="week_start",
        help="Optional starting week to include (inclusive)",
    )
    parser.add_argument(
        "--week-end",
        type=int,
        default=None,
        dest="week_end",
        help="Optional ending week to include (inclusive)",
    )
    parser.add_argument(
        "--min-wp",
        type=float,
        default=None,
        dest="min_wp",
        help="Minimum win probability filter (0–1). Plays with win probability below this value are excluded.",
    )
    parser.add_argument(
        "--max-wp",
        type=float,
        default=None,
        dest="max_wp",
        help="Maximum win probability filter (0–1). Plays with win probability above this value are excluded.",
    )
    parser.add_argument(
        "--include-playoffs",
        action="store_true",
        default=False,
        dest="include_playoffs",
        help="Include postseason plays in addition to regular season plays.",
    )
    return parser.parse_args()


def filter_pbp(
    pbp: pd.DataFrame,
    week_start: Optional[int] = None,
    week_end: Optional[int] = None,
    min_wp: Optional[float] = None,
    max_wp: Optional[float] = None,
    include_playoffs: bool = False,
) -> pd.DataFrame:
    """
    Apply filters to the play‑by‑play dataframe.

    Parameters
    ----------
    pbp : pd.DataFrame
        Raw play‑by‑play data for a season.
    week_start : int, optional
        First week number to include (inclusive).
    week_end : int, optional
        Last week number to include (inclusive).
    min_wp : float, optional
        Minimum win probability (0–1). Plays with win probability below this
        value are dropped.
    max_wp : float, optional
        Maximum win probability (0–1). Plays with win probability above this
        value are dropped.
    include_playoffs : bool
        Whether to include postseason plays. If ``False``, only regular
        season plays are kept (i.e., rows where ``season_type`` == ``'REG'``).

    Returns
    -------
    pd.DataFrame
        Filtered play‑by‑play data.
    """
    df = pbp.copy()

    # Validate ranges early (fail fast)
    if week_start is not None and week_end is not None and week_start > week_end:
        raise ValueError(f"--week-start ({week_start}) cannot be greater than --week-end ({week_end})")
    if min_wp is not None and not (0.0 <= min_wp <= 1.0):
        raise ValueError(f"--min-wp must be between 0 and 1. Got {min_wp}")
    if max_wp is not None and not (0.0 <= max_wp <= 1.0):
        raise ValueError(f"--max-wp must be between 0 and 1. Got {max_wp}")
    if min_wp is not None and max_wp is not None and min_wp > max_wp:
        raise ValueError(f"--min-wp ({min_wp}) cannot be greater than --max-wp ({max_wp})")

    # Limit to regular season unless explicitly requested otherwise
    if not include_playoffs:
        if "season_type" in df.columns:
            df = df[df["season_type"].astype(str).str.upper() == "REG"]

    # Filter by week range if requested
    if week_start is not None or week_end is not None:
        if "week" not in df.columns:
            raise ValueError("Play-by-play data is missing 'week', required for --week-start/--week-end filtering")
        df["week"] = pd.to_numeric(df["week"], errors="coerce")
        if week_start is not None:
            df = df[df["week"] >= week_start]
        if week_end is not None:
            df = df[df["week"] <= week_end]

    # Filter by win probability range if available
    if min_wp is not None or max_wp is not None:
        if "wp" not in df.columns:
            raise ValueError("Play-by-play data is missing 'wp', required for --min-wp/--max-wp filtering")
        df["wp"] = pd.to_numeric(df["wp"], errors="coerce")
        if min_wp is not None:
            df = df[df["wp"] >= min_wp]
        if max_wp is not None:
            df = df[df["wp"] <= max_wp]

    return df


def _standardize_team_epa(team_epa: pd.DataFrame) -> pd.DataFrame:
    """
    Coerce compute_team_epa() output into a consistent schema:
        team, EPA_off_per_play, EPA_def_per_play
    """
    df = team_epa.copy()

    # If team isn't a column, assume it's the index and promote it.
    if "team" not in df.columns:
        df = df.reset_index()
        if "team" not in df.columns:
            df = df.rename(columns={df.columns[0]: "team"})

    # Normalize common column-name variants
    rename_map = {}
    if "off_epa_per_play" in df.columns and "EPA_off_per_play" not in df.columns:
        rename_map["off_epa_per_play"] = "EPA_off_per_play"
    if "def_epa_per_play" in df.columns and "EPA_def_per_play" not in df.columns:
        rename_map["def_epa_per_play"] = "EPA_def_per_play"
    if rename_map:
        df = df.rename(columns=rename_map)

    required = {"team", "EPA_off_per_play", "EPA_def_per_play"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            "compute_team_epa returned unexpected columns. Missing: "
            + ", ".join(sorted(missing))
            + ". Present columns: "
            + ", ".join(df.columns.astype(str))
        )

    df = df[["team", "EPA_off_per_play", "EPA_def_per_play"]].copy()
    df["team"] = df["team"].astype(str).str.strip().str.upper()
    df = df.sort_values("team").reset_index(drop=True)
    return df


def main() -> None:
    args = parse_args()
    season = args.season

    # Download play‑by‑play data for the season
    pbp = download_pbp(season)

    # Apply filters
    pbp = filter_pbp(
        pbp,
        week_start=args.week_start,
        week_end=args.week_end,
        min_wp=args.min_wp,
        max_wp=args.max_wp,
        include_playoffs=args.include_playoffs,
    )

    # Compute team EPA statistics
    team_epa = _standardize_team_epa(compute_team_epa(pbp))

    # Ensure output directory exists
    output_dir = Path("data")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"team_epa_{season}.csv"

    # Save to CSV
    team_epa.to_csv(output_path, index=False)
    print(f"Saved team EPA data to {output_path}")


if __name__ == "__main__":
    main()
