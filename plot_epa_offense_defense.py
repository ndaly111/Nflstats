"""Plot offense vs defense EPA per play for every NFL team."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import pandas as pd

from plot_team_color_squares import NFL_TEAM_COLORS

REQUIRED_COLUMNS = {"team", "EPA_off_per_play", "EPA_def_per_play"}


def _validate_input(df: pd.DataFrame) -> pd.DataFrame:
    """Validate required columns exist and drop rows lacking coordinates."""

    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise ValueError(f"CSV is missing required columns: {missing_cols}")

    # Keep only rows that have both offensive and defensive EPA values.
    return df.dropna(subset=["EPA_off_per_play", "EPA_def_per_play"]).copy()


def _team_colors(teams: Iterable[str]) -> list[str]:
    """Look up primary colors for teams, defaulting to a dark gray."""

    colors: list[str] = []
    for team in teams:
        palette = NFL_TEAM_COLORS.get(team.upper())
        colors.append(palette.get("primary", "#333333") if palette else "#333333")
    return colors


def plot_offense_vs_defense(
    csv_path: Path | str,
    output_path: Path | str = Path("epa_offense_vs_defense.png"),
) -> Path:
    """Create scatter plot of offensive vs defensive EPA per play for each team."""

    csv_path = Path(csv_path)
    output_path = Path(output_path)

    df = pd.read_csv(csv_path)
    df = _validate_input(df)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(9, 7))
    colors = _team_colors(df["team"])

    ax.scatter(
        df["EPA_off_per_play"],
        df["EPA_def_per_play"],
        c=colors,
        edgecolors="black",
        linewidths=0.4,
        s=55,
    )

    for row in df.itertuples(index=False):
        ax.text(
            row.EPA_off_per_play,
            row.EPA_def_per_play,
            str(row.team),
            fontsize=8,
            ha="center",
            va="center",
            color="white",
            weight="bold",
            path_effects=[],
        )

    ax.axvline(0, color="gray", linestyle="--", linewidth=0.6)
    ax.axhline(0, color="gray", linestyle="--", linewidth=0.6)
    ax.set_xlabel("Offensive EPA per play (higher is better)")
    ax.set_ylabel("Defensive EPA per play (higher is better)")
    ax.set_title("EPA per Play: Offense vs Defense")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.6)

    plt.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)

    return output_path


def main() -> None:
    plot_offense_vs_defense(Path("nfl_2025_team_epa.csv"))


if __name__ == "__main__":
    main()
