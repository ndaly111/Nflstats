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
DB_PATH = REPO_ROOT / "data" / "epa.sqlite"


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
    off_epa_sum REAL NOT NULL,
    off_plays INTEGER NOT NULL,
    def_epa_sum REAL NOT NULL,
    def_plays INTEGER NOT NULL,
    EPA_off_per_play REAL NOT NULL,
    EPA_def_per_play REAL NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (season, week, team)
);
"""


def init_db(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=DELETE;")
    conn.execute(TEAM_EPA_SCHEMA)
    conn.execute(TEAM_EPA_WEEKLY_SCHEMA)
    _migrate_weekly_schema(conn)
    return conn


def _migrate_weekly_schema(conn: sqlite3.Connection) -> None:
    """Add any missing weekly EPA columns for older databases.

    Previous runs may have created ``team_epa_weekly`` without the new
    aggregate columns. SQLite will not modify an existing table when using
    ``CREATE TABLE IF NOT EXISTS``, so we proactively add columns if they are
    missing to keep reruns idempotent.
    """

    cur = conn.execute("PRAGMA table_info(team_epa_weekly)")
    existing_columns = {row[1] for row in cur.fetchall()}
    migrations = [
        ("off_epa_sum", "REAL", "0"),
        ("off_plays", "INTEGER", "0"),
        ("def_epa_sum", "REAL", "0"),
        ("def_plays", "INTEGER", "0"),
        ("EPA_off_per_play", "REAL", "0"),
        ("EPA_def_per_play", "REAL", "0"),
        ("updated_at", "TEXT", "''"),
    ]

    for name, col_type, default in migrations:
        if name not in existing_columns:
            conn.execute(
                f"ALTER TABLE team_epa_weekly ADD COLUMN {name} {col_type} "
                f"NOT NULL DEFAULT {default};"
            )


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
    returned. For week ranges, EPA values are weighted by play counts to avoid
    biasing toward short samples.
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
        SELECT team, week, off_epa_sum, off_plays, def_epa_sum, def_plays
        FROM team_epa_weekly
        WHERE season = ? AND week BETWEEN ? AND ?
        ORDER BY week, team
    """
    df = pd.read_sql_query(query, conn, params=(season, target_start, target_end))
    conn.close()
    if df.empty:
        return None

    grouped = (
        df.groupby("team", as_index=False)[["off_epa_sum", "off_plays", "def_epa_sum", "def_plays"]]
        .sum()
        .sort_values("team")
        .reset_index(drop=True)
    )

    grouped["EPA_off_per_play"] = grouped.apply(
        lambda row: row["off_epa_sum"] / row["off_plays"] if row["off_plays"] else float("nan"),
        axis=1,
    )
    grouped["EPA_def_per_play"] = grouped.apply(
        lambda row: row["def_epa_sum"] / row["def_plays"] if row["def_plays"] else float("nan"),
        axis=1,
    )
    grouped = grouped.dropna(subset=["EPA_off_per_play", "EPA_def_per_play"]).reset_index(drop=True)

    grouped.attrs["week_start"] = int(target_start)
    grouped.attrs["week_end"] = int(target_end)
    if target_start == target_end:
        grouped.attrs["week"] = int(target_end)

    return grouped[["team", "EPA_off_per_play", "EPA_def_per_play"]]


def save_team_epa_snapshot(
    df: pd.DataFrame, season: int, week: int, db_path: Path | str = DB_PATH
) -> None:
    """Persist a per-week EPA snapshot for a season."""

    required = {"team", "off_epa_sum", "off_plays", "def_epa_sum", "def_plays"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Team EPA dataframe missing columns required for DB storage: {sorted(missing)}"
        )

    df_to_write = df[list(required)].copy()
    df_to_write["EPA_off_per_play"] = df_to_write["off_epa_sum"] / df_to_write["off_plays"]
    df_to_write["EPA_def_per_play"] = df_to_write["def_epa_sum"] / df_to_write["def_plays"]
    df_to_write["season"] = season
    df_to_write["week"] = week

    conn = init_db(db_path)
    with conn:
        conn.executemany(
            """
            INSERT INTO team_epa_weekly (
                season, week, team,
                off_epa_sum, off_plays, def_epa_sum, def_plays,
                EPA_off_per_play, EPA_def_per_play
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(season, week, team) DO UPDATE SET
                off_epa_sum=excluded.off_epa_sum,
                off_plays=excluded.off_plays,
                def_epa_sum=excluded.def_epa_sum,
                def_plays=excluded.def_plays,
                EPA_off_per_play=excluded.EPA_off_per_play,
                EPA_def_per_play=excluded.EPA_def_per_play,
                updated_at=strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
            """,
            [
                (
                    season,
                    week,
                    row.team,
                    float(row.off_epa_sum),
                    int(row.off_plays),
                    float(row.def_epa_sum),
                    int(row.def_plays),
                    float(row.off_epa_sum) / float(row.off_plays),
                    float(row.def_epa_sum) / float(row.def_plays),
                )
                for row in df_to_write.itertuples(index=False)
            ],
        )
    conn.close()
