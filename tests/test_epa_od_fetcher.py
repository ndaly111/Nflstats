"""Tests for scripts.epa_od_fetcher.

Skipped automatically when nflreadpy is not installed (CI without network).
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

pytest.importorskip("nflreadpy")
from scripts.epa_od_fetcher import compute_team_game_epa  # noqa: E402


def test_sentinel_without_scores():
    """Missing score columns should produce -1 sentinel values."""
    pbp = pd.DataFrame([
        {"game_id": "g1", "posteam": "AAA", "defteam": "BBB", "epa": 0.1},
        {"game_id": "g1", "posteam": "BBB", "defteam": "AAA", "epa": -0.2},
    ])
    result = compute_team_game_epa(pbp, week=1)
    assert set(result["points_for"].unique()) == {-1}
    assert set(result["points_against"].unique()) == {-1}


def test_scores_from_running_totals():
    """Score columns should be picked up from the last play of each game."""
    pbp = pd.DataFrame([
        {
            "game_id": "g2", "posteam": "AAA", "defteam": "BBB", "epa": 0.3,
            "home_team": "AAA", "away_team": "BBB",
            "total_home_score": 7, "total_away_score": 3,
        },
        {
            "game_id": "g2", "posteam": "BBB", "defteam": "AAA", "epa": -0.1,
            "home_team": "AAA", "away_team": "BBB",
            "total_home_score": 14, "total_away_score": 10,
        },
    ])
    result = compute_team_game_epa(pbp, week=2)
    team_points = dict(zip(result["team"], result["points_for"]))
    opp_points = dict(zip(result["team"], result["points_against"]))
    assert team_points["AAA"] == 14
    assert opp_points["AAA"] == 10
    assert team_points["BBB"] == 10
    assert opp_points["BBB"] == 14
