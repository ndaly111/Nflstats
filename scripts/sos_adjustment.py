"""Schedule-adjusted EPA helpers.

This module computes a ridge-regularised SRS-style rating from team-game net
EPA/play values. Ratings are centred to league average so positive numbers
represent above-average performance after adjusting for opponent quality.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_sos_adjusted_net_epa(team_games: pd.DataFrame, lam: float = 20.0) -> pd.Series:
    """Return schedule-adjusted net EPA/play ratings for each team.

    Deprecated in favour of :func:`compute_sos_adjusted_off_def` but retained for
    backward compatibility.
    """

    required = {"team", "opp", "net_epa_pp", "plays"}
    missing = required - set(team_games.columns)
    if missing:
        raise ValueError(f"team_games is missing required columns: {sorted(missing)}")

    if team_games.empty:
        return pd.Series(dtype=float, name="net_epa_pp_sos_adj")

    teams = sorted(set(team_games["team"].astype(str)) | set(team_games["opp"].astype(str)))
    team_to_idx = {team: idx for idx, team in enumerate(teams)}

    m = len(team_games)
    n = len(teams)

    A = np.zeros((m, n), dtype=float)
    b = team_games["net_epa_pp"].to_numpy(dtype=float)
    w = team_games["plays"].to_numpy(dtype=float)

    for row_idx, row in enumerate(team_games.itertuples(index=False)):
        team_idx = team_to_idx[str(row.team)]
        opp_idx = team_to_idx[str(row.opp)]
        A[row_idx, team_idx] = 1.0
        A[row_idx, opp_idx] = -1.0

    sw = np.sqrt(np.clip(w, 0, None))
    Aw = A * sw[:, None]
    bw = b * sw

    reg_identity = lam * np.eye(n)
    lhs = Aw.T @ Aw + reg_identity
    rhs = Aw.T @ bw

    ratings = np.linalg.solve(lhs, rhs)
    ratings = ratings - ratings.mean()

    return pd.Series(ratings, index=teams, name="net_epa_pp_sos_adj")


def compute_sos_adjusted_off_def(team_games: pd.DataFrame, lam: float = 20.0) -> pd.DataFrame:
    """Return SOS-adjusted offense and defense ratings.

    Expects ``team_games`` columns: ``team``, ``opp``, ``off_epa_pp``,
    ``off_plays``, ``def_epa_pp`` and ``def_plays``. Ratings are centred by
    subtracting the mean of all coefficients so that league average is zero.
    """

    required = {"team", "opp", "off_epa_pp", "off_plays", "def_epa_pp", "def_plays"}
    missing = required - set(team_games.columns)
    if missing:
        raise ValueError(f"team_games is missing required columns: {sorted(missing)}")

    if team_games.empty:
        return pd.DataFrame(columns=["off_rating", "def_rating"])

    teams = sorted(set(team_games["team"].astype(str)) | set(team_games["opp"].astype(str)))
    team_to_idx = {team: idx for idx, team in enumerate(teams)}

    n = len(teams)
    total_vars = n * 2  # offense and defense per team

    AtA = np.zeros((total_vars, total_vars), dtype=float)
    Atb = np.zeros(total_vars, dtype=float)
    equation_count = 0

    def off_idx(team: str) -> int:
        return team_to_idx[team]

    def def_idx(team: str) -> int:
        return team_to_idx[team] + n

    for row in team_games.itertuples(index=False):
        team = str(row.team)
        opp = str(row.opp)

        # Offense equation: O_team - D_opp = off_epa_pp
        off_weight = float(row.off_plays)
        if off_weight > 0 and pd.notna(row.off_epa_pp):
            t_idx = off_idx(team)
            o_idx = def_idx(opp)
            weight = off_weight
            AtA[t_idx, t_idx] += weight
            AtA[o_idx, o_idx] += weight
            AtA[t_idx, o_idx] -= weight
            AtA[o_idx, t_idx] -= weight
            Atb[t_idx] += weight * float(row.off_epa_pp)
            Atb[o_idx] -= weight * float(row.off_epa_pp)
            equation_count += 1

        # Defense equation: D_team - O_opp = def_epa_pp
        def_weight = float(row.def_plays)
        if def_weight > 0 and pd.notna(row.def_epa_pp):
            t_idx = def_idx(team)
            o_idx = off_idx(opp)
            weight = def_weight
            AtA[t_idx, t_idx] += weight
            AtA[o_idx, o_idx] += weight
            AtA[t_idx, o_idx] -= weight
            AtA[o_idx, t_idx] -= weight
            Atb[t_idx] += weight * float(row.def_epa_pp)
            Atb[o_idx] -= weight * float(row.def_epa_pp)
            equation_count += 1

    if equation_count == 0:
        return pd.DataFrame(columns=["off_rating", "def_rating"])

    AtA += lam * np.eye(total_vars)
    ratings = np.linalg.solve(AtA, Atb)

    # Centre both offense and defense around league average
    ratings = ratings - ratings.mean()

    off_ratings = pd.Series(ratings[:n], index=teams, name="off_rating")
    def_ratings = pd.Series(ratings[n:], index=teams, name="def_rating")
    return pd.DataFrame({"off_rating": off_ratings, "def_rating": def_ratings})


def compute_sos_faced(team_games: pd.DataFrame, ratings: pd.Series) -> pd.Series:
    """Compute average opponent rating faced by each team.

    Weights each game by the ``plays`` column to emphasise larger samples.
    """

    if team_games.empty or ratings.empty:
        return pd.Series(dtype=float, name="sos_faced")

    games = team_games.copy()
    games["opp_rating"] = games["opp"].map(ratings)
    games = games.dropna(subset=["opp_rating"])

    games["weighted_opp"] = games["opp_rating"] * games["plays"]
    weighted_sum = games.groupby("team")["weighted_opp"].sum()
    total_weight = games.groupby("team")["plays"].sum()

    sos = (weighted_sum / total_weight).reindex(ratings.index).fillna(0.0)
    sos.name = "sos_faced"
    return sos


def compute_split_sos_faced(
    team_games: pd.DataFrame, off_rating: pd.Series, def_rating: pd.Series
) -> tuple[pd.Series, pd.Series]:
    """Compute offense/defense SOS faced using opponent ratings.

    Offense SOS faced averages opponent defensive ratings weighted by ``off_plays``.
    Defense SOS faced averages opponent offensive ratings weighted by ``def_plays``.
    """

    if team_games.empty:
        empty = pd.Series(dtype=float)
        return empty, empty

    games = team_games.copy()
    games["opp_def_rating"] = games["opp"].map(def_rating)
    games["opp_off_rating"] = games["opp"].map(off_rating)

    off_weighted = games.assign(weight=lambda df: df["off_plays"].clip(lower=0)).copy()
    off_weighted["weighted"] = off_weighted["opp_def_rating"] * off_weighted["weight"]
    off_sum = off_weighted.groupby("team")["weighted"].sum()
    off_total = off_weighted.groupby("team")["weight"].sum()

    def_weighted = games.assign(weight=lambda df: df["def_plays"].clip(lower=0)).copy()
    def_weighted["weighted"] = def_weighted["opp_off_rating"] * def_weighted["weight"]
    def_sum = def_weighted.groupby("team")["weighted"].sum()
    def_total = def_weighted.groupby("team")["weight"].sum()

    all_teams = sorted(set(team_games["team"].astype(str)) | set(team_games["opp"].astype(str)))
    sos_off = (off_sum / off_total).reindex(all_teams).fillna(0.0)
    sos_off.name = "sos_off_faced"
    sos_def = (def_sum / def_total).reindex(all_teams).fillna(0.0)
    sos_def.name = "sos_def_faced"

    return sos_off, sos_def

