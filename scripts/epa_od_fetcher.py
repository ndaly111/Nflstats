from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import nflreadpy as nfl
import numpy as np
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


def load_pbp_pandas(season: int, max_retries: int = 3, retry_delay: float = 5.0) -> pd.DataFrame:
  """
  Download play-by-play data for a given season using nflreadpy and return a pandas DataFrame.

  Retries up to ``max_retries`` times on transient network errors before raising.
  """
  last_exc: Exception | None = None
  for attempt in range(1, max_retries + 1):
      try:
          pbp_polars = nfl.load_pbp(seasons=season)
          pbp = pbp_polars.to_pandas()
          break
      except Exception as exc:  # pragma: no cover - network/cache issues
          last_exc = exc
          if attempt < max_retries:
              print(f"[fetch] nflreadpy download attempt {attempt} failed: {exc}. Retrying in {retry_delay}s ...")
              time.sleep(retry_delay)
  else:  # pragma: no cover
      raise RuntimeError(
          f"Failed to download/read PBP data for {season} after {max_retries} attempts. "
          f"Last error: {last_exc}"
      ) from last_exc

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

    Returns columns: team, off_epa_sum, off_plays, def_epa_sum, def_plays,
    plus pass/rush split columns (off_pass_epa_sum, off_pass_plays, off_rush_epa_sum,
    off_rush_plays, def_pass_epa_sum, def_pass_plays, def_rush_epa_sum, def_rush_plays).
    Defense values are sign-flipped so higher = better defense.
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

    # Pass / rush split
    _SPLIT_COLS = [
        "off_pass_epa_sum", "off_pass_plays",
        "off_rush_epa_sum", "off_rush_plays",
        "def_pass_epa_sum", "def_pass_plays",
        "def_rush_epa_sum", "def_rush_plays",
    ]
    if "play_type" in df.columns:
        pt = df["play_type"].astype(str).str.lower()
        df_pass = df[pt == "pass"]
        df_rush = df[pt == "run"]

        def _split_agg(sub: pd.DataFrame, group_col: str, prefix: str, sign: int) -> pd.DataFrame:
            if sub.empty:
                return pd.DataFrame(columns=["team", f"{prefix}_epa_sum", f"{prefix}_plays"])
            result = (
                sub.dropna(subset=[group_col])
                .groupby(group_col)["epa"]
                .agg(**{f"{prefix}_epa_sum": "sum", f"{prefix}_plays": "count"})
                .reset_index()
                .rename(columns={group_col: "team"})
            )
            if sign == -1:
                result[f"{prefix}_epa_sum"] = -result[f"{prefix}_epa_sum"]
            return result

        for prefix, sub, col, sign in [
            ("off_pass", df_pass, "posteam", 1),
            ("off_rush", df_rush, "posteam", 1),
            ("def_pass", df_pass, "defteam", -1),
            ("def_rush", df_rush, "defteam", -1),
        ]:
            split = _split_agg(sub, col, prefix, sign)
            merged = merged.merge(split, on="team", how="left")
    else:
        for col in _SPLIT_COLS:
            merged[col] = 0

    for col in _SPLIT_COLS:
        merged[col] = pd.to_numeric(merged.get(col, 0), errors="coerce").fillna(0)

    return merged[
        ["team", "off_epa_sum", "off_plays", "def_epa_sum", "def_plays"] + _SPLIT_COLS
    ].sort_values("team").reset_index(drop=True)


