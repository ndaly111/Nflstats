from __future__ import annotations

import datetime
from io import BytesIO
from typing import Optional

from flask import Flask, abort, make_response, render_template_string, request, send_file, url_for

from scripts.db_storage import DB_PATH, get_cached_weeks
from scripts.plot_epa_scatter import TEAM_DISPLAY_NAMES, load_team_epa, plot_scatter

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
      .table-wrapper { margin-top: 1.5rem; }
      table { border-collapse: collapse; width: 100%; }
      th, td { padding: 0.5rem; border: 1px solid #ddd; text-align: left; }
      th { cursor: pointer; background-color: #f4f4f4; user-select: none; }
      th.sorted-asc::after { content: " \2191"; }
      th.sorted-desc::after { content: " \2193"; }
      tbody tr:nth-child(odd) { background-color: #fbfbfb; }
      tbody tr:nth-child(even) { background-color: #f1f1f1; }
      .table-note { margin: 0.3rem 0 0.6rem; color: #444; font-size: 0.95rem; }
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
      {% for wk in week_options %}
        <option value="{{ wk.value }}" {% if wk.value == week_start %}selected{% endif %}>{{ wk.label }}</option>
      {% endfor %}
    </select>

    <label for="week_end">Week end</label>
    <select name="week_end" id="week_end">
      {% for wk in week_options %}
        <option value="{{ wk.value }}" {% if wk.value == week_end %}selected{% endif %}>{{ wk.label }}</option>
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
    {% if table_rows %}
      <div class="table-wrapper">
        <h2>EPA/play table</h2>
        <p class="table-note">Click any column header to sort. Values match the chart above.</p>
        <table id="epa-table">
          <thead>
            <tr>
              <th data-type="string">Team</th>
              <th data-type="number">Combined EPA/play</th>
              <th data-type="number">Offense EPA/play</th>
              <th data-type="number">Defense EPA/play</th>
            </tr>
          </thead>
          <tbody>
            {% for row in table_rows %}
              <tr>
                <td data-value="{{ row.team }}">{{ row.display_name }} ({{ row.team }})</td>
                <td data-value="{{ "%.6f"|format(row.combined) }}">{{ "%.3f"|format(row.combined) }}</td>
                <td data-value="{{ "%.6f"|format(row.offense) }}">{{ "%.3f"|format(row.offense) }}</td>
                <td data-value="{{ "%.6f"|format(row.defense) }}">{{ "%.3f"|format(row.defense) }}</td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    {% endif %}
  {% endif %}
  <script>
    (function() {
      const table = document.getElementById('epa-table');
      if (!table) return;

      const tbody = table.querySelector('tbody');
      const headers = table.querySelectorAll('th');
      const sortState = { column: null, direction: 'asc' };

      const getCellValue = (cell, type) => {
        const raw = cell.dataset.value ?? cell.textContent.trim();
        if (type === 'number') {
          const parsed = parseFloat(raw);
          return Number.isNaN(parsed) ? -Infinity : parsed;
        }
        return raw.toLowerCase();
      };

      const updateHeaderState = (activeHeader, direction) => {
        headers.forEach((header) => header.classList.remove('sorted-asc', 'sorted-desc'));
        activeHeader.classList.add(direction === 'asc' ? 'sorted-asc' : 'sorted-desc');
      };

      headers.forEach((header, index) => {
        header.addEventListener('click', () => {
          const type = header.dataset.type || 'string';
          const isSameColumn = sortState.column === index;
          sortState.direction = isSameColumn && sortState.direction === 'asc' ? 'desc' : 'asc';
          sortState.column = index;

          const rows = Array.from(tbody.querySelectorAll('tr'));
          rows.sort((a, b) => {
            const aValue = getCellValue(a.children[index], type);
            const bValue = getCellValue(b.children[index], type);

            if (aValue === bValue) return 0;
            if (sortState.direction === 'asc') {
              return aValue > bValue ? 1 : -1;
            }
            return aValue < bValue ? 1 : -1;
          });

          tbody.innerHTML = '';
          rows.forEach((row) => tbody.appendChild(row));
          updateHeaderState(header, sortState.direction);
        });
      });
    })();
  </script>
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


def _format_week_options(weeks: list[int]) -> list[dict[str, int | str]]:
    playoff_labels = ["Super Bowl", "Conference Round", "Divisional Round", "Wild Card Round"]
    total_weeks = len(weeks)
    formatted = []
    for idx, week in enumerate(weeks):
        offset_from_end = total_weeks - 1 - idx
        playoff_label = playoff_labels[offset_from_end] if offset_from_end < len(playoff_labels) else None
        label = playoff_label or f"Week {week}"
        formatted.append({"value": week, "label": label})
    return formatted


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
            week_options=[],
            week_start=None,
            week_end=None,
            chart_url=None,
            table_rows=[],
        )

    week_start = _parse_int(request.args.get("week_start"), weeks[0]) or weeks[0]
    week_end = _parse_int(request.args.get("week_end"), weeks[-1]) or weeks[-1]
    if week_start > week_end:
        week_start, week_end = week_end, week_start

    df = load_team_epa(season, week_start=week_start, week_end=week_end)
    data_for_table = df.dropna(subset=["EPA_off_per_play", "EPA_def_per_play"])
    table_rows = []
    for team, row in data_for_table.sort_index().iterrows():
        table_rows.append(
            {
                "team": team,
                "display_name": TEAM_DISPLAY_NAMES.get(team, team),
                "combined": row["EPA_off_per_play"] + row["EPA_def_per_play"],
                "offense": row["EPA_off_per_play"],
                "defense": row["EPA_def_per_play"],
            }
        )

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
        week_options=_format_week_options(weeks),
        week_start=week_start,
        week_end=week_end,
        chart_url=chart_url,
        table_rows=table_rows,
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
