from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Optional

from .plot_epa_scatter import REPO_ROOT, load_team_epa


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a static HTML page that displays the EPA scatter chart for a "
            "season and week range using the SQLite-backed cache."
        )
    )
    parser.add_argument("--season", type=int, required=True, help="Season year (e.g., 2025)")
    parser.add_argument("--week-start", type=int, default=None, dest="week_start")
    parser.add_argument("--week-end", type=int, default=None, dest="week_end")
    parser.add_argument(
        "--chart",
        type=str,
        default=str(REPO_ROOT / "site" / "epa_scatter.png"),
        help="Path to the generated chart PNG",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(REPO_ROOT / "site"),
        help="Directory where index.html and assets will be written",
    )
    return parser.parse_args()


def _format_week_label(start: Optional[int], end: Optional[int]) -> str:
    if start and end:
        if start == end:
            return f"Week {end}"
        return f"Weeks {start}–{end}"
    return "Season to date"


def build_page(
    season: int,
    week_start: Optional[int],
    week_end: Optional[int],
    chart_path: Path,
    output_dir: Path,
) -> None:
    df = load_team_epa(season, week_start=week_start, week_end=week_end)
    resolved_start = df.attrs.get("week_start") or week_start
    resolved_end = df.attrs.get("week_end") or week_end
    week_label = _format_week_label(resolved_start, resolved_end)

    chart_path = chart_path.resolve()
    if not chart_path.exists():
        raise FileNotFoundError(f"Chart image not found: {chart_path}")

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    chart_dest = output_dir / chart_path.name
    if chart_dest.resolve() != chart_path:
        chart_dest.write_bytes(chart_path.read_bytes())

    generated_at = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    html = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>NFL EPA Explorer — {season}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem auto; max-width: 960px; }}
    h1 {{ margin-bottom: 0.2rem; }}
    .meta {{ color: #444; margin-top: 0; }}
    img {{ max-width: 100%; height: auto; border: 1px solid #ddd; }}
  </style>
</head>
<body>
  <h1>NFL Offense vs Defense Efficiency (EPA/play)</h1>
  <p class=\"meta\">Season {season} · {week_label} · Generated {generated_at}</p>
  <p>This chart is rendered from the SQLite cache shipped with the repository. For interactive
     week selection, run the Flask app locally (<code>python app.py</code>).</p>
  <img src=\"{chart_dest.name}\" alt=\"EPA scatter chart for season {season}\">
</body>
</html>
"""
    (output_dir / "index.html").write_text(html, encoding="utf-8")


def main() -> None:
    args = parse_args()
    chart_path = Path(args.chart)
    if not chart_path.is_absolute():
        chart_path = (REPO_ROOT / chart_path).resolve()

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = (REPO_ROOT / output_dir).resolve()

    build_page(args.season, args.week_start, args.week_end, chart_path, output_dir)
    print(f"Static site written to {output_dir}")


if __name__ == "__main__":
    main()
