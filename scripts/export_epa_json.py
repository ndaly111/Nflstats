"""Export cached team EPA to the static JSON format used by index.html.

Run this after populating ``nflstats.db`` with ``scripts.fetch_epa``. The
output JSON mirrors ``data/epa_sample.json`` so it can be dropped into GitHub
Pages (or any static host) for the interactive Chart.js page to consume.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Iterable

from scripts.db_storage import DB_PATH


def collect_seasons(conn: sqlite3.Connection, seasons: Iterable[int] | None) -> list[int]:
    if seasons:
        return sorted({int(s) for s in seasons})
    rows = conn.execute("SELECT DISTINCT season FROM team_epa_weekly ORDER BY season").fetchall()
    return [int(row[0]) for row in rows]


def fetch_season_payload(conn: sqlite3.Connection, season: int) -> dict | None:
    rows = conn.execute(
        """
        SELECT team, week, EPA_off_per_play, EPA_def_per_play
        FROM team_epa_weekly
        WHERE season = ?
        ORDER BY week, team
        """,
        (season,),
    ).fetchall()
    if not rows:
        return None

    weeks: list[int] = []
    teams: dict[str, dict[int, dict[str, float]]] = {}

    for team, week, off, deff in rows:
        if week not in weeks:
            weeks.append(int(week))
        teams.setdefault(team, {})[int(week)] = {"off": float(off), "def": float(deff)}

    payload = {
        "weeks": weeks,
        "teams": [
            {"team": team, "weeks": weeks_data}
            for team, weeks_data in sorted(teams.items())
        ],
    }
    return payload


def export_json(db_path: Path, output_path: Path, seasons: Iterable[int] | None) -> None:
    conn = sqlite3.connect(db_path)
    try:
        season_keys = collect_seasons(conn, seasons)
        snapshot: dict[str, dict] = {"seasons": {}}
        for season in season_keys:
            payload = fetch_season_payload(conn, season)
            if payload is None:
                continue
            snapshot["seasons"][str(season)] = payload
    finally:
        conn.close()

    if not snapshot["seasons"]:
        raise SystemExit("No season data found in the database. Did you run scripts.fetch_epa?")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, indent=2)
    print(f"Wrote {output_path} with {len(snapshot['seasons'])} season(s)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", type=Path, default=DB_PATH, help="Path to nflstats SQLite database (default: nflstats.db)",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/epa_sample.json"),
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
