"""SQLite storage for team EPA snapshots.

This module stores per-team EPA snapshots in SQLite so charts can be built from
cached data without touching CSV files. A weekly snapshot table tracks EPA
values for each week of a season so downstream code can render charts for a
specific week or aggregate a range of weeks.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "nflstats.db"


TEAM_EPA_SCHEMA = """
CREATE TABLE IF NOT EXISTS team_epa (
    season INTEGER NOT NULL,
    team TEXT NOT NULL,
    EPA_off_per_play REAL NOT NULL,
    EPA_def_per_play REAL NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (season, team)
);
"""

TEAM_EPA_WEEKLY_SCHEMA = """
CREATE TABLE IF NOT EXISTS team_epa_weekly (
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    team TEXT NOT NULL,
    EPA_off_per_play REAL NOT NULL,
    EPA_def_per_play REAL NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (season, week, team)
);
"""


def init_db(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(TEAM_EPA_SCHEMA)
    conn.execute(TEAM_EPA_WEEKLY_SCHEMA)
    return conn


def get_cached_weeks(season: int, db_path: Path | str = DB_PATH) -> list[int]:
    """Return sorted list of cached week numbers for a season."""

    conn = init_db(db_path)
    rows = conn.execute(
        "SELECT DISTINCT week FROM team_epa_weekly WHERE season = ? ORDER BY week", (season,)
    ).fetchall()
    conn.close()
    return [int(r[0]) for r in rows]


def load_team_epa_from_db(
    season: int,
    week: Optional[int] = None,
    week_start: Optional[int] = None,
    week_end: Optional[int] = None,
    db_path: Path | str = DB_PATH,
) -> Optional[pd.DataFrame]:
    """
    Load team EPA values for a specific week or range of weeks.

    When ``week_start``/``week_end`` are omitted, the latest cached week is
    used. If only ``week`` is provided, the snapshot for that exact week is
    returned. For week ranges, the EPA values are averaged across the selected
    weeks.
    """

    conn = init_db(db_path)
    target_start: Optional[int] = week_start
    target_end: Optional[int] = week_end

    if target_start is None and target_end is None:
        if week is not None:
            target_start = target_end = week
        else:
            row = conn.execute(
                "SELECT MAX(week) FROM team_epa_weekly WHERE season = ?", (season,)
            ).fetchone()
            if row and row[0] is not None:
                target_start = target_end = int(row[0])

    if target_start is None or target_end is None:
        conn.close()
        return None

    query = """
        SELECT team, week, EPA_off_per_play, EPA_def_per_play
        FROM team_epa_weekly
        WHERE season = ? AND week BETWEEN ? AND ?
        ORDER BY week, team
    """
    df = pd.read_sql_query(query, conn, params=(season, target_start, target_end))
    conn.close()
    if df.empty:
        return None

    grouped = (
        df.groupby("team", as_index=False)[["EPA_off_per_play", "EPA_def_per_play"]]
        .mean()
        .sort_values("team")
        .reset_index(drop=True)
    )

    grouped.attrs["week_start"] = int(target_start)
    grouped.attrs["week_end"] = int(target_end)
    if target_start == target_end:
        grouped.attrs["week"] = int(target_end)

    return grouped


def save_team_epa_snapshot(
    df: pd.DataFrame, season: int, week: int, db_path: Path | str = DB_PATH
) -> None:
    """Persist a per-week EPA snapshot for a season."""

    required = {"team", "EPA_off_per_play", "EPA_def_per_play"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Team EPA dataframe missing columns required for DB storage: {sorted(missing)}"
        )

    conn = init_db(db_path)
    with conn:
        conn.execute("DELETE FROM team_epa_weekly WHERE season = ? AND week = ?", (season, week))
        df_to_write = df[["team", "EPA_off_per_play", "EPA_def_per_play"]].copy()
        df_to_write["season"] = season
        df_to_write["week"] = week
        df_to_write.to_sql("team_epa_weekly", conn, if_exists="append", index=False)
    conn.close()
