"""Generate an offensive vs defensive EPA/play scatter plot with team logos.

This script expects a CSV containing per-team offensive and defensive EPA/play
aggregates (as produced by ``scripts/fetch_epa.py``) and caches of 256x256 logo
PNGs under ``assets/logos``. Logos are placed at each team's coordinates and
reference lines are drawn at league averages.
"""
from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.offsetbox import AnnotationBbox, OffsetImage

try:
    from PIL import Image  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    Image = None  # type: ignore

from scripts.download_logos import placeholder_logo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--season",
        type=int,
        required=True,
        help="Season year matching the aggregated EPA file (e.g., 2023)",
    )
    parser.add_argument(
        "--week",
        type=str,
        default=None,
        help="Optional week or week range label to show in the subtitle (e.g., 'Week 10', 'Weeks 1-4')",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Path to aggregated EPA CSV. Defaults to data/team_epa_<season>.csv",
    )
    parser.add_argument(
        "--logos-dir",
        type=Path,
        default=Path("assets") / "logos",
        help="Directory containing 256x256 team logo PNGs named <TEAM>.png",
    )
    parser.add_argument(
        "--output",
        type=Path,
        # Save the plot in the repository root by default instead of under the plots/ directory.
        default=Path("epa_scatter.png"),
        help="Output PNG path for the scatter plot",
    )
    parser.add_argument(
        "--svg",
        action="store_true",
        help="Also save an SVG copy next to the PNG output",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="Also save a PDF copy next to the PNG output",
    )
    parser.add_argument(
        "--invert-y",
        action="store_true",
        help="Invert the defensive EPA axis so better defenses trend upward",
    )
    return parser.parse_args()


def load_aggregates(csv_path: Path) -> pd.DataFrame:
    """Load team EPA aggregates from CSV."""

    df = pd.read_csv(csv_path)
    required = {"team", "off_epa_per_play", "def_epa_per_play"}
    missing = required - set(df.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise ValueError(f"CSV is missing required columns: {missing_cols}")

    return df.dropna(subset=["team"]).copy()


def logo_image(path: Path, zoom: float = 0.2) -> Optional[OffsetImage]:
    """Load a logo image as an OffsetImage for matplotlib."""

    if not path.exists():
        return None
    try:
        image = plt.imread(path)
    except OSError:
        return None
    return OffsetImage(image, zoom=zoom)


def draw_logos(
    ax: plt.Axes, df: pd.DataFrame, logos_dir: Path, zoom: float = 0.2
) -> None:
    """Place team logos (or fallback text) at the provided coordinates."""

    for row in df.itertuples(index=False):
        team = str(row.team).upper()
        x = row.off_epa_per_play
        y = row.def_epa_per_play
        if pd.isna(x) or pd.isna(y):
            continue

        image = logo_image(logos_dir / f"{team}.png", zoom=zoom)
        if image:
            ab = AnnotationBbox(image, (x, y), frameon=False)
            ax.add_artist(ab)
            continue

        try:
            placeholder_png = placeholder_logo(team, 256)
            img_arr = plt.imread(BytesIO(placeholder_png))
            image = OffsetImage(img_arr, zoom=zoom)
            ab = AnnotationBbox(image, (x, y), frameon=False)
            ax.add_artist(ab)
            continue
        except Exception:
            pass

        # Fallback to a bold text square when placeholder generation fails
        ax.scatter(x, y, color="black", s=400, marker="s", zorder=5)
        ax.text(
            x,
            y,
            team,
            fontsize=14,
            fontweight="bold",
            color="white",
            ha="center",
            va="center",
            zorder=6,
        )


def add_reference_lines(ax: plt.Axes, df: pd.DataFrame) -> tuple[float, float]:
    """Draw league-average reference lines for offense and defense."""

    league_off = df["off_epa_per_play"].mean()
    league_def = df["def_epa_per_play"].mean()

    ax.axvline(league_off, color="gray", linestyle="--", linewidth=1, label="League Offense Avg")
    ax.axhline(league_def, color="gray", linestyle=":", linewidth=1, label="League Defense Avg")

    ax.text(league_off, ax.get_ylim()[0], " Off avg", color="gray", ha="left", va="bottom")
    ax.text(ax.get_xlim()[1], league_def, "Def avg ", color="gray", ha="right", va="bottom")
    return league_off, league_def


def format_axes(ax: plt.Axes, invert_y: bool) -> None:
    ax.set_xlabel("Offensive EPA per play (higher is better)")
    ax.set_ylabel("Defensive EPA per play (lower is better)")
    ax.margins(0.1)
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.6)
    if invert_y:
        ax.invert_yaxis()


def build_titles(ax: plt.Axes, season: int, week_label: Optional[str]) -> None:
    title = f"Offense vs Defense Efficiency (EPA/play), {season}"
    subtitle_parts = ["Negative is better for defense"]
    if week_label:
        subtitle_parts.append(str(week_label))
    ax.set_title("\n".join([title, " ".join(subtitle_parts)]))


def save_outputs(fig: plt.Figure, output: Path, save_svg: bool, save_pdf: bool) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=300, bbox_inches="tight")
    stem = output.with_suffix("")
    if save_svg:
        fig.savefig(stem.with_suffix(".svg"), bbox_inches="tight")
    if save_pdf:
        fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")


def main() -> None:
    args = parse_args()

    csv_path = args.csv or (Path("data") / f"team_epa_{args.season}.csv")
    df = load_aggregates(csv_path)

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.scatter(df["off_epa_per_play"], df["def_epa_per_play"], alpha=0)
    draw_logos(ax, df, args.logos_dir)
    format_axes(ax, invert_y=args.invert_y)
    add_reference_lines(ax, df)
    build_titles(ax, args.season, args.week)

    plt.tight_layout()
    save_outputs(fig, args.output, save_svg=args.svg, save_pdf=args.pdf)
    print(f"Saved plot to {args.output}")


if __name__ == "__main__":
    main()
