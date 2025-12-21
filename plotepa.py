from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

def _load_epa_csv(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    # promote unnamed index column to 'team'
    if "team" not in df.columns:
        unnamed = [c for c in df.columns if str(c).lower().startswith("unnamed")]
        if unnamed:
            df = df.rename(columns={unnamed[0]: "team"})
    # normalise legacy column names
    if "EPA_off_per_play" not in df.columns and "off_epa_per_play" in df.columns:
        df = df.rename(columns={"off_epa_per_play": "EPA_off_per_play"})
    if "EPA_def_per_play" not in df.columns and "def_epa_per_play" in df.columns:
        df = df.rename(columns={"def_epa_per_play": "EPA_def_per_play"})
    required = {"team", "EPA_off_per_play", "EPA_def_per_play"}
    if not required.issubset(df.columns):
        missing = required - set(df.columns)
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    df["team"] = df["team"].astype(str).str.strip().str.upper()
    df["EPA_off_per_play"] = pd.to_numeric(df["EPA_off_per_play"], errors="coerce")
    df["EPA_def_per_play"] = pd.to_numeric(df["EPA_def_per_play"], errors="coerce")
    return df.dropna(subset=["EPA_off_per_play", "EPA_def_per_play"])

def plot_epa(csv_path: str) -> str:
    """Read the team‑EPA CSV and save an offense‑vs‑defense scatter plot."""
    df = _load_epa_csv(csv_path)
    plots_dir = Path(__file__).resolve().parent / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    output_path = plots_dir / "epa_scatter.png"
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(df["EPA_off_per_play"], df["EPA_def_per_play"], color="steelblue")
    for _, row in df.iterrows():
        ax.text(row["EPA_off_per_play"], row["EPA_def_per_play"], row["team"], fontsize=8)
    ax.set_xlabel("Offensive EPA per play")
    ax.set_ylabel("Defensive EPA per play")
    ax.axvline(0, color="grey", linestyle="--", linewidth=0.7)
    ax.axhline(0, color="grey", linestyle="--", linewidth=0.7)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return str(output_path)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Plot EPA scatter from a team EPA CSV")
    parser.add_argument("csv_path", help="Path to CSV with team EPA columns")
    args = parser.parse_args()
    print(plot_epa(args.csv_path))
