import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from scripts import db_storage


def test_migration_converts_legacy_zero_scores(tmp_path):
    db_path = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE team_epa_games (
            season INTEGER NOT NULL,
            week INTEGER NOT NULL,
            game_id TEXT NOT NULL,
            team TEXT NOT NULL,
            opp TEXT NOT NULL,
            off_epa_sum REAL NOT NULL,
            off_plays INTEGER NOT NULL,
            off_epa_pp REAL NOT NULL,
            def_epa_sum REAL NOT NULL,
            def_plays INTEGER NOT NULL,
            def_epa_pp REAL NOT NULL,
            points_for INTEGER NOT NULL DEFAULT 0,
            points_against INTEGER NOT NULL DEFAULT 0,
            net_epa_sum REAL NOT NULL,
            plays INTEGER NOT NULL,
            net_epa_pp REAL NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (season, game_id, team)
        );
        """
    )
    conn.execute(
        """
        INSERT INTO team_epa_games
        (season, week, game_id, team, opp, off_epa_sum, off_plays, off_epa_pp, def_epa_sum, def_plays, def_epa_pp,
         points_for, points_against, net_epa_sum, plays, net_epa_pp, updated_at)
        VALUES (2023, 1, 'g1', 'AAA', 'BBB', 0.0, 10, 0.0, 0.0, 10, 0.0, 0, 0, 0.0, 20, 0.0, '');
        """
    )
    conn.commit()
    conn.close()

    migrated_conn = db_storage.init_db(db_path)
    try:
        row = migrated_conn.execute(
            "SELECT points_for, points_against FROM team_epa_games WHERE game_id = 'g1'"
        ).fetchone()
        assert row == (-1, -1)
    finally:
        migrated_conn.close()
