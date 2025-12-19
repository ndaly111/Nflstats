"""Run the full EPA refresh pipeline for a season.

This script downloads team logos, fetches nflfastR play-by-play data for the
specified season, computes offensive and defensive EPA/play aggregates, and
renders the offense vs defense scatter plot with team logos.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import matplotlib

# Use a non-interactive backend for CI/headless environments.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.download_logos import TEAM_ABBREVIATIONS, cache_all_logos
from scripts.fetch_epa import compute_team_epa, ensure_epa_file, filter_plays
from scripts.plot_epa_scatter import (
    add_reference_lines,
    build_titles,
    draw_logos,
    format_axes,
    save_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--season",
        type=int,
        default=2025,
        help="Season year to process (default: 2025)",
    )
    parser.add_argument(
        "--week-label",
        type=str,
        default=None,
        help="Optional week label for plot subtitle (e.g., 'Weeks 1-10')",
    )
    parser.add_argument(
        "--invert-defense-axis",
        action="store_true",
        help="Invert defensive EPA axis so better defenses trend upward",
    )
    return parser.parse_args()


def refresh_for_season(season: int, week_label: str | None, invert_defense_axis: bool) -> None:
    logos_dir = Path("assets") / "logos"
    data_dir = Path("data")
    plots_dir = Path("plots")

    print("Caching team logos...")
    cache_all_logos(TEAM_ABBREVIATIONS, logos_dir, canvas_size=256)

    print(f"Ensuring play-by-play data for {season} is available...")
    try:
        epa_path = ensure_epa_file(season, data_dir)
    except (FileNotFoundError, ConnectionError) as exc:
        print(f"Unable to download play-by-play data: {exc}")
        sys.exit(1)

    print(f"Loading {epa_path} and computing team aggregates...")
    df = pd.read_csv(epa_path, compression="gzip", low_memory=False)
    filtered = filter_plays(df)
    summary = compute_team_epa(filtered)

    summary_path = data_dir / f"team_epa_{season}.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_path, index=False)
    print(f"Saved team EPA summary to {summary_path}")

    print("Rendering scatter plot...")
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.scatter(summary["off_epa_per_play"], summary["def_epa_per_play"], alpha=0)
    draw_logos(ax, summary, logos_dir)
    format_axes(ax, invert_y=invert_defense_axis)
    add_reference_lines(ax, summary)
    build_titles(ax, season, week_label)
    plt.tight_layout()

    output_path = plots_dir / "epa_scatter.png"
    save_outputs(fig, output_path, save_svg=True, save_pdf=True)
    print(f"Saved plot to {output_path}")


if __name__ == "__main__":
    args = parse_args()
    refresh_for_season(
        season=args.season,
        week_label=args.week_label,
        invert_defense_axis=args.invert_defense_axis,
    )
