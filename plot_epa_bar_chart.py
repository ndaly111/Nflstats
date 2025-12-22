from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


def plot_offense_bar_chart(csv_path: str) -> str:
    """Plot a bar chart of offensive EPA per play by team."""
    df = pd.read_csv(csv_path)
    df = df.sort_values("EPA_off_per_play", ascending=False)

    plots_dir = Path("plots")
    plots_dir.mkdir(exist_ok=True)
    output_path = plots_dir / "offense_epa_bar.png"

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(df["team"], df["EPA_off_per_play"], color="seagreen")
    ax.set_ylabel("Offensive EPA per play")
    ax.set_xlabel("Team")
    ax.set_title("Offensive EPA per play by Team")
    ax.tick_params(axis="x", rotation=45)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return str(output_path)
