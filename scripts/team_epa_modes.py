"""Transform weekly team EPA data across viewing modes.

The functions here operate on the weekly-level aggregates stored in
``team_epa_weekly`` and exported to ``data/epa.json``. Defensive EPA values are
already oriented such that higher is better, so no sign flipping occurs.
"""
from __future__ import annotations

import pandas as pd

REQUIRED_BASE_COLUMNS = {"season", "week", "team"}


def _coerce_numeric(values: pd.Series) -> pd.Series:
    return pd.to_numeric(values, errors="coerce")


def _mask_weights(values: pd.Series, weights: pd.Series) -> pd.Series:
    """Mask weights where the corresponding value is missing."""

    weights = weights.fillna(0)
    values = _coerce_numeric(values)
    return weights.where(values.notna(), 0)


def _has_positive_weights(
    df: pd.DataFrame, value_col: str, weight_col: str | None
) -> bool:
    if weight_col is None or weight_col not in df.columns:
        return False
    values = _coerce_numeric(df[value_col])
    weights = _mask_weights(values, df[weight_col])
    return weights.gt(0).any()


def _weighted_expanding_mean(
    df: pd.DataFrame, value_col: str, weight_col: str
) -> pd.Series:
    values = _coerce_numeric(df[value_col])
    weights = _mask_weights(values, df[weight_col])
    numer = (values.fillna(0) * weights).cumsum()
    denom = weights.cumsum()
    denom = denom.replace(0, pd.NA)
    return numer.divide(denom)


def _weighted_rolling_mean(
    df: pd.DataFrame, value_col: str, weight_col: str, window: int
) -> pd.Series:
    values = _coerce_numeric(df[value_col])
    weights = _mask_weights(values, df[weight_col])
    numer = (values.fillna(0) * weights).rolling(window, min_periods=1).sum()
    denom = weights.rolling(window, min_periods=1).sum()
    denom = denom.replace(0, pd.NA)
    return numer.divide(denom)


def _unweighted_expanding_mean(df: pd.DataFrame, value_col: str) -> pd.Series:
    values = _coerce_numeric(df[value_col])
    return values.expanding(min_periods=1).mean()


def _unweighted_rolling_mean(df: pd.DataFrame, value_col: str, window: int) -> pd.Series:
    values = _coerce_numeric(df[value_col])
    return values.rolling(window, min_periods=1).mean()


def _compute_mode_values(
    group: pd.DataFrame,
    value_col: str,
    weight_col: str | None,
    mode: str,
    window: int,
) -> pd.Series:
    has_weights = _has_positive_weights(group, value_col, weight_col)

    if mode == "weekly":
        return group[value_col]

    if mode == "season_to_date_avg":
        if has_weights:
            return _weighted_expanding_mean(group, value_col, weight_col)  # type: ignore[arg-type]
        return _unweighted_expanding_mean(group, value_col)

    if mode == "trailing_avg":
        if has_weights:
            return _weighted_rolling_mean(group, value_col, weight_col, window)  # type: ignore[arg-type]
        return _unweighted_rolling_mean(group, value_col, window)

    raise ValueError(f"Unsupported EPA mode: {mode}")


def apply_epa_mode(
    df: pd.DataFrame,
    mode: str,
    window: int = 3,
    off_col: str = "off_epa",
    def_col: str = "def_epa",
    off_weight_col: str | None = "off_plays",
    def_weight_col: str | None = "def_plays",
) -> pd.DataFrame:
    """Apply an EPA viewing mode to weekly team data.

    Parameters
    ----------
    df:
        DataFrame with at least ``season``, ``week``, ``team``, ``off_epa``,
        and ``def_epa`` columns. Optional play count columns allow weighting
        for rolling/expanding averages.
    mode:
        One of ``"weekly"``, ``"season_to_date_avg"``, or ``"trailing_avg"``.
    window:
        Rolling window size for trailing averages (default: 3).
    off_col / def_col:
        Column names for offense and defense EPA metrics.
    off_weight_col / def_weight_col:
        Optional play count column names for weighting.

    Returns
    -------
    pd.DataFrame
        Sorted copy of the input with three added columns:
        ``off_epa_mode``, ``def_epa_mode``, and ``net_epa_mode``. The
        ``net`` column always sums offense and defense (defense remains
        higher-is-better).
    """

    required_columns = REQUIRED_BASE_COLUMNS | {off_col, def_col}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"Dataframe missing required columns: {sorted(missing)}")

    if mode not in {"weekly", "season_to_date_avg", "trailing_avg"}:
        raise ValueError(f"Unsupported EPA mode: {mode}")

    if window <= 0:
        raise ValueError("Rolling window must be positive")

    sorted_df = df.sort_values(["season", "team", "week"]).copy()

    def transform(group: pd.DataFrame) -> pd.DataFrame:
        season_val, team_val = group.name
        group = group.sort_values("week").copy()
        group["season"] = season_val
        group["team"] = team_val
        group["off_epa_mode"] = _compute_mode_values(
            group, off_col, off_weight_col, mode, window
        )
        group["def_epa_mode"] = _compute_mode_values(
            group, def_col, def_weight_col, mode, window
        )
        group["net_epa_mode"] = group["off_epa_mode"] + group["def_epa_mode"]
        return group

    grouped = sorted_df.groupby(["season", "team"], group_keys=False)
    try:
        result = grouped.apply(transform, include_groups=False)
    except TypeError:
        result = grouped.apply(transform)

    result = result.reset_index(drop=True)

    return result
