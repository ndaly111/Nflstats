from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import nflreadpy as nfl
import pandas as pd


REQUIRED_WEEK_COLUMN = "week"
WIN_PROB_COLUMN = "wp"
SEASON_TYPE_COLUMN = "season_type"
REQUIRED_COLS = {"epa", "posteam", "defteam"}


@dataclass(frozen=True)
class PbpFilters:
  week_start: Optional[int] = None
  week_end: Optional[int] = None
  min_wp: Optional[float] = None
  max_wp: Optional[float] = None
  include_playoffs: bool = False


def _validate_range(start: Optional[int], end: Optional[int], label: str) -> None:
  if start is not None and end is not None and start > end:
      raise ValueError(f"{label} start ({start}) cannot exceed end ({end})")


def _validate_prob(prob: Optional[float], name: str) -> None:
  if prob is not None and not (0.0 <= prob <= 1.0):
      raise ValueError(f"{name} must be between 0 and 1. Got {prob}")


def load_pbp_pandas(season: int) -> pd.DataFrame:
  """
  Download play-by-play data for a given season using nflreadpy and return a pandas DataFrame.
  """
  try:
      pbp_polars = nfl.load_pbp(seasons=season)
      pbp = pbp_polars.to_pandas()
  except Exception as exc:  # pragma: no cover - network/cache issues
      raise RuntimeError(
          f"Failed to download/read PBP data for {season} using nflreadpy. Original error: {exc}"
      ) from exc

  if not isinstance(pbp, pd.DataFrame):
      raise RuntimeError(f"Unexpected return type from load_pbp: {type(pbp)}")

  missing = REQUIRED_COLS.difference(pbp.columns)
  if missing:
      raise RuntimeError(
          f"PBP data loaded for {season}, but required columns are missing: {sorted(list(missing))}"
      )

  if pbp.empty:
      raise RuntimeError(
          f"PBP dataframe is empty for {season}. Either the season data isn't published yet, or the download failed."
      )

  return pbp


def apply_filters(pbp: pd.DataFrame, filters: PbpFilters) -> pd.DataFrame:
  df = pbp.copy()

  _validate_range(filters.week_start, filters.week_end, "Week")
  _validate_prob(filters.min_wp, "min_wp")
  _validate_prob(filters.max_wp, "max_wp")
  if filters.min_wp is not None and filters.max_wp is not None and filters.min_wp > filters.max_wp:
      raise ValueError(f"min_wp ({filters.min_wp}) cannot exceed max_wp ({filters.max_wp})")

  if not filters.include_playoffs and SEASON_TYPE_COLUMN in df.columns:
      df = df[df[SEASON_TYPE_COLUMN].astype(str).str.upper() == "REG"]

  if filters.week_start is not None or filters.week_end is not None:
      if REQUIRED_WEEK_COLUMN not in df.columns:
          raise ValueError("Play-by-play data missing 'week' column required for filtering")
      df[REQUIRED_WEEK_COLUMN] = pd.to_numeric(df[REQUIRED_WEEK_COLUMN], errors="coerce")
      df = df.dropna(subset=[REQUIRED_WEEK_COLUMN])
      if filters.week_start is not None:
          df = df[df[REQUIRED_WEEK_COLUMN] >= filters.week_start]
      if filters.week_end is not None:
          df = df[df[REQUIRED_WEEK_COLUMN] <= filters.week_end]

  if filters.min_wp is not None or filters.max_wp is not None:
      if WIN_PROB_COLUMN not in df.columns:
          raise ValueError("Play-by-play data missing 'wp' column required for win prob filtering")
      df[WIN_PROB_COLUMN] = pd.to_numeric(df[WIN_PROB_COLUMN], errors="coerce")
      df = df.dropna(subset=[WIN_PROB_COLUMN])
      if filters.min_wp is not None:
          df = df[df[WIN_PROB_COLUMN] >= filters.min_wp]
      if filters.max_wp is not None:
          df = df[df[WIN_PROB_COLUMN] <= filters.max_wp]

  return df


def compute_team_epa(pbp: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-team EPA aggregates for each side of the ball.

    Returns columns: team, off_epa_sum, off_plays, def_epa_sum, def_plays
    with defense sign-flipped so higher = better defense.
    """
    df = pbp.copy()
    df["epa"] = pd.to_numeric(df["epa"], errors="coerce")
    df = df.dropna(subset=["epa"])

    off = (
        df.dropna(subset=["posteam"])
        .groupby("posteam")["epa"]
        .agg(off_epa_sum="sum", off_plays="count")
        .reset_index()
        .rename(columns={"posteam": "team"})
    )

    deff = (
        df.dropna(subset=["defteam"])
        .groupby("defteam")["epa"]
        .agg(def_epa_sum="sum", def_plays="count")
        .reset_index()
        .rename(columns={"defteam": "team"})
    )

    merged = pd.merge(off, deff, on="team", how="outer")
    merged["team"] = merged["team"].astype(str).str.strip().str.upper()
    merged = merged[merged["team"].notna() & (merged["team"] != "") & (merged["team"].str.lower() != "nan")]

    merged["off_epa_sum"] = pd.to_numeric(merged["off_epa_sum"], errors="coerce")
    merged["off_plays"] = pd.to_numeric(merged["off_plays"], errors="coerce")
    merged["def_epa_sum"] = pd.to_numeric(merged["def_epa_sum"], errors="coerce")
    merged["def_plays"] = pd.to_numeric(merged["def_plays"], errors="coerce")
    merged = merged.dropna(subset=["off_epa_sum", "off_plays", "def_epa_sum", "def_plays"])
    merged = merged[merged["off_plays"] > 0]
    merged = merged[merged["def_plays"] > 0]

    # Flip sign so higher = better defense
    merged["def_epa_sum"] = -merged["def_epa_sum"]

    return merged[["team", "off_epa_sum", "off_plays", "def_epa_sum", "def_plays"]].sort_values("team").reset_index(
        drop=True
    )


def build_team_epa(season: int, filters: Optional[PbpFilters] = None) -> pd.DataFrame:
    filters = filters or PbpFilters()

    pbp = load_pbp_pandas(season)
    filtered = apply_filters(pbp, filters)
    team_epa = compute_team_epa(filtered)

    required = {"team", "off_epa_sum", "off_plays", "def_epa_sum", "def_plays"}
    missing = required - set(team_epa.columns)
    if missing:
        raise ValueError(f"Team EPA is missing expected columns: {sorted(missing)}")

    return team_epa[["team", "off_epa_sum", "off_plays", "def_epa_sum", "def_plays"]].copy()
