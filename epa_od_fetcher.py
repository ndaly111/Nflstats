import pandas as pd
import nflreadpy as nfl

REQUIRED_COLS = {"epa", "posteam", "defteam"}

def download_pbp(year: int) -> pd.DataFrame:
    """
    Download play-by-play data for a given season year using nflreadpy.
    Converts the returned Polars dataframe to pandas and validates required columns.
    """
    try:
        pbp_polars = nfl.load_pbp(seasons=year)
        pbp = pbp_polars.to_pandas()
    except Exception as e:  # pragma: no cover - network/cache issues
        raise RuntimeError(
            f"Failed to download/read PBP data for {year} using nflreadpy. "
            f"Original error: {e}"
        ) from e

    # Validate we actually got what we need
    if not isinstance(pbp, pd.DataFrame):
        raise RuntimeError(f"Unexpected return type from load_pbp: {type(pbp)}")

    if pbp.empty:
        raise RuntimeError(
            f"PBP dataframe is empty for {year}. "
            f"Either the season data isn't published yet, or the download failed."
        )

    missing = REQUIRED_COLS.difference(pbp.columns)
    if missing:
        # Print some debugging info to Actions logs
        print("\nDEBUG: pbp columns returned:")
        print(sorted(list(pbp.columns))[:80])
        print("\nDEBUG: pbp head():")
        print(pbp.head(3).to_string())

        raise RuntimeError(
            f"PBP data loaded for {year}, but required columns are missing: {sorted(list(missing))}. "
            f"This usually means the data file didn't load correctly or returned unexpected schema."
        )

    return pbp

def compute_team_epa(pbp: pd.DataFrame) -> pd.DataFrame:
    """
    Compute EPA per play for each team's offense and defense.
    Defense is shown as 'EPA_def_per_play' where higher = better (i.e., allowed EPA * -1).
    """
    pbp = pbp[pbp["epa"].notna()].copy()

    # Offensive EPA: by possession team
    off = (
        pbp.groupby("posteam")["epa"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "EPA_off_total", "count": "Plays_off"})
    )
    off["EPA_off_per_play"] = off["EPA_off_total"] / off["Plays_off"]

    # Defensive EPA allowed: by defensive team
    defn = (
        pbp.groupby("defteam")["epa"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "EPA_def_total", "count": "Plays_def"})
    )
    # Flip sign so higher = better defense (less EPA allowed)
    defn["EPA_def_per_play"] = -defn["EPA_def_total"] / defn["Plays_def"]

    team_epa = pd.concat([off, defn], axis=1).fillna(0)

    # Nice consistent ordering; keep team as an explicit column for downstream CSV/plots
    team_epa = team_epa.reset_index().rename(columns={"index": "team"})
    if "posteam" in team_epa.columns:
        team_epa = team_epa.rename(columns={"posteam": "team"})
    elif "defteam" in team_epa.columns:
        team_epa = team_epa.rename(columns={"defteam": "team"})

    return team_epa
