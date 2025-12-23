# NFL EPA explorer (static)

This repository powers a static GitHub Pages site that renders an offense vs.
defense EPA scatter plot directly from a JSON file. No Flask server is needed
once the data is bundled.

## Update the data using GitHub Actions (no local runs needed)

Use the **"Update EPA data"** workflow. It runs automatically once per week and
can also be triggered manually with two modes:

- `update_current` (default): refreshes the in-progress NFL season (January–August
  runs target the previous calendar year).
- `backfill_season`: rebuilds a specific season passed via the `season` input.

Each run downloads play-by-play data with `nflreadpy`, aggregates weekly team
EPA into `data/epa.sqlite`, exports the JSON consumed by the static chart to
`data/epa_sample.json`, and commits the updated artifacts back to the
repository.

Make sure GitHub Pages is configured to **Deploy from a branch** (root folder)
so the latest `index.html` and `data/epa_sample.json` are served directly from
the repository.

### Run the update locally

```bash
python -m scripts.fetch_epa --season 2024 --db data/epa.sqlite --include-playoffs
python -m scripts.export_epa_json --db data/epa.sqlite --output data/epa_sample.json
```

Swap in the season you need, then open `index.html` to see the refreshed data.

## Preview locally (optional)

Open `index.html` in your browser (double-click from your file explorer or run
`python -m http.server 8000` and visit `http://localhost:8000`). Use the season
and week range controls to redraw the chart.
