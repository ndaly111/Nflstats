"""Create a horizontal bar chart of offensive EPA/play by team."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

REQUIRED_COLUMNS = {"team", "EPA_off_per_play"}


def _validate_columns(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise ValueError(f"CSV is missing required columns: {missing_cols}")


def _normalize_output_path(output_path: Path | str) -> Path:
    output = Path(output_path)
    # Ensure the output lives in the project root (no nested directories).
    return Path(output.name)


def plot_offense_bar_chart(csv_path: Path | str, output_path: Path | str = Path("offense_epa_bar.png")) -> Path:
    """Plot offensive EPA/play by team and save as a PNG in the repo root.

    Parameters
    ----------
    csv_path: Path | str
        Path to a CSV containing at least ``team`` and ``EPA_off_per_play`` columns.
    output_path: Path | str, optional
        Filename for the PNG output. If a directory is provided, only the file name
        is used so the image is saved in the repository root.

    Returns
    -------
    Path
        The path to the saved PNG file in the project root.
    """

    csv_path = Path(csv_path)
    output = _normalize_output_path(output_path)

    df = pd.read_csv(csv_path)
    _validate_columns(df)

    # Drop rows with missing values and sort best to worst.
    data = df.dropna(subset=["EPA_off_per_play"]).copy()
    data.sort_values("EPA_off_per_play", ascending=True, inplace=True)

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.barh(data["team"], data["EPA_off_per_play"], color="#1f77b4")
    ax.set_xlabel("Offensive EPA per play")
    ax.set_title("Offensive Efficiency by Team")
    ax.grid(True, axis="x", linestyle="--", linewidth=0.5, alpha=0.6)

    plt.tight_layout()
    fig.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(fig)

    return output


if __name__ == "__main__":
    plot_offense_bar_chart(Path("nfl_2025_team_epa.csv"))
