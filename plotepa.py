"""Plot offensive vs defensive EPA per play using team color squares."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import pandas as pd

from plot_team_color_squares import NFL_TEAM_COLORS


REQUIRED_COLUMNS = {"team", "EPA_off_per_play", "EPA_def_per_play"}


def _validate_columns(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise ValueError(f"CSV is missing required columns: {missing_cols}")


def _team_color(team: str) -> str:
    colors = NFL_TEAM_COLORS.get(team.upper())
    if not colors:
        return "#333333"
    return colors.get("primary", "#333333")


def plot_epa(csv_path: Path | str, output_path: Path | str = Path("epa_team_colors.png")) -> Path:
    """Generate a scatter plot of offensive vs defensive EPA per play.

    Points are rendered as small squares colored with each team's primary color.
    """

    csv_path = Path(csv_path)
    output = Path(output_path)

    df = pd.read_csv(csv_path)
    _validate_columns(df)

    # Ensure we only plot rows with numeric values for both axes.
    df = df.dropna(subset=["EPA_off_per_play", "EPA_def_per_play"]).copy()

    output.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 6))

    # Plot with small square markers.
    colors: Iterable[str] = (_team_color(team) for team in df["team"])
    ax.scatter(
        df["EPA_off_per_play"],
        df["EPA_def_per_play"],
        marker="s",
        s=40,
        c=list(colors),
        edgecolors="black",
        linewidths=0.4,
    )

    ax.set_xlabel("EPA_off_per_play")
    ax.set_ylabel("EPA_def_per_play")
    ax.set_title("Offense vs Defense EPA per Play")
    ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.6)

    plt.tight_layout()
    fig.savefig(output, dpi=200)
    plt.close(fig)

    return output


def main() -> None:
    plot_epa(Path("nfl_2025_team_epa.csv"))


if __name__ == "__main__":
    main()
