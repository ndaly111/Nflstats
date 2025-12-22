# NFL EPA explorer (static)

This repository powers a static GitHub Pages site that renders an offense vs.
defense EPA scatter plot directly from a JSON file. No Flask server is needed
once the data is bundled.

## Update the data using GitHub Actions (no local runs needed)

1. **Seed database** (one-time backfill): Run the "Seed database" workflow from
the Actions tab. It restores the latest cached `nflstats.db`, backfills the
season range you specify (defaults to 1999 through the current season), and
uploads the refreshed database as both a cache entry and an artifact.

2. **Refresh in-season data** (scheduled): The "Refresh current season data"
workflow runs automatically at 11:30 UTC on Monday, Tuesday, and Friday during
the season. It restores the cached database, recomputes the latest weekly EPA
snapshots for the current season, and re-caches/uploads the updated database.
You can also run it manually with an optional season override.

3. **Build charts** (publish): The "Build charts" workflow restores the cached
`nflstats.db`, optionally refreshes the current season again, exports the
Chart.js payload to `data/epa_sample.json`, and assembles the static site bundle
with `scripts.prepare_site`. It runs automatically whenever either data workflow
finishes successfully or can be started manually. The companion "Deploy Pages"
workflow publishes the resulting artifact to GitHub Pages.

## Preview locally (optional)

Open `index.html` in your browser (double-click from your file explorer or run
`python -m http.server 8000` and visit `http://localhost:8000`). Use the season
and week range controls to redraw the chart.
