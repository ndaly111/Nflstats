"""Per-player EPA aggregation from nflverse play-by-play.

Roles describe what a player did on the play -- passing, rushing, receiving --
rather than a position, because play-by-play gives us the action and never the
depth chart. A quarterback's designed runs therefore land in rushing, which is
what actually happened.

Two conventions worth stating, because they change the numbers:

* Passing means dropbacks, not attempts. Sacks and scrambles are the quarterback
  choosing to keep the ball, so they belong to his passing line; excluding them
  flatters a quarterback who takes bad sacks. nflverse leaves ``passer_player_id``
  empty on a scramble and puts the quarterback in the rusher columns instead, so
  scrambles are picked up from there.
* Receiving is per target, not per catch. ``receiver_player_id`` is filled in on
  incompletions when the intended receiver is identifiable, which is most but not
  all of them -- throwaways and batted balls have no target, so they charge the
  passer alone. Receiving EPA therefore excludes some of the worst pass outcomes
  and reads slightly generous.
"""
from __future__ import annotations

import pandas as pd

PASSING = "passing"
RUSHING = "rushing"
RECEIVING = "receiving"
ROLES = (PASSING, RUSHING, RECEIVING)

OUTPUT_COLS = ["week", "team", "player_id", "player_name", "role", "epa_sum", "plays"]

_GROUP_COLS = ["team", "player_id", "player_name", "role", "epa_sum", "plays"]


def _flag(df: pd.DataFrame, col: str) -> pd.Series:
    """Read a 0/1 play-by-play flag that may be missing or null."""
    if col not in df.columns:
        return pd.Series(False, index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(0) == 1


def _aggregate(sub: pd.DataFrame, id_col: str, name_col: str, role: str) -> pd.DataFrame:
    if sub.empty or id_col not in sub.columns:
        return pd.DataFrame(columns=_GROUP_COLS)

    d = sub.dropna(subset=[id_col])
    d = d[d[id_col].astype(str).str.strip() != ""]
    if d.empty:
        return pd.DataFrame(columns=_GROUP_COLS)

    name_source = name_col if name_col in d.columns else id_col
    grouped = (
        d.groupby(["posteam", id_col], as_index=False, dropna=False)
        .agg(player_name=(name_source, "last"), epa_sum=("epa", "sum"), plays=("epa", "size"))
        .rename(columns={"posteam": "team", id_col: "player_id"})
    )
    grouped["role"] = role
    grouped["player_name"] = grouped["player_name"].fillna(grouped["player_id"])
    return grouped[_GROUP_COLS]


def compute_player_epa(pbp: pd.DataFrame, week: int) -> pd.DataFrame:
    """Aggregate one week of play-by-play into per-player, per-role EPA totals.

    Returns columns: week, team, player_id, player_name, role, epa_sum, plays.
    Offense only -- standard play-by-play credits defensive EPA to the team, with
    no defender attached to the play.
    """
    df = pbp.copy()
    df["epa"] = pd.to_numeric(df["epa"], errors="coerce")
    df = df.dropna(subset=["epa", "posteam"])
    if df.empty:
        return pd.DataFrame(columns=OUTPUT_COLS)

    df["posteam"] = df["posteam"].astype(str).str.strip().str.upper()
    play_type = df["play_type"].astype(str).str.lower()

    # Kneels and spikes are clock management, not offense. Penalty rows come
    # through as no_play and are excluded by the play_type checks below.
    live = ~_flag(df, "qb_kneel") & ~_flag(df, "qb_spike")
    scramble = _flag(df, "qb_scramble")

    is_dropback = (play_type == "pass") & live
    is_scramble = (play_type == "run") & scramble & live
    is_rush = (play_type == "run") & ~scramble & live

    parts = [
        _aggregate(df[is_dropback], "passer_player_id", "passer_player_name", PASSING),
        _aggregate(df[is_scramble], "rusher_player_id", "rusher_player_name", PASSING),
        _aggregate(df[is_rush], "rusher_player_id", "rusher_player_name", RUSHING),
        _aggregate(df[is_dropback], "receiver_player_id", "receiver_player_name", RECEIVING),
    ]
    parts = [p for p in parts if not p.empty]
    if not parts:
        return pd.DataFrame(columns=OUTPUT_COLS)

    # Dropbacks and scrambles both land in `passing`, so fold them together.
    out = (
        pd.concat(parts, ignore_index=True)
        .groupby(["team", "player_id", "role"], as_index=False, dropna=False)
        .agg(player_name=("player_name", "last"), epa_sum=("epa_sum", "sum"), plays=("plays", "sum"))
    )
    out.insert(0, "week", week)
    return out[OUTPUT_COLS].reset_index(drop=True)
