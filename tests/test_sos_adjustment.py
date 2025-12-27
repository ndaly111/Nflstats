from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from scripts.sos_adjustment import compute_sos_adjusted_net_epa, compute_sos_faced


def test_ratings_center_to_zero():
    data = pd.DataFrame(
        [
            {"team": "A", "opp": "B", "net_epa_pp": 0.2, "plays": 60},
            {"team": "B", "opp": "A", "net_epa_pp": -0.2, "plays": 60},
        ]
    )

    ratings = compute_sos_adjusted_net_epa(data, lam=1.0)
    assert abs(ratings.mean()) < 1e-9


def test_ordering_respects_schedule():
    games = pd.DataFrame(
        [
            {"team": "A", "opp": "B", "net_epa_pp": 0.2, "plays": 60},
            {"team": "B", "opp": "C", "net_epa_pp": 0.2, "plays": 60},
            {"team": "C", "opp": "A", "net_epa_pp": -0.1, "plays": 60},
        ]
    )

    ratings = compute_sos_adjusted_net_epa(games, lam=5.0)
    assert ratings["A"] > ratings["B"] > ratings["C"]

    sos_faced = compute_sos_faced(games, ratings)
    assert sos_faced.loc["B"] < sos_faced.loc["A"] < sos_faced.loc["C"]


def test_identical_results_yield_zeroish():
    symmetrical = pd.DataFrame(
        [
            {"team": "A", "opp": "B", "net_epa_pp": 0.0, "plays": 40},
            {"team": "B", "opp": "A", "net_epa_pp": 0.0, "plays": 40},
            {"team": "A", "opp": "C", "net_epa_pp": 0.0, "plays": 50},
            {"team": "C", "opp": "A", "net_epa_pp": 0.0, "plays": 50},
        ]
    )

    ratings = compute_sos_adjusted_net_epa(symmetrical)
    assert ratings.abs().max() < 1e-6
