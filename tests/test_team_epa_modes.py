import pandas as pd
import pytest

from scripts.team_epa_modes import apply_epa_mode


def make_df():
    return pd.DataFrame(
        {
            "season": [2024, 2024, 2024, 2024, 2024, 2024],
            "week": [1, 2, 3, 1, 2, 3],
            "team": ["AAA", "AAA", "AAA", "BBB", "BBB", "BBB"],
            "off_epa": [0.1, 0.3, 0.2, -0.2, -0.1, 0.0],
            "def_epa": [0.05, 0.1, 0.2, 0.0, 0.15, 0.25],
            "off_plays": [10, 20, 30, 15, 10, 20],
            "def_plays": [12, 18, 24, 10, 14, 16],
        }
    )


def test_weekly_mode_passthrough():
    df = make_df()
    result = apply_epa_mode(df, mode="weekly")
    pd.testing.assert_series_equal(
        result.loc[result.team == "AAA", "off_epa_mode"].reset_index(drop=True),
        df.loc[df.team == "AAA", "off_epa"].reset_index(drop=True),
        check_names=False,
    )
    pd.testing.assert_series_equal(
        result.loc[result.team == "AAA", "def_epa_mode"].reset_index(drop=True),
        df.loc[df.team == "AAA", "def_epa"].reset_index(drop=True),
        check_names=False,
    )
    expected_net = result["off_epa_mode"] + result["def_epa_mode"]
    pd.testing.assert_series_equal(result["net_epa_mode"], expected_net, check_names=False)


def test_season_to_date_average_unweighted():
    df = pd.DataFrame(
        {
            "season": [2023, 2023, 2023],
            "week": [1, 2, 3],
            "team": ["AAA"] * 3,
            "off_epa": [0.0, 0.5, 1.0],
            "def_epa": [0.3, 0.3, 0.3],
        }
    )
    result = apply_epa_mode(df, mode="season_to_date_avg")
    assert result["off_epa_mode"].round(4).tolist() == [0.0, 0.25, 0.5]
    assert result["def_epa_mode"].round(4).tolist() == [0.3, 0.3, 0.3]
    assert result["net_epa_mode"].round(4).tolist() == [0.3, 0.55, 0.8]


def test_season_to_date_average_weighted():
    df = pd.DataFrame(
        {
            "season": [2022, 2022, 2022],
            "week": [1, 2, 3],
            "team": ["AAA"] * 3,
            "off_epa": [0.0, 0.5, 1.0],
            "def_epa": [0.2, 0.2, 0.2],
            "off_plays": [1, 3, 6],
            "def_plays": [2, 2, 2],
        }
    )
    result = apply_epa_mode(df, mode="season_to_date_avg")
    # Weighted offense average: (0*1 + 0.5*3 + 1.0*6) / (1+3+6) = 0.75
    assert result["off_epa_mode"].iloc[-1] == pytest.approx(0.75, rel=1e-3)
    # Defense uses constant value so weighted and unweighted are the same
    assert result["def_epa_mode"].round(4).tolist() == [0.2, 0.2, 0.2]


def test_weighted_average_ignores_missing_values():
    df = pd.DataFrame(
        {
            "season": [2025, 2025, 2025],
            "week": [1, 2, 3],
            "team": ["AAA"] * 3,
            "off_epa": [0.1, pd.NA, 0.3],
            "def_epa": [0.0, 0.0, 0.0],
            "off_plays": [10, 20, 30],
            "def_plays": [5, 5, 5],
        }
    )
    result = apply_epa_mode(df, mode="season_to_date_avg")
    # The second week's missing value should not add its weight to the running denominator.
    assert result["off_epa_mode"].tolist() == [0.1, 0.1, 0.25]


def test_trailing_average_window_three():
    df = pd.DataFrame(
        {
            "season": [2021, 2021, 2021, 2021],
            "week": [1, 2, 3, 4],
            "team": ["AAA"] * 4,
            "off_epa": [1.0, 2.0, 3.0, 4.0],
            "def_epa": [0.0, 0.5, 1.0, 1.5],
        }
    )
    result = apply_epa_mode(df, mode="trailing_avg", window=3)
    assert result["off_epa_mode"].tolist() == [1.0, 1.5, 2.0, 3.0]
    assert result["def_epa_mode"].round(4).tolist() == [0.0, 0.25, 0.5, 1.0]
    assert result["net_epa_mode"].round(4).tolist() == [1.0, 1.75, 2.5, 4.0]


def test_grouping_separated_by_team_and_season():
    df = pd.DataFrame(
        {
            "season": [2020, 2020, 2021, 2021],
            "week": [1, 2, 1, 2],
            "team": ["AAA", "AAA", "AAA", "AAA"],
            "off_epa": [0.1, 0.3, 1.0, 2.0],
            "def_epa": [0.2, 0.4, 0.5, 1.5],
        }
    )
    result = apply_epa_mode(df, mode="season_to_date_avg")
    season_2020 = result[result.season == 2020]
    season_2021 = result[result.season == 2021]
    assert season_2020["off_epa_mode"].tolist() == [0.1, 0.2]
    assert season_2021["off_epa_mode"].tolist() == [1.0, 1.5]


