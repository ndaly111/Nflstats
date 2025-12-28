import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from scripts.records import compute_records
from scripts.epa_od_fetcher import compute_team_game_epa


def test_compute_team_game_epa_uses_sentinel_without_scores():
    pbp = pd.DataFrame(
        [
            {"game_id": "g1", "posteam": "AAA", "defteam": "BBB", "epa": 0.1},
            {"game_id": "g1", "posteam": "BBB", "defteam": "AAA", "epa": -0.2},
        ]
    )

    result = compute_team_game_epa(pbp, week=1)

    assert set(result["points_for"].unique()) == {-1}
    assert set(result["points_against"].unique()) == {-1}


def test_compute_team_game_epa_scores_from_running_totals():
    pbp = pd.DataFrame(
        [
            {
                "game_id": "g2",
                "posteam": "AAA",
                "defteam": "BBB",
                "epa": 0.3,
                "home_team": "AAA",
                "away_team": "BBB",
                "total_home_score": 7,
                "total_away_score": 3,
            },
            {
                "game_id": "g2",
                "posteam": "BBB",
                "defteam": "AAA",
                "epa": -0.1,
                "home_team": "AAA",
                "away_team": "BBB",
                "total_home_score": 14,
                "total_away_score": 10,
            },
        ]
    )

    result = compute_team_game_epa(pbp, week=2)
    team_points = dict(zip(result["team"], result["points_for"]))
    opp_points = dict(zip(result["team"], result["points_against"]))

    assert team_points["AAA"] == 14
    assert opp_points["AAA"] == 10
    assert team_points["BBB"] == 10
    assert opp_points["BBB"] == 14


def test_compute_records_ignores_missing_scores():
    rows = pd.DataFrame(
        [
            {"team": "AAA", "points_for": 10, "points_against": 7},
            {"team": "AAA", "points_for": -1, "points_against": -1},
            {"team": "AAA", "points_for": 3, "points_against": 3},
        ]
    )

    records = compute_records(rows)

    assert records["AAA"]["wins"] == 1
    assert records["AAA"]["losses"] == 0
    assert records["AAA"]["ties"] == 1
    assert records["AAA"]["win_pct"] == (1 + 0.5) / 2
