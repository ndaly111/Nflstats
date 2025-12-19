"""Generate an offense vs defense EPA/play logo scatter in one command.

The script mirrors the "team tiers" view by pulling play-by-play data via
``nflreadpy`` when available (falling back to the cached nflfastR CSV),
filtering down to competitive run/pass plays, aggregating EPA/play for offense
and defense, and plotting with team logos.
"""
from __future__ import annotations

import argparse
import inspect
from datetime import datetime
from pathlib import Path
import sys
from typing import Iterable, Optional

import matplotlib.pyplot as plt
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.fetch_epa import compute_team_epa, filter_plays, normalize_team_abbr
from scripts.plot_epa_scatter import (
    add_reference_lines,
    build_titles,
    draw_logos,
    format_axes,
    save_outputs,
)
from sources import download_epa_csv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--season",
        type=int,
        default=None,
        help="Season year to analyze (defaults to current year)",
    )
    parser.add_argument("--week-start", type=int, default=None, help="First regular-season week to include")
    parser.add_argument("--week-end", type=int, default=None, help="Last regular-season week to include")
    parser.add_argument(
        "--wp-min",
        type=float,
        default=0.1,
        help="Minimum in-play win probability to include (0-1). Default mirrors 10%% threshold",
    )
    parser.add_argument(
        "--wp-max",
        type=float,
        default=0.9,
        help="Maximum in-play win probability to include (0-1). Default mirrors 90%% threshold",
    )
    parser.add_argument(
        "--include-playoffs",
        action="store_true",
        help="Include postseason plays when filtering by week",
    )
    parser.add_argument(
        "--down-min",
        type=int,
        default=1,
        help="Lowest down number to keep (defaults to 1)",
    )
    parser.add_argument(
        "--down-max",
        type=int,
        default=4,
        help="Highest down number to keep (defaults to 4)",
    )
    parser.add_argument(
        "--play-types",
        type=str,
        nargs="+",
        default=["run", "pass"],
        help="Play types to include (case-insensitive). Defaults to run/pass",
    )
    parser.add_argument(
        "--logos-dir",
        type=Path,
        default=Path("assets") / "logos",
        help="Directory containing cached 256x256 team logos named <TEAM>.png",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output PNG path (defaults to plots/team_tiers_<season>.png)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Optional path to write the aggregated team EPA data",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Directory used for cached play-by-play downloads when falling back to nflfastR",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Re-download the nflfastR CSV cache when nflreadpy is unavailable",
    )
    parser.add_argument(
        "--invert-y",
        action="store_true",
        default=True,
        help="Invert the defensive EPA axis so better defenses trend upward (default: on)",
    )
    parser.add_argument(
        "--no-invert-y",
        dest="invert_y",
        action="store_false",
        help="Disable defensive axis inversion",
    )
    parser.add_argument(
        "--week-label",
        type=str,
        default=None,
        help="Optional subtitle label describing the week window",
    )
    return parser.parse_args()


def _call_loader(loader, season: int):
    signature = inspect.signature(loader)
    kwargs: dict[str, object] = {}
    if "seasons" in signature.parameters:
        kwargs["seasons"] = [season]
    elif "years" in signature.parameters:
        kwargs["years"] = [season]
    elif "season" in signature.parameters:
        kwargs["season"] = season
    return loader(**kwargs) if kwargs else loader(season)


def load_play_by_play(season: int, cache_dir: Path, force_download: bool = False) -> pd.DataFrame:
    """Load play-by-play data using nflreadpy when available.

    The function attempts to pull through nflreadpy first to stay aligned with
    nflverse's supported Python loader. If that fails (missing dependency or
    API changes), it falls back to the cached nflfastR CSV download.
    """

    try:
        import nflreadpy as nfl

        loader = next(
            (
                getattr(nfl, name)
                for name in ("load_pbp_data", "load_pbp", "load_pbp_data_pq")
                if hasattr(nfl, name)
            ),
            None,
        )
        if loader is None:
            print("nflreadpy is installed but no play-by-play loader was found; using cached CSV instead.")
        else:
            try:
                return _call_loader(loader, season)
            except Exception as exc:  # pragma: no cover - defensive path
                print(f"nflreadpy failed to load play-by-play data ({exc}); falling back to cached CSV.")
    except ImportError:
        print("nflreadpy not installed; using cached nflfastR CSV.")

    cache_dir.mkdir(parents=True, exist_ok=True)
    csv_path = cache_dir / f"play_by_play_{season}.csv.gz"
    if not csv_path.exists() or force_download:
        print(f"Downloading play-by-play data for {season} to {csv_path}...")
        download_epa_csv(season, target_dir=cache_dir)

    return pd.read_csv(csv_path, compression="gzip", low_memory=False)


