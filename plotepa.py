import os
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


def plot_epa(csv_path: str) -> str:
    """Create a simple EPA scatter plot for offense vs defense.

    Parameters
    ----------
    csv_path: str
        Path to a CSV containing columns ``team``, ``EPA_off_per_play`` and
        ``EPA_def_per_play``.

    Returns
    -------
    str
        File path to the saved plot image.
    """
    df = pd.read_csv(csv_path)
    plots_dir = Path("plots")
    plots_dir.mkdir(exist_ok=True)
    output_path = plots_dir / "epa_scatter.png"

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(df["EPA_off_per_play"], df["EPA_def_per_play"], color="steelblue")
    for _, row in df.iterrows():
        ax.text(row["EPA_off_per_play"], row["EPA_def_per_play"], row["team"], fontsize=8)

    ax.set_xlabel("Offensive EPA per play")
    ax.set_ylabel("Defensive EPA per play (higher is better)")
    ax.axvline(0, color="grey", linestyle="--", linewidth=0.7)
    ax.axhline(0, color="grey", linestyle="--", linewidth=0.7)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return str(output_path)
