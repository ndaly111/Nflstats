"""Export cached team EPA to the static JSON format used by index.html.

Run this after populating ``data/epa.sqlite`` with ``scripts.fetch_epa``. The
exported payload is consumed directly by GitHub Pages (or any static host) so
the browser can render the chart without touching SQLite.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
import sqlite3
from pathlib import Path
from typing import Iterable

from scripts.db_storage import DB_PATH, init_db


def collect_seasons(conn: sqlite3.Connection, seasons: Iterable[int] | None) -> list[int]:
    if seasons:
        return sorted({int(s) for s in seasons})
    rows = conn.execute("SELECT DISTINCT season FROM team_epa_weekly ORDER BY season").fetchall()
    return [int(row[0]) for row in rows]


def fetch_season_payload(conn: sqlite3.Connection, season: int) -> dict | None:
    rows = conn.execute(
        """
        SELECT team, week, off_epa_sum, off_plays, def_epa_sum, def_plays
        FROM team_epa_weekly
        WHERE season = ?
        ORDER BY week, team
        """,
        (season,),
    ).fetchall()
    if not rows:
        return None

    weeks: list[int] = []
    teams: dict[str, dict[int, dict[str, float | int]]] = {}

    for team, week, off_sum, off_plays, def_sum, def_plays in rows:
        if week not in weeks:
            weeks.append(int(week))
        off_play_count = int(off_plays)
        def_play_count = int(def_plays)
        off_value = float(off_sum) / off_play_count if off_play_count else None
        def_value = float(def_sum) / def_play_count if def_play_count else None
        week_payload = {}
        if off_value is not None:
            week_payload["off"] = off_value
            week_payload["off_plays"] = off_play_count
        if def_value is not None:
            week_payload["def"] = def_value
            week_payload["def_plays"] = def_play_count
        teams.setdefault(team, {})[int(week)] = week_payload

    game_rows = conn.execute(
        """
        SELECT
            game_id, week, team, opp,
            off_epa_pp, def_epa_pp,
            off_plays, def_plays,
            points_for, points_against,
            net_epa_pp, plays
        FROM team_epa_games
        WHERE season = ?
        ORDER BY week, game_id, team
        """,
        (season,),
    ).fetchall()

    return {
        "weeks": sorted(weeks),
        "teams": [
            {
                "team": team,
                "weeks": {str(week): payload for week, payload in sorted(weeks_data.items())},
            }
            for team, weeks_data in sorted(teams.items())
        ],
        "games": [
            {
                "game_id": row[0],
                "week": int(row[1]),
                "team": row[2],
                "opp": row[3],
                "off_epa_pp": float(row[4]),
                "def_epa_pp": float(row[5]),
                "off_plays": int(row[6]),
                "def_plays": int(row[7]),
                "points_for": int(row[8]),
                "points_against": int(row[9]),
                "net_epa_pp": float(row[10]),
                "plays": int(row[11]),
            }
            for row in game_rows
        ],
    }


def export_json(db_path: Path, output_path: Path, seasons: Iterable[int] | None) -> None:
    conn = init_db(db_path)
    try:
        season_keys = collect_seasons(conn, seasons)
        snapshot: dict[str, dict] = {"seasons": {}}
        for season in season_keys:
            payload = fetch_season_payload(conn, season)
            if payload is None:
                continue
            snapshot["seasons"][str(season)] = payload

        snapshot["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        sha = os.getenv("GITHUB_SHA")
        if sha:
            snapshot["git_sha"] = sha
    finally:
        conn.close()

    if not snapshot["seasons"]:
        raise SystemExit("No season data found in the database. Did you run scripts.fetch_epa?")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, indent=2)
        fh.write("\n")
    print(f"Wrote {output_path} with {len(snapshot['seasons'])} season(s)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", type=Path, default=DB_PATH, help="Path to SQLite database (default: data/epa.sqlite)",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/epa.json"),
        help="Where to write the Chart.js-friendly JSON payload",
    )
    parser.add_argument(
        "--season", "--seasons", nargs="*", type=int,
        help="Optional season years to export (defaults to all seasons in the DB)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    export_json(args.db, args.output, args.season)
