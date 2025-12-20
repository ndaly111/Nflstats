import pandas as pd
import nfl_data_py as nfl


def download_pbp(year: int) -> pd.DataFrame:
    """Download play-by-play data for the given season including EPA."""
    return nfl.import_pbp_data(years=[year], cache=True)


def compute_team_epa(pbp: pd.DataFrame) -> pd.DataFrame:
    """Compute per-team offensive and defensive EPA metrics."""
    pbp = pbp[pbp["epa"].notna()]

    off = (
        pbp.groupby("posteam")["epa"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "EPA_off_total", "count": "Plays_off"})
    )
    off["EPA_off_per_play"] = off["EPA_off_total"] / off["Plays_off"]

    defn = (
        pbp.groupby("defteam")["epa"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "EPA_def_total", "count": "Plays_def"})
    )
    defn["EPA_def_per_play"] = -defn["EPA_def_total"] / defn["Plays_def"]

    return pd.concat([off, defn], axis=1).fillna(0)
