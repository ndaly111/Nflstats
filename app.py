from __future__ import annotations

import datetime
from io import BytesIO
from typing import Optional

import pandas as pd
from flask import Flask, abort, make_response, render_template_string, request, send_file, url_for

from scripts.db_storage import DB_PATH, get_cached_weeks, load_team_game_epa_from_db
from scripts.plot_epa_scatter import TEAM_DISPLAY_NAMES, load_team_epa, plot_scatter
from scripts.records import compute_records

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
      .raw-value { color: #9ca3af; font-size: 0.9em; margin-left: 0.35rem; }
      .rank-note { color: #6b7280; font-size: 0.9em; margin-left: 0.35rem; }
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

    <label for="metric_mode">EPA view</label>
    <select name="metric_mode" id="metric_mode">
      <option value="raw" {% if metric_mode == 'raw' %}selected{% endif %}>Raw EPA/play</option>
      <option value="sos" {% if metric_mode == 'sos' %}selected{% endif %}>SOS-adjusted EPA/play</option>
    </select>

    {% if metric_mode == 'sos' %}
    <label for="sos_basis">Opponent strength basis</label>
    <select name="sos_basis" id="sos_basis">
      <option value="season_to_date" {% if sos_basis == 'season_to_date' %}selected{% endif %}>Season-to-date (through end week)</option>
      <option value="window_only" {% if sos_basis == 'window_only' %}selected{% endif %}>Selected weeks only</option>
      <option value="full_season" {% if sos_basis == 'full_season' %}selected{% endif %}>Full season (hindsight)</option>
    </select>
    {% else %}
    <input type="hidden" name="sos_basis" value="{{ sos_basis }}">
    {% endif %}

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
        <p class="table-note">Click any column header to sort. Values match the chart above. SOS columns show play-weighted opponent ratings faced (rank #1 = hardest schedule).</p>
        <table id="epa-table">
          <thead>
            <tr>
              <th data-type="string">Team</th>
              <th data-type="number">Record</th>
              <th data-type="number">Win%</th>
              <th data-type="number">Combined EPA/play</th>
              {% if metric_mode == 'sos' %}
              <th data-type="number">SOS faced (opp DEF)</th>
              <th data-type="number">SOS faced (opp OFF)</th>
              {% endif %}
              <th data-type="number">Offense EPA/play</th>
              <th data-type="number">Defense EPA/play</th>
            </tr>
          </thead>
          <tbody>
              {% for row in table_rows %}
              <tr>
                <td data-value="{{ row.team }}">{{ row.display_name }} ({{ row.team }})</td>
                <td data-value="{{ row.win_pct if row.win_pct is not none else '' }}">{{ row.record if row.record else 'N/A' }}</td>
                <td data-value="{{ row.win_pct if row.win_pct is not none else '' }}">{{ row.win_pct is not none and "%.3f"|format(row.win_pct) or 'N/A' }}</td>
                <td data-value="{{ "%.6f"|format(row.combined) }}">{{ "%.3f"|format(row.combined) }}{% if metric_mode == 'sos' %}<span class="raw-value">(raw {{ "%.3f"|format(row.raw_combined) }})</span>{% endif %}</td>
                {% if metric_mode == 'sos' %}
                <td data-value="{{ row.sos_off_faced if row.sos_off_faced is not none else '' }}">
                  {% if row.sos_off_faced is not none %}{{ "%.3f"|format(row.sos_off_faced) }}{% else %}N/A{% endif %}{% if row.sos_off_rank %} <span class="rank-note">(#{{ row.sos_off_rank }})</span>{% endif %}
                </td>
                <td data-value="{{ row.sos_def_faced if row.sos_def_faced is not none else '' }}">
                  {% if row.sos_def_faced is not none %}{{ "%.3f"|format(row.sos_def_faced) }}{% else %}N/A{% endif %}{% if row.sos_def_rank %} <span class="rank-note">(#{{ row.sos_def_rank }})</span>{% endif %}
                </td>
                {% endif %}
                <td data-value="{{ "%.6f"|format(row.offense) }}">{{ "%.3f"|format(row.offense) }}{% if metric_mode == 'sos' %}<span class="raw-value">(raw {{ "%.3f"|format(row.raw_offense) }})</span>{% endif %}</td>
                <td data-value="{{ "%.6f"|format(row.defense) }}">{{ "%.3f"|format(row.defense) }}{% if metric_mode == 'sos' %}<span class="raw-value">(raw {{ "%.3f"|format(row.raw_defense) }})</span>{% endif %}</td>
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


def _regular_season_max(season: int) -> int:
    # NFL moved to 18-week regular season starting 2021 season
    return 18 if season >= 2021 else 17


def _format_week_options(season: int, weeks: list[int]) -> list[dict[str, int | str]]:
    playoff_labels = {
        1: "Wild Card Round",
        2: "Divisional Round",
        3: "Conference Round",
        4: "Super Bowl",
    }
    reg_max = _regular_season_max(season)

    formatted: list[dict[str, int | str]] = []
    for week in weeks:
        label = f"Week {week}"
        if week > reg_max:
            label = playoff_labels.get(week - reg_max, label)
        formatted.append({"value": week, "label": label})
    return formatted


@app.route("/")
def index() -> str:
    season = _parse_int(request.args.get("season"), datetime.date.today().year)
    metric_mode = request.args.get("metric_mode", default="raw")
    if metric_mode not in {"raw", "sos"}:
        metric_mode = "raw"
    sos_basis = request.args.get("sos_basis", default="season_to_date")
    if sos_basis not in {"season_to_date", "window_only", "full_season"}:
        sos_basis = "season_to_date"
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
            metric_mode=metric_mode,
            sos_basis=sos_basis,
            chart_url=None,
            table_rows=[],
        )

    week_start = _parse_int(request.args.get("week_start"), weeks[0]) or weeks[0]
    week_end = _parse_int(request.args.get("week_end"), weeks[-1]) or weeks[-1]
    if week_start > week_end:
        week_start, week_end = week_end, week_start

    df = load_team_epa(
        season,
        week_start=week_start,
        week_end=week_end,
        include_sos=metric_mode == "sos",
        sos_basis=sos_basis,
    )
    game_rows = load_team_game_epa_from_db(season, week_start=week_start, week_end=week_end)
    records_by_team = compute_records(game_rows)
    data_for_table = df.dropna(subset=["EPA_off_per_play", "EPA_def_per_play"])
    sos_off_ranks: dict[str, int] | None = None
    sos_def_ranks: dict[str, int] | None = None
    if metric_mode == "sos":
        if "sos_off_faced" in data_for_table.columns:
            ranked = (
                data_for_table[["sos_off_faced"]]
                .dropna()
                .sort_values("sos_off_faced", ascending=False)
                .reset_index()
                .rename(columns={"index": "team"})
            )
            sos_off_ranks = {str(row.team): idx + 1 for idx, row in ranked.iterrows()}
        if "sos_def_faced" in data_for_table.columns:
            ranked = (
                data_for_table[["sos_def_faced"]]
                .dropna()
                .sort_values("sos_def_faced", ascending=False)
                .reset_index()
                .rename(columns={"index": "team"})
            )
            sos_def_ranks = {str(row.team): idx + 1 for idx, row in ranked.iterrows()}
    table_rows = []
    for team, row in data_for_table.sort_index().iterrows():
        base_off = row["EPA_off_per_play"]
        base_def = row["EPA_def_per_play"]
        base_net = row.get("net_epa_pp", base_off + base_def)

        use_sos = metric_mode == "sos" and {
            "EPA_off_sos_adj",
            "EPA_def_sos_adj",
        }.issubset(row.index)
        offense = row.get("EPA_off_sos_adj", base_off) if use_sos else base_off
        defense = row.get("EPA_def_sos_adj", base_def) if use_sos else base_def
        combined = row.get("net_epa_pp_sos_adj", offense + defense) if use_sos else base_net
        record = records_by_team.get(team)
        table_rows.append(
            {
                "team": team,
                "display_name": TEAM_DISPLAY_NAMES.get(team, team),
                "combined": combined,
                "offense": offense,
                "defense": defense,
                "raw_combined": base_net,
                "raw_offense": base_off,
                "raw_defense": base_def,
                "sos_off_faced": row.get("sos_off_faced"),
                "sos_def_faced": row.get("sos_def_faced"),
                "wins": record.get("wins") if record else None,
                "losses": record.get("losses") if record else None,
                "ties": record.get("ties") if record else None,
                "record": record.get("record") if record else None,
                "win_pct": record.get("win_pct") if record else None,
                "sos_off_rank": sos_off_ranks.get(team) if sos_off_ranks else None,
                "sos_def_rank": sos_def_ranks.get(team) if sos_def_ranks else None,
            }
        )

    chart_url = url_for(
        "chart",
        season=season,
        week_start=week_start,
        week_end=week_end,
        metric_mode=metric_mode,
        sos_basis=sos_basis,
        cachebuster=datetime.datetime.utcnow().timestamp(),
    )

    return render_template_string(
        PAGE_TEMPLATE,
        db_path=DB_PATH,
        season=season,
        weeks=weeks,
        week_options=_format_week_options(season, weeks),
        week_start=week_start,
        week_end=week_end,
        metric_mode=metric_mode,
        sos_basis=sos_basis,
        chart_url=chart_url,
        table_rows=table_rows,
    )


@app.route("/chart.png")
def chart():
    season = request.args.get("season", type=int)
    week_start = request.args.get("week_start", type=int)
    week_end = request.args.get("week_end", type=int)
    metric_mode = request.args.get("metric_mode", default="raw")
    if metric_mode not in {"raw", "sos"}:
        metric_mode = "raw"
    sos_basis = request.args.get("sos_basis", default="season_to_date")
    if sos_basis not in {"season_to_date", "window_only", "full_season"}:
        sos_basis = "season_to_date"

    if season is None:
        abort(make_response({"error": "Missing required season"}, 400))

    df = load_team_epa(
        season,
        week_start=week_start,
        week_end=week_end,
        include_sos=metric_mode == "sos",
        sos_basis=sos_basis,
    )
    start = df.attrs.get("week_start") or week_start
    end = df.attrs.get("week_end") or week_end
    week_label = None
    if start and end:
        week_label = f"Week {end}" if start == end else f"Weeks {start}–{end}"

    buffer = BytesIO()
    plot_scatter(
        df,
        week_label,
        invert_y=False,
        output=buffer,
        season=season,
        metric_mode=metric_mode,
    )
    buffer.seek(0)

    return send_file(buffer, mimetype="image/png")


if __name__ == "__main__":
    app.run(debug=True)
