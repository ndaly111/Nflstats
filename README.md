# NFL EPA explorer (static)

This repository powers a static GitHub Pages site that renders an offense vs.
defense EPA scatter plot directly from a JSON file. No Flask server is needed
once the data is bundled.

## How to build/update the chart data

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
2. **Fetch EPA snapshots into SQLite**
   ```bash
   python -m scripts.fetch_epa --season 2024
   # add --week-start / --week-end to limit the window if desired
   ```
   This downloads play-by-play data via `nflreadpy` and writes per-week team EPA
   into `nflstats.db`.
3. **Export to the static JSON format used by `index.html`**
   ```bash
   python -m scripts.export_epa_json --output data/epa_sample.json
   # optional: restrict which seasons to include
   python -m scripts.export_epa_json --season 2023 2024 --output data/epa_sample.json
   ```
   The file `data/epa_sample.json` is what the Chart.js page reads. Replace the
   committed sample with your freshly exported file to publish new values.

## Preview locally

Open `index.html` in your browser (double-click from your file explorer or run
`python -m http.server 8000` and visit `http://localhost:8000`). Use the season
and week range controls to redraw the chart.

## Deploy on GitHub Pages

Commit your updated `data/epa_sample.json` and push to the `gh-pages` branch
(or enable Pages from `main` depending on your settings). GitHub Pages will
serve `index.html`, which automatically loads the bundled JSON and renders the
interactive chart.
