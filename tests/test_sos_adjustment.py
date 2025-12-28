import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from scripts.sos_adjustment import compute_sos_adjusted_off_def, compute_split_sos_faced


def test_off_def_ratings_center_to_zero():
    data = pd.DataFrame(
        [
            {"team": "A", "opp": "B", "off_epa_pp": 0.2, "off_plays": 60, "def_epa_pp": 0.1, "def_plays": 60},
            {"team": "B", "opp": "A", "off_epa_pp": -0.2, "off_plays": 60, "def_epa_pp": -0.1, "def_plays": 60},
        ]
    )

    ratings = compute_sos_adjusted_off_def(data, lam=1.0)
    stacked = np.concatenate([ratings["off_rating"].to_numpy(), ratings["def_rating"].to_numpy()])
    assert math.isclose(float(stacked.mean()), 0.0, abs_tol=1e-9)


def test_off_def_ratings_zero_signal_return_zero():
    games = pd.DataFrame(
        [
            {"team": "A", "opp": "B", "off_epa_pp": 0.0, "off_plays": 30, "def_epa_pp": 0.0, "def_plays": 30},
            {"team": "B", "opp": "A", "off_epa_pp": 0.0, "off_plays": 30, "def_epa_pp": 0.0, "def_plays": 30},
        ]
    )

    ratings = compute_sos_adjusted_off_def(games, lam=5.0)

    assert ratings["off_rating"].abs().max() <= 1e-9
    assert ratings["def_rating"].abs().max() <= 1e-9


def test_split_sos_uses_opponent_axes():
    games = pd.DataFrame(
        [
            {"team": "A", "opp": "B", "off_epa_pp": 0.5, "off_plays": 20, "def_epa_pp": 1.0, "def_plays": 10},
            {"team": "B", "opp": "A", "off_epa_pp": -0.5, "off_plays": 20, "def_epa_pp": -1.0, "def_plays": 10},
        ]
    )

    ratings = compute_sos_adjusted_off_def(games, lam=5.0)
    sos_off, sos_def = compute_split_sos_faced(games, ratings["off_rating"], ratings["def_rating"])

    assert math.isclose(float(sos_off.loc["A"]), float(ratings.loc["B", "def_rating"]), rel_tol=1e-3)
    assert math.isclose(float(sos_def.loc["A"]), float(ratings.loc["B", "off_rating"]), rel_tol=1e-3)


def test_empty_equations_returns_empty_frame():
    games = pd.DataFrame(
        [
            {"team": "A", "opp": "B", "off_epa_pp": 0.0, "off_plays": 0, "def_epa_pp": 0.0, "def_plays": 0},
            {"team": "B", "opp": "A", "off_epa_pp": 0.0, "off_plays": 0, "def_epa_pp": 0.0, "def_plays": 0},
        ]
    )

    ratings = compute_sos_adjusted_off_def(games, lam=5.0)

    assert ratings.empty
