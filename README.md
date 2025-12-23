# NFL EPA explorer (static)

This repository powers a static GitHub Pages site that renders an offense vs.
defense EPA scatter plot directly from a JSON file. No Flask server is needed
once the data is bundled.

## Update the data using GitHub Actions (no local runs needed)

Use the **"Update EPA data"** workflow. It runs automatically once per week and
can also be triggered manually with three modes:

- `update_current` (default): refreshes the in-progress NFL season (January–August
  runs target the previous calendar year).
- `backfill_season`: rebuilds a specific season passed via the `season` input.
- `backfill_range`: loops from `season_start` to `season_end` (inclusive) to
  rebuild multiple seasons in one run; leave `season_end` blank to stop at the
  current season.

Each run downloads play-by-play data with `nflreadpy`, aggregates weekly team
EPA into `data/epa.sqlite`, exports the JSON consumed by the static chart to
`data/epa_sample.json`, and commits the updated artifacts back to the
repository. The GitHub Actions UI shows **Run workflow** only after the
workflow file exists on the default branch (and you have write access).

## GitHub Pages Settings

Open **Settings → Pages** and select **Deploy from a branch → main → /(root)**
so GitHub Pages serves `index.html` and `data/epa_sample.json` directly from the
repository without an extra build step.

### Run the update locally

```bash
python -m scripts.fetch_epa --season 2024 --db data/epa.sqlite --include-playoffs
python -m scripts.export_epa_json --db data/epa.sqlite --output data/epa_sample.json
python -m http.server 8000
```

Swap in the season you need, then open `index.html` (or visit
`http://localhost:8000`) to see the refreshed data.

### Workflow usage examples

- `update_current`: runs weekly automatically.
- `backfill_season`: run manually once per season (provide `season`).
- `backfill_range`: use shorter ranges to avoid long-running jobs (e.g.,
  `season_start=2000`, `season_end=2004`, then `2005-2009`, and so on) instead
  of attempting a single 2000→current backfill.

## Preview locally (optional)

Open `index.html` in your browser (double-click from your file explorer or run
`python -m http.server 8000` and visit `http://localhost:8000`). Use the season
and week range controls to redraw the chart.
