import os
from pathlib import Path

from scripts.epa_od_fetcher import build_team_epa, PbpFilters
from scripts.plot_epa_scatter import load_team_epa, plot_scatter, REPO_ROOT


def _env_int(name: str) -> int | None:
    v = os.getenv(name, "").strip()
    return int(v) if v else None


def _env_float(name: str) -> float | None:
    v = os.getenv(name, "").strip()
    return float(v) if v else None


def main() -> None:
    # Season (default to 2025 like your current code)
    season_str = os.getenv("NFL_SEASON", "2025").strip()
    try:
        season = int(season_str)
    except ValueError:
        raise SystemExit(f"Invalid NFL_SEASON env var: {season_str!r} (must be an int like 2025)")

    # Optional filters via env vars (all optional)
    filters = PbpFilters(
        week_start=_env_int("WEEK_START"),
        week_end=_env_int("WEEK_END"),
        min_wp=_env_float("MIN_WP"),
        max_wp=_env_float("MAX_WP"),
        include_playoffs=os.getenv("INCLUDE_PLAYOFFS", "").strip().lower() in {"1", "true", "yes"},
    )

    print(f"Building team EPA for season {season} ...")
    team_epa = build_team_epa(season, filters=filters)

    # Save CSV to data/ like your plotting script expects
    data_dir = REPO_ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    out_csv = data_dir / f"team_epa_{season}.csv"
    team_epa.to_csv(out_csv, index=False)
    print(f"Saved CSV: {out_csv}")

    # Build the EXACT chart your index.html expects: repo-root epa_scatter.png
    print("Generating EPA scatter chart (team squares) ...")
    df = load_team_epa(season)  # reads the CSV we just wrote and normalizes columns
    output_path = REPO_ROOT / "epa_scatter.png"

    # NOTE: Defense EPA is already sign-flipped in scripts/epa_od_fetcher.compute_team_epa
    # so higher = better defense. Therefore invert_y should be False.
    plot_scatter(
        df=df,
        week_label=None,
        invert_y=False,
        output_path=output_path,
        season=season,
    )

    print(f"Saved chart: {output_path}")
    print("DONE ✅")


if __name__ == "__main__":
    main()
