"""
Create an offense‑vs‑defense EPA scatter plot for NFL teams.

This script reads per‑team offensive and defensive EPA per play from the SQLite
cache populated by ``scripts.fetch_epa``. Each team is drawn as a coloured
hex‑style square using primary/secondary colours defined in
``plot_team_color_squares.NFL_TEAM_COLORS`` and labelled with the team
city/region name (e.g., "Washington" for WAS). Two reference lines are drawn at
the league‑average offensive and defensive EPA values. The resulting chart can
be saved to disk or streamed directly (used by the Flask app).

Defense EPA values from ``scripts.fetch_epa`` are already sign-flipped so
"higher = better defense". Use ``--invert-y`` only if you are plotting legacy
data that did not flip defensive EPA.

Example usage::

    python -m scripts.plot_epa_scatter --season 2025 --week-start 1 --week-end 6
"""

import argparse
from pathlib import Path
from typing import IO, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

try:
    # Prefer DB-backed data when available.
    from .db_storage import load_team_epa_from_db, DB_PATH
except ImportError:  # pragma: no cover
    try:
        from scripts.db_storage import load_team_epa_from_db, DB_PATH
    except ImportError:  # pragma: no cover
        load_team_epa_from_db = None  # type: ignore
        DB_PATH = None  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[1]

try:
    # When executed as: python -m scripts.plot_epa_scatter
    from .plot_team_color_squares import NFL_TEAM_COLORS, pick_text_color
except ImportError:  # pragma: no cover
    try:
        from plot_team_color_squares import NFL_TEAM_COLORS, pick_text_color
    except ImportError:  # pragma: no cover
        import sys

        sys.path.insert(0, str(REPO_ROOT))
        from plot_team_color_squares import NFL_TEAM_COLORS, pick_text_color


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot offense vs defense EPA scatter for NFL teams.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--season",
        type=int,
        required=True,
        help="Season year for the EPA snapshot",
    )
    parser.add_argument(
        "--week-label",
        type=str,
        default=None,
        help="Optional subtitle describing the week range (e.g., 'Weeks 1–6')",
    )
    parser.add_argument(
        "--week-start",
        type=int,
        default=None,
        help="Start week (defaults to first cached week)",
    )
    parser.add_argument(
        "--week-end",
        type=int,
        default=None,
        help="End week (defaults to latest cached week)",
    )
    parser.add_argument(
        "--invert-y",
        action="store_true",
        default=False,
        help="Invert defensive EPA axis (only for legacy, non-flipped data).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="epa_scatter.png",
        help="File path to save the resulting PNG chart",
    )
    return parser.parse_args()


# City/region labels for each team abbreviation
TEAM_DISPLAY_NAMES = {
    "ARI": "Arizona",
    "ATL": "Atlanta",
    "BAL": "Baltimore",
    "BUF": "Buffalo",
    "CAR": "Carolina",
    "CHI": "Chicago",
    "CIN": "Cincinnati",
    "CLE": "Cleveland",
    "DAL": "Dallas",
    "DEN": "Denver",
    "DET": "Detroit",
    "GB": "Green Bay",
    "HOU": "Houston",
    "IND": "Indianapolis",
    "JAX": "Jacksonville",
    "KC": "Kansas City",
    "LAC": "Los Angeles (Chargers)",
    "LAR": "Los Angeles (Rams)",
    "LV": "Las Vegas",
    "MIA": "Miami",
    "MIN": "Minnesota",
    "NE": "New England",
    "NO": "New Orleans",
    "NYG": "New York (Giants)",
    "NYJ": "New York (Jets)",
    "PHI": "Philadelphia",
    "PIT": "Pittsburgh",
    "SEA": "Seattle",
    "SF": "San Francisco",
    "TB": "Tampa Bay",
    "TEN": "Tennessee",
    "WAS": "Washington",
}


def _normalize_team_epa_df(df: pd.DataFrame, source_desc: str) -> pd.DataFrame:
    """Normalize column names and index for plotting."""

    # Handle legacy dataframes that may include a numeric index column
    if "team" not in df.columns:
        unnamed = [c for c in df.columns if str(c).lower().startswith("unnamed")]
        if unnamed:
            df = df.rename(columns={unnamed[0]: "team"})

    # Normalize common column-name variants
    rename_map = {}
    if "off_epa_per_play" in df.columns and "EPA_off_per_play" not in df.columns:
        rename_map["off_epa_per_play"] = "EPA_off_per_play"
    if "def_epa_per_play" in df.columns and "EPA_def_per_play" not in df.columns:
        rename_map["def_epa_per_play"] = "EPA_def_per_play"
    if rename_map:
        df = df.rename(columns=rename_map)

    required = {"team", "EPA_off_per_play", "EPA_def_per_play"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"{source_desc} is missing required columns: {', '.join(sorted(missing))}. "
            f"Found columns: {', '.join(df.columns.astype(str))}"
        )

    df["team"] = df["team"].astype(str).str.strip().str.upper()
    df["EPA_off_per_play"] = pd.to_numeric(df["EPA_off_per_play"], errors="coerce")
    df["EPA_def_per_play"] = pd.to_numeric(df["EPA_def_per_play"], errors="coerce")
    return df.set_index("team")


