"""Export per-player weekly EPA to one compact JSON file per season.

Split by season on purpose: the drill-down only ever shows one season at a time,
so a page fetches ~300 KB instead of the ~9 MB every season would weigh together.
Written without indentation for the same reason -- this file is read by code, not
by people.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .db_storage import DB_PATH

DEFAULT_OUTDIR = Path(__file__).resolve().parents[1] / "data" / "players"


def available_seasons(conn: sqlite3.Connection) -> list[int]:
    rows = conn.execute("SELECT DISTINCT season FROM player_epa_weekly ORDER BY season").fetchall()
    return [int(r[0]) for r in rows]


def build_season_payload(conn: sqlite3.Connection, season: int) -> dict:
    """Shape: weeks -> team -> list of players, keyed for the drill-down's lookup."""
    rows = conn.execute(
        """
        SELECT week, team, player_id, player_name, role, epa_sum, plays
        FROM player_epa_weekly
        WHERE season = ?
        ORDER BY week, team, role, epa_sum DESC
        """,
        (season,),
    ).fetchall()

    weeks: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for week, team, player_id, name, role, epa_sum, plays in rows:
        weeks[str(int(week))][str(team)].append(
            {
                "i": str(player_id),
                "n": str(name),
                "r": str(role),
                "e": round(float(epa_sum), 4),
                "p": int(plays),
            }
        )

    payload = {
        "season": season,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "weeks": {w: dict(teams) for w, teams in weeks.items()},
    }
    sha = os.getenv("GITHUB_SHA")
    if sha:
        payload["git_sha"] = sha
    return payload


def export(db_path: Path, outdir: Path, seasons: list[int] | None) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        targets = seasons or available_seasons(conn)
        if not targets:
            raise SystemExit(
                "No player data found in the database. Did you run scripts.fetch_epa?"
            )
        outdir.mkdir(parents=True, exist_ok=True)
        written = 0
        for season in targets:
            payload = build_season_payload(conn, season)
            if not payload["weeks"]:
                print(f"Skipping {season}: no player rows")
                continue
            path = outdir / f"{season}.json"
            with path.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, separators=(",", ":"))
                fh.write("\n")
            written += 1
            print(f"Wrote {path} ({path.stat().st_size / 1e6:.2f} MB)")

        index = outdir / "index.json"
        with index.open("w", encoding="utf-8") as fh:
            json.dump({"seasons": sorted(available_seasons(conn))}, fh, separators=(",", ":"))
            fh.write("\n")
        print(f"Wrote {index} covering {written} season file(s)")
    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH, help="Path to SQLite cache")
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR, help="Directory for per-season files")
    parser.add_argument(
        "--season", type=int, action="append", dest="seasons",
        help="Export only this season (repeatable); defaults to every season present",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    export(args.db, args.outdir, args.seasons)


if __name__ == "__main__":
    main()
