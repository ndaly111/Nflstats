import os

import pandas as pd

from scripts.db_storage import DB_PATH, load_team_epa_from_db, save_team_epa_snapshot
from scripts.epa_od_fetcher import PbpFilters, apply_filters, compute_team_epa, load_pbp_pandas
from scripts.plot_epa_scatter import REPO_ROOT, load_team_epa, plot_scatter


def _env_int(name: str) -> int | None:
    v = os.getenv(name, "").strip()
    return int(v) if v else None


def _env_float(name: str) -> float | None:
    v = os.getenv(name, "").strip()
    return float(v) if v else None


def _is_standard_filter(filters: PbpFilters) -> bool:
    """Return True when filters represent the standard season-to-date dataset."""

    return (
        filters.week_start is None
        and filters.min_wp is None
        and filters.max_wp is None
        and not filters.include_playoffs
    )


def _week_label(start_week: int, end_week: int) -> str:
    if start_week == end_week:
        return f"Week {end_week}"
    return f"Weeks {start_week}–{end_week}"


def main() -> None:
    # Default to the current 2025 season; override with NFL_SEASON if needed.
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

    standard_filters = _is_standard_filter(filters)
    target_week = filters.week_end
    cached_df = None
    cached_week = None
    if standard_filters:
        cached_df = load_team_epa_from_db(season, week=target_week)
        if cached_df is not None:
            cached_week = cached_df.attrs.get("week", target_week)
            week_desc = f"week {cached_week}" if cached_week else "latest week"
            print(f"Using cached team EPA from database ({week_desc}) at {DB_PATH}")

    if cached_df is None:
        print(
            f"No cached EPA data found for {season} (week {target_week or 'latest'}). "
            "Attempting to download play-by-play data; "
            "this will fail if the season's games are not published yet or if you are offline."
        )
        print(f"Building team EPA for season {season} ...")
        try:
            pbp = load_pbp_pandas(season)
        except Exception as exc:
            raise SystemExit(
                "Could not build team EPA data. If this is a future season with no published play-by-play "
                "data yet (e.g., preseason), wait until data is available or point NFL_SEASON to a season "
                "with cached data in ./data."
            ) from exc

        available_weeks = pd.to_numeric(pbp.get("week"), errors="coerce").dropna().astype(int)
        if available_weeks.empty:
            raise SystemExit("Play-by-play data is missing week numbers; cannot build weekly snapshots.")

        latest_week_available = int(available_weeks.max())
        start_week = filters.week_start or 1
        if target_week is None or target_week > latest_week_available:
            if target_week is not None and target_week > latest_week_available:
                print(
                    f"Requested week {target_week} exceeds available data; using latest week "
                    f"{latest_week_available} instead."
                )
            target_week = latest_week_available

        weeks_to_build = [w for w in sorted(set(available_weeks.tolist())) if start_week <= w <= target_week]
        team_epa = None

        for week_num in weeks_to_build:
            week_filters = PbpFilters(
                week_start=filters.week_start,
                week_end=week_num,
                min_wp=filters.min_wp,
                max_wp=filters.max_wp,
                include_playoffs=filters.include_playoffs,
            )
            weekly_epa = compute_team_epa(apply_filters(pbp, week_filters))

            if weekly_epa.empty:
                raise SystemExit(f"Computed empty EPA snapshot for week {week_num}; cannot plot chart.")

            if standard_filters:
                save_team_epa_snapshot(weekly_epa, season, week_num)
                print(f"Stored team EPA for week {week_num} in SQLite database: {DB_PATH}")

            if week_num == target_week:
                team_epa = weekly_epa

        if team_epa is None:
            raise SystemExit(f"Failed to build EPA snapshot for requested week {target_week}.")
        cached_week = target_week
    else:
        team_epa = cached_df

    # Build the EXACT chart your index.html expects: repo-root epa_scatter.png
    print("Generating EPA scatter chart (team squares) ...")
    if standard_filters:
        df = load_team_epa(season, week=cached_week)  # normalize DB-backed data for plotting
    else:
        df = team_epa.set_index("team")
        if cached_week is not None:
            df.attrs["week"] = cached_week
    output_path = REPO_ROOT / "epa_scatter.png"

    inferred_week = df.attrs.get("week")
    week_label = _week_label(filters.week_start or 1, inferred_week) if inferred_week else None

    # NOTE: Defense EPA is already sign-flipped in scripts/epa_od_fetcher.compute_team_epa
    # so higher = better defense. Therefore invert_y should be False.
    plot_scatter(
        df=df,
        week_label=week_label,
        invert_y=False,
        output_path=output_path,
        season=season,
    )

    print(f"Saved chart: {output_path}")
    print("DONE ✅")


if __name__ == "__main__":
    main()