def restrict_plays(
    df: pd.DataFrame,
    *,
    week_start: Optional[int],
    week_end: Optional[int],
    wp_min: Optional[float],
    wp_max: Optional[float],
    include_playoffs: bool,
    play_types: Iterable[str],
    down_min: Optional[int],
    down_max: Optional[int],
) -> pd.DataFrame:
    filtered = filter_plays(
        df,
        week_start=week_start,
        week_end=week_end,
        min_wp=wp_min,
        max_wp=wp_max,
        include_playoffs=include_playoffs,
    )

    if play_types:
        allowed = {p.lower() for p in play_types}
        if "play_type" in filtered.columns:
            filtered = filtered[filtered["play_type"].astype(str).str.lower().isin(allowed)]

    if "down" in filtered.columns and (down_min is not None or down_max is not None):
        filtered["down"] = pd.to_numeric(filtered.get("down"), errors="coerce")
        start = down_min if down_min is not None else filtered["down"].min()
        end = down_max if down_max is not None else filtered["down"].max()
        filtered = filtered[filtered["down"].between(start, end, inclusive="both")]

    return filtered


def build_week_label(args: argparse.Namespace) -> Optional[str]:
    if args.week_label:
        return args.week_label

    parts = []
    if args.week_start or args.week_end:
        start = args.week_start or 1
        end = args.week_end or "latest"
        parts.append(f"Weeks {start}-{end}")

    wp_window = None
    if args.wp_min is not None or args.wp_max is not None:
        low = args.wp_min if args.wp_min is not None else 0
        high = args.wp_max if args.wp_max is not None else 1
        wp_window = f"win prob {int(low * 100)}-{int(high * 100)}%"
    if wp_window:
        parts.append(wp_window)

    if args.include_playoffs:
        parts.append("including playoffs")

    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]

    return f"{parts[0]} ({'; '.join(parts[1:])})"


def main() -> None:
    args = parse_args()
    season = args.season or datetime.now().year

    pbp = load_play_by_play(season, cache_dir=args.data_dir, force_download=args.force_download)
    pbp["posteam"] = pbp.get("posteam").apply(normalize_team_abbr)
    pbp["defteam"] = pbp.get("defteam").apply(normalize_team_abbr)

    filtered = restrict_plays(
        pbp,
        week_start=args.week_start,
        week_end=args.week_end,
        wp_min=args.wp_min,
        wp_max=args.wp_max,
        include_playoffs=args.include_playoffs,
        play_types=args.play_types,
        down_min=args.down_min,
        down_max=args.down_max,
    )

    team_epa = compute_team_epa(filtered)

    csv_output = args.csv or args.data_dir / f"team_epa_{season}_tiers.csv"
    csv_output.parent.mkdir(parents=True, exist_ok=True)
    team_epa.to_csv(csv_output, index=False)
    print(f"Saved aggregated team EPA to {csv_output}")

    output = args.output or Path("plots") / f"team_tiers_{season}.png"
    output.parent.mkdir(parents=True, exist_ok=True)

    week_label = build_week_label(args)

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.scatter(team_epa["off_epa_per_play"], team_epa["def_epa_per_play"], alpha=0)
    draw_logos(ax, team_epa, args.logos_dir)
    format_axes(ax, invert_y=args.invert_y)
    add_reference_lines(ax, team_epa)
    build_titles(ax, season, week_label)

    save_outputs(fig, output, save_svg=False, save_pdf=False)
    print(f"Saved team tiers plot to {output}")


if __name__ == "__main__":
    main()