def compute_team_game_epa(pbp: pd.DataFrame, week: int) -> pd.DataFrame:
    """Compute per-team, per-game EPA metrics for a specific week."""

    required_columns = {"game_id", "posteam", "defteam", "epa"}
    missing = required_columns - set(pbp.columns)
    if missing:
        raise ValueError(f"PBP data missing required columns for team-game EPA: {sorted(missing)}")

    df = pbp.copy()
    df["epa"] = pd.to_numeric(df["epa"], errors="coerce")
    df = df.dropna(subset=["epa", "posteam", "defteam", "game_id"])

    home_col = away_col = None
    if {"home_team", "away_team", "total_home_score", "total_away_score"}.issubset(df.columns):
        home_col, away_col = "total_home_score", "total_away_score"
    elif {"home_team", "away_team", "home_score", "away_score"}.issubset(df.columns):
        home_col, away_col = "home_score", "away_score"

    # Offensive perspective
    off = (
        df.groupby(["game_id", "posteam", "defteam"])["epa"]
        .agg(off_epa_sum="sum", off_plays="count")
        .reset_index()
        .rename(columns={"posteam": "team", "defteam": "opp"})
    )

    # Defensive perspective (sign flipped so higher = better)
    deff = (
        df.groupby(["game_id", "defteam", "posteam"])["epa"]
        .agg(def_epa_sum="sum", def_plays="count")
        .reset_index()
        .rename(columns={"defteam": "team", "posteam": "opp"})
    )
    deff["def_epa_sum"] = -deff["def_epa_sum"]

    merged = off.merge(deff, on=["game_id", "team", "opp"], how="outer")
    merged[["off_epa_sum", "def_epa_sum"]] = merged[["off_epa_sum", "def_epa_sum"]].fillna(0.0)
    merged[["off_plays", "def_plays"]] = merged[["off_plays", "def_plays"]].fillna(0)

    merged["team"] = merged["team"].astype(str).str.upper()
    merged["opp"] = merged["opp"].astype(str).str.upper()

    sentinel_points = -1
    if home_col and away_col and {"home_team", "away_team"}.issubset(df.columns):
        score_df = df[["game_id", "home_team", "away_team", home_col, away_col]].copy()
        score_df[home_col] = pd.to_numeric(score_df[home_col], errors="coerce")
        score_df[away_col] = pd.to_numeric(score_df[away_col], errors="coerce")
        final_scores = (
            score_df.groupby("game_id")
            .agg(
                home_team=("home_team", "first"),
                away_team=("away_team", "first"),
                home_points=(home_col, "max"),
                away_points=(away_col, "max"),
            )
            .reset_index()
        )
        final_scores[["home_team", "away_team"]] = final_scores[["home_team", "away_team"]].apply(
            lambda col: col.astype(str).str.upper()
        )
        merged = merged.merge(final_scores, on="game_id", how="left")
        merged["home_points"] = merged["home_points"].fillna(sentinel_points)
        merged["away_points"] = merged["away_points"].fillna(sentinel_points)
        merged["points_for"] = np.select(
            [merged["team"] == merged["home_team"], merged["team"] == merged["away_team"]],
            [merged["home_points"], merged["away_points"]],
            default=sentinel_points,
        )
        merged["points_against"] = np.select(
            [merged["team"] == merged["home_team"], merged["team"] == merged["away_team"]],
            [merged["away_points"], merged["home_points"]],
            default=sentinel_points,
        )
    else:
        merged["points_for"] = sentinel_points
        merged["points_against"] = sentinel_points

    merged = merged[(merged["off_plays"] > 0) & (merged["def_plays"] > 0)].copy()

    merged["off_epa_pp"] = merged["off_epa_sum"] / merged["off_plays"]
    merged["def_epa_pp"] = merged["def_epa_sum"] / merged["def_plays"]

    merged["plays"] = merged["off_plays"].astype(int) + merged["def_plays"].astype(int)
    merged["net_epa_pp"] = merged["off_epa_pp"] + merged["def_epa_pp"]
    merged["net_epa_sum"] = merged["off_epa_sum"] + merged["def_epa_sum"]
    merged["week"] = week
    merged["points_for"] = merged["points_for"].fillna(sentinel_points).astype(int)
    merged["points_against"] = merged["points_against"].fillna(sentinel_points).astype(int)

    return merged[
        [
            "game_id",
            "week",
            "team",
            "opp",
            "off_epa_sum",
            "off_plays",
            "off_epa_pp",
            "def_epa_sum",
            "def_plays",
            "def_epa_pp",
            "points_for",
            "points_against",
            "net_epa_sum",
            "plays",
            "net_epa_pp",
        ]
    ]


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
