import os
from pathlib import Path
from typing import Optional

from scripts.plot_epa_scatter import REPO_ROOT, load_team_epa, plot_scatter


def _env_int(name: str) -> Optional[int]:
    value = os.getenv(name, "").strip()
    return int(value) if value else None


def _week_label(start: int, end: int) -> str:
    if start == end:
        return f"Week {end}"
    return f"Weeks {start}–{end}"


def main() -> None:
    season_str = os.getenv("NFL_SEASON", "2025").strip()
    try:
        season = int(season_str)
    except ValueError:
        raise SystemExit(f"Invalid NFL_SEASON env var: {season_str!r} (must be an int like 2025)")

    week_start = _env_int("WEEK_START")
    week_end = _env_int("WEEK_END")

    df = load_team_epa(season, week_start=week_start, week_end=week_end)
    start = df.attrs.get("week_start") or week_start or 1
    end = df.attrs.get("week_end") or week_end or start

    week_label = _week_label(start, end)

    output_path = REPO_ROOT / "epa_scatter.png"
    plot_scatter(df, week_label, invert_y=False, output=output_path, season=season)

    print(f"Saved chart: {output_path}")
    print("DONE ✅")


if __name__ == "__main__":
    main()
