"""Download and summarize nflfastR EPA data for a season.

The script downloads the season play-by-play CSV if it is not already cached
locally, normalizes team abbreviations to align with logo filenames, and
produces per-team offensive and defensive EPA/play aggregates.
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


def ensure_epa_file(season: int, data_dir: Path, force: bool = False) -> Path:
    """Ensure the season EPA CSV is present locally."""

    data_dir.mkdir(parents=True, exist_ok=True)
    destination = data_dir / f"play_by_play_{season}.csv.gz"

    if destination.exists() and not force:
        return destination

    print(f"Downloading play-by-play data for {season} to {destination}...")
    return download_epa_csv(season, target_dir=data_dir)


def compute_team_epa(df: pd.DataFrame) -> pd.DataFrame:
    """Compute offensive and defensive EPA/play per team.

    Missing teams or EPA values are ignored to keep the aggregates robust.
    """

    working = df.copy()
    working["epa"] = pd.to_numeric(working.get("epa"), errors="coerce")
    working["offense_team"] = working.get("posteam").apply(normalize_team_abbr)
    working["defense_team"] = working.get("defteam").apply(normalize_team_abbr)

    valid_offense = working.dropna(subset=["epa", "offense_team"])
    valid_defense = working.dropna(subset=["epa", "defense_team"])

    offense = (
        valid_offense.groupby("offense_team")["epa"]
        .mean()
        .rename("off_epa_per_play")
        .reset_index()
    )
    defense = (
        valid_defense.groupby("defense_team")["epa"]
        .mean()
        .rename("def_epa_per_play")
        .reset_index()
    )

    merged = offense.merge(
        defense,
        how="outer",
        left_on="offense_team",
        right_on="defense_team",
    )
    merged["team"] = merged["offense_team"].combine_first(merged["defense_team"])

    summary = merged[["team", "off_epa_per_play", "def_epa_per_play"]]
    summary = summary.sort_values("team").reset_index(drop=True)
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    epa_path = ensure_epa_file(args.season, args.data_dir, force=args.force_download)
    print(f"Loading play-by-play data from {epa_path}...")

    df = pd.read_csv(epa_path, compression="gzip", low_memory=False)
    summary = compute_team_epa(df)

    output_path = args.output or args.data_dir / f"team_epa_{args.season}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_path, index=False)

    print(f"Saved team EPA summary to {output_path}")


if __name__ == "__main__":
    main()
