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

    Parameters
    ----------
    team_games : pd.DataFrame
        Dataframe with columns ``team``, ``opp``, ``net_epa_pp`` and ``plays``.
        Each row should correspond to a single team-game (two rows per NFL game).
    lam : float, optional
        Ridge regularisation strength; larger values shrink ratings toward zero.

    Returns
    -------
    pd.Series
        Schedule-adjusted ratings indexed by team, centred to mean zero.
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

