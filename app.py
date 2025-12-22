from __future__ import annotations

import datetime
from io import BytesIO
from typing import Optional

from flask import Flask, abort, make_response, render_template_string, request, send_file, url_for

from scripts.db_storage import DB_PATH, get_cached_weeks
from scripts.plot_epa_scatter import load_team_epa, plot_scatter

app = Flask(__name__)

PAGE_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>NFL EPA Explorer</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 2rem auto; max-width: 960px; }
    form { margin-bottom: 1rem; padding: 1rem; border: 1px solid #ddd; border-radius: 6px; }
    label { display: block; margin: 0.5rem 0 0.2rem; font-weight: bold; }
    input, select { padding: 0.4rem; }
    .chart { text-align: center; margin-top: 1rem; }
    .notice { color: #b32d00; }
  </style>
</head>
<body>
  <h1>NFL Offense vs Defense Efficiency (EPA/play)</h1>
  <p>Charts are rendered directly from the SQLite cache at <code>{{ db_path }}</code>.</p>
  <form method="get" action="/">
    <label for="season">Season</label>
    <input type="number" name="season" id="season" value="{{ season }}" min="2000" max="2100" required>

    <label for="week_start">Week start</label>
    <select name="week_start" id="week_start">
      {% for wk in weeks %}
        <option value="{{ wk }}" {% if wk == week_start %}selected{% endif %}>Week {{ wk }}</option>
      {% endfor %}
    </select>

    <label for="week_end">Week end</label>
    <select name="week_end" id="week_end">
      {% for wk in weeks %}
        <option value="{{ wk }}" {% if wk == week_end %}selected{% endif %}>Week {{ wk }}</option>
      {% endfor %}
    </select>

    <div style="margin-top:0.5rem;">
      <button type="submit">Update chart</button>
    </div>
  </form>

  {% if not weeks %}
    <p class="notice">No cached EPA snapshots found for {{ season }}. Run the fetch script to populate the database.</p>
  {% else %}
    <div class="chart">
      <img src="{{ chart_url }}" alt="EPA scatter plot" style="max-width: 100%; height: auto;">
    </div>
  {% endif %}
</body>
</html>
"""


def _parse_int(arg: str, default: Optional[int]) -> Optional[int]:
    if arg is None or arg == "":
        return default
    try:
        return int(arg)
    except ValueError:
        return default


@app.route("/")
def index() -> str:
    season = _parse_int(request.args.get("season"), datetime.date.today().year)
    weeks = get_cached_weeks(season)
    if not weeks:
        return render_template_string(
            PAGE_TEMPLATE,
            db_path=DB_PATH,
            season=season,
            weeks=[],
            week_start=None,
            week_end=None,
            chart_url=None,
        )

    week_start = _parse_int(request.args.get("week_start"), weeks[0]) or weeks[0]
    week_end = _parse_int(request.args.get("week_end"), weeks[-1]) or weeks[-1]
    if week_start > week_end:
        week_start, week_end = week_end, week_start

    chart_url = url_for(
        "chart",
        season=season,
        week_start=week_start,
        week_end=week_end,
        cachebuster=datetime.datetime.utcnow().timestamp(),
    )

    return render_template_string(
        PAGE_TEMPLATE,
        db_path=DB_PATH,
        season=season,
        weeks=weeks,
        week_start=week_start,
        week_end=week_end,
        chart_url=chart_url,
    )


@app.route("/chart.png")
def chart():
    season = request.args.get("season", type=int)
    week_start = request.args.get("week_start", type=int)
    week_end = request.args.get("week_end", type=int)

    if season is None:
        abort(make_response({"error": "Missing required season"}, 400))

    df = load_team_epa(season, week_start=week_start, week_end=week_end)
    start = df.attrs.get("week_start") or week_start
    end = df.attrs.get("week_end") or week_end
    week_label = None
    if start and end:
        week_label = f"Week {end}" if start == end else f"Weeks {start}–{end}"

    buffer = BytesIO()
    plot_scatter(df, week_label, invert_y=False, output=buffer, season=season)
    buffer.seek(0)

    return send_file(buffer, mimetype="image/png")


if __name__ == "__main__":
    app.run(debug=True)