def load_team_epa(
    season: int, week_start: Optional[int] = None, week_end: Optional[int] = None
) -> pd.DataFrame:
    """
    Load per‑team EPA data from the SQLite cache and normalise for plotting.

    Parameters
    ----------
    season : int
        Season year used to query the SQLite cache.
    week_start : int, optional
        Week number marking the start of the aggregation window. Defaults to the
        first cached week for the season.
    week_end : int, optional
        Week number marking the end of the aggregation window. Defaults to the
        latest cached week for the season.
    Returns
    -------
    pd.DataFrame
        Team EPA metrics indexed by team.
    """
    if load_team_epa_from_db is None:
        raise RuntimeError("Database support is unavailable; cannot load team EPA data.")

    df_db = load_team_epa_from_db(season, week_start=week_start, week_end=week_end)
    if df_db is None:
        raise FileNotFoundError(
            f"No EPA data found for season {season} in SQLite cache at {DB_PATH}. "
            "Run the fetch workflow to populate the database first."
        )
    normalized = _normalize_team_epa_df(df_db, f"SQLite cache at {DB_PATH}")
    normalized.attrs["week_start"] = df_db.attrs.get("week_start")
    normalized.attrs["week_end"] = df_db.attrs.get("week_end")
    if "week" in df_db.attrs:
        normalized.attrs["week"] = df_db.attrs["week"]
    return normalized


def add_team_marker(
    ax: plt.Axes,
    x: float,
    y: float,
    team: str,
) -> None:
    """
    Draw a team marker at the specified coordinates.

    A coloured square with the team's city/region name is drawn using
    primary/secondary colours defined in ``NFL_TEAM_COLORS``.
    """

    colours = NFL_TEAM_COLORS.get(team, {"primary": "#777777", "secondary": "#FFFFFF"})
    primary = colours["primary"]
    secondary = colours["secondary"]
    text_color = pick_text_color(primary, secondary)
    label = TEAM_DISPLAY_NAMES.get(team, team)
    # Draw square marker
    ax.scatter(
        [x],
        [y],
        marker="s",
        s=400,  # adjust size for readability
        color=primary,
        edgecolors="black",
        linewidths=0.5,
        zorder=3,
    )
    ax.text(
        x,
        y,
        label,
        ha="center",
        va="center",
        fontsize=8,
        fontweight="bold",
        color=text_color,
        zorder=4,
    )


def plot_scatter(
    df: pd.DataFrame,
    week_label: Optional[str],
    invert_y: bool,
    output: Path | IO[bytes],
    season: int,
) -> None:
    """
    Create and save the offense vs defence scatter plot.

    Parameters
    ----------
    df : pd.DataFrame
        Dataframe indexed by team containing 'EPA_off_per_play' and 'EPA_def_per_play' columns.
    week_label : str, optional
        Subtitle describing the week range (e.g., "Weeks 1–6").  If None, a default
        'Season to date' subtitle is used.
    invert_y : bool
        If True, invert the y-axis direction (only needed for legacy data where lower values
        indicate better defense and no sign flip was applied).
    output : pathlib.Path or binary IO
        Where to write the PNG file or buffer.
    season : int
        Season year for labelling.
    """
    df = df.dropna(subset=["EPA_off_per_play", "EPA_def_per_play"])
    if df.empty:
        raise ValueError("No rows to plot after dropping missing EPA values.")

    # Compute league averages
    x_vals = df["EPA_off_per_play"]
    y_vals = df["EPA_def_per_play"]
    x_avg = x_vals.mean()
    y_avg = y_vals.mean()

    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot each team
    for team, row in df.iterrows():
        add_team_marker(ax, row["EPA_off_per_play"], row["EPA_def_per_play"], team)

    # Draw reference lines at league averages
    ax.axvline(x_avg, color="grey", linestyle="--", linewidth=1.0, zorder=1)
    ax.axhline(y_avg, color="grey", linestyle="--", linewidth=1.0, zorder=1)

    # Label axes
    ax.set_xlabel("Offense EPA per play (higher = better offense)")
    y_label = "Defense EPA per play (higher = better defense)"
    if invert_y:
        y_label += " — axis inverted for legacy data"
    ax.set_ylabel(y_label)

    # Title and subtitle
    title = f"NFL Team Efficiency (EPA/play), {season}"
    subtitle = week_label if week_label else "Season to date"
    ax.set_title(title + "\n" + subtitle, pad=14)

    # Improve layout
    ax.grid(False)
    # Give some margins so markers aren't clipped
    padding_x = (x_vals.max() - x_vals.min()) * 0.1
    padding_y = (y_vals.max() - y_vals.min()) * 0.1
    ax.set_xlim(x_vals.min() - padding_x, x_vals.max() + padding_x)
    y_min = y_vals.min() - padding_y
    y_max = y_vals.max() + padding_y
    if invert_y:
        ax.set_ylim(y_max, y_min)
    else:
        ax.set_ylim(y_min, y_max)

    plt.tight_layout()
    fig.savefig(output, dpi=200, format="png")
    if isinstance(output, (str, Path)):
        print(f"Saved scatter plot to {output}")


def main() -> None:
    args = parse_args()
    season = args.season
    week_label = args.week_label
    invert_y = args.invert_y

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = load_team_epa(season, week_start=args.week_start, week_end=args.week_end)
    start = df.attrs.get("week_start")
    end = df.attrs.get("week_end")
    if week_label is None and start is not None and end is not None:
        if start == end:
            week_label = f"Week {end}"
        else:
            week_label = f"Weeks {start}–{end}"
    plot_scatter(df, week_label, invert_y, output_path, season)


if __name__ == "__main__":
    main()
