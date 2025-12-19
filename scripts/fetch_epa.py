"""Download and summarize nflfastR EPA data for a season.

The script downloads the season play-by-play CSV if it is not already cached
locally, normalizes team abbreviations to align with logo filenames, and
produces per-team offensive and defensive EPA/play aggregates. Optional flags
restrict plays by week, win probability, and season type to mirror common
analytics charts.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sources import download_epa_csv

# Mapping of alternate or historical team abbreviations to current canon values
# used by logo filenames.
TEAM_ABBREVIATION_ALIASES = {
    "ARZ": "ARI",
    "BLT": "BAL",
    "CLV": "CLE",
    "GNB": "GB",
    "HST": "HOU",
    "JAC": "JAX",
    "KCC": "KC",
    "LAC": "LAC",
    "LAR": "LAR",
    "LA": "LAR",
    "OAK": "LV",
    "SD": "LAC",
    "SDG": "LAC",
    "STL": "LAR",
    "TAM": "TB",
    "WAS": "WAS",
    "WSH": "WAS",
    "WFT": "WAS",
}


def normalize_team_abbr(raw_abbr: Optional[str]) -> Optional[str]:
    """Normalize team abbreviations to match logo filenames.

    Args:
        raw_abbr: Team abbreviation from the dataset.

    Returns:
        Canonical three-letter abbreviation in uppercase, or ``None`` when the
        input is missing.
    """

    if raw_abbr is None:
        return None

    trimmed = str(raw_abbr).strip().upper()
    if not trimmed:
        return None

    return TEAM_ABBREVIATION_ALIASES.get(trimmed, trimmed)


FALLBACK_EPA_SAMPLE = REPO_ROOT / "data" / "play_by_play_sample.csv"


def ensure_epa_file(
    season: int, data_dir: Path, force: bool = False, fallback_sample: Optional[Path] = None
) -> Path:
    """Ensure the season EPA CSV is present locally."""

    data_dir.mkdir(parents=True, exist_ok=True)
    destination = data_dir / f"play_by_play_{season}.csv.gz"

    if destination.exists() and not force:
        return destination

    print(f"Downloading play-by-play data for {season} to {destination}...")
    return download_epa_csv(season, target_dir=data_dir, fallback_sample=fallback_sample)


def filter_plays(
    df: pd.DataFrame,
    *,
    week_start: Optional[int] = None,
    week_end: Optional[int] = None,
    min_wp: Optional[float] = None,
    max_wp: Optional[float] = None,
    include_playoffs: bool = False,
) -> pd.DataFrame:
    """Apply optional filters before aggregating EPA."""

    working = df.copy()

    if not include_playoffs and "season_type" in working.columns:
        working = working[working["season_type"].astype(str).str.upper() == "REG"]

    if week_start is not None or week_end is not None:
        if "week" not in working.columns:
            raise ValueError("Input data is missing the 'week' column required for week filtering")
        working["week"] = pd.to_numeric(working.get("week"), errors="coerce")
        start = week_start if week_start is not None else working["week"].min()
        end = week_end if week_end is not None else working["week"].max()
        working = working[working["week"].between(start, end, inclusive="both")]

    if min_wp is not None or max_wp is not None:
        if "wp" not in working.columns:
            raise ValueError("Input data is missing the 'wp' column required for win-probability filtering")
        working["wp"] = pd.to_numeric(working.get("wp"), errors="coerce")
        if min_wp is not None:
            working = working[working["wp"] >= min_wp]
        if max_wp is not None:
            working = working[working["wp"] <= max_wp]

    return working


def compute_team_epa(df: pd.DataFrame) -> pd.DataFrame:
    """Compute offensive and defensive EPA/play per team.

    Missing teams or EPA values are ignored to keep the aggregates robust.
    """

    working = df.copy()
    working["epa"] = pd.to_numeric(working.get("epa"), errors="coerce")
    working["team_offense"] = working.get("posteam").apply(normalize_team_abbr)
    working["team_defense"] = working.get("defteam").apply(normalize_team_abbr)

    melted = pd.concat(
        [
            working.rename(columns={"team_offense": "team"})[["team", "epa"]].assign(metric="off_epa_per_play"),
            working.rename(columns={"team_defense": "team"})[["team", "epa"]].assign(metric="def_epa_per_play"),
        ]
    )

    summary = (
        melted.dropna(subset=["team", "epa"])
        .groupby(["team", "metric"])["epa"]
        .mean()
        .unstack()
        .reset_index()
        .sort_values("team")
        .reset_index(drop=True)
    )
    summary = summary.rename_axis(None, axis=1)
    summary = summary.reindex(columns=["team", "off_epa_per_play", "def_epa_per_play"])
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, required=True, help="Season year to download (e.g., 2023)")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Directory to cache raw play-by-play downloads.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output CSV path for team EPA aggregates.",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Re-download the play-by-play file even if a cached copy exists.",
    )
    parser.add_argument(
        "--week-start",
        type=int,
        default=None,
        help="First week to include (regular season numbering)",
    )
    parser.add_argument(
        "--week-end",
        type=int,
        default=None,
        help="Last week to include (regular season numbering)",
    )
    parser.add_argument(
        "--min-wp",
        type=float,
        default=None,
        help="Minimum in-play win probability to include (0-1). Useful for dropping blowouts.",
    )
    parser.add_argument(
        "--max-wp",
        type=float,
        default=None,
        help="Maximum in-play win probability to include (0-1). Useful for dropping blowouts.",
    )
    parser.add_argument(
        "--include-playoffs",
        action="store_true",
        help="Include postseason plays when filtering by week.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        epa_path = ensure_epa_file(
            args.season, args.data_dir, force=args.force_download, fallback_sample=FALLBACK_EPA_SAMPLE
        )
    except (FileNotFoundError, ConnectionError) as exc:
        print(f"Unable to download play-by-play data: {exc}")
        sys.exit(1)

    print(f"Loading play-by-play data from {epa_path}...")

    df = pd.read_csv(epa_path, compression="infer", low_memory=False)
    df = filter_plays(
        df,
        week_start=args.week_start,
        week_end=args.week_end,
        min_wp=args.min_wp,
        max_wp=args.max_wp,
        include_playoffs=args.include_playoffs,
    )
    summary = compute_team_epa(df)

    output_path = args.output or args.data_dir / f"team_epa_{args.season}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_path, index=False)

    print(f"Saved team EPA summary to {output_path}")


if __name__ == "__main__":
    main()
