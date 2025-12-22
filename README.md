# NFL EPA explorer (static)

This repository powers a static GitHub Pages site that renders an offense vs.
defense EPA scatter plot directly from a JSON file. No Flask server is needed
once the data is bundled.

## Update the data using GitHub Actions (no local runs needed)

1. Go to the **Actions** tab in GitHub and run the "Generate EPA chart" workflow
   using **Run workflow**. Choose your season and optional week range. The job
   will:
   - install Python deps
   - fetch weekly EPA snapshots into `nflstats.db`
   - export `site/data/epa_sample.json` (the Chart.js payload)
   - bundle `index.html` + `data/` into a Pages artifact
2. The companion "Deploy Pages" workflow publishes the artifact automatically
   to GitHub Pages when "Generate EPA chart" succeeds. You can also schedule or
   rerun the "Main" workflow for daily refreshes with the default season.

## Preview locally (optional)

Open `index.html` in your browser (double-click from your file explorer or run
`python -m http.server 8000` and visit `http://localhost:8000`). Use the season
and week range controls to redraw the chart.
