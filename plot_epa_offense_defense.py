from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


def plot_offense_vs_defense(csv_path: str) -> str:
    """Plot offense vs defense EPA with a diagonal reference line."""
    df = pd.read_csv(csv_path)
    plots_dir = Path("plots")
    plots_dir.mkdir(exist_ok=True)
    output_path = plots_dir / "offense_vs_defense.png"

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(df["EPA_off_per_play"], df["EPA_def_per_play"], color="darkorange")
    ax.plot([-0.5, 0.5], [-0.5, 0.5], linestyle="--", color="grey", linewidth=0.7)
    for _, row in df.iterrows():
        ax.text(row["EPA_off_per_play"], row["EPA_def_per_play"], row["team"], fontsize=8)

    ax.set_xlabel("Offensive EPA per play")
    ax.set_ylabel("Defensive EPA per play")
    ax.set_title("Offense vs Defense EPA")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return str(output_path)
