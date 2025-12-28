# NFL EPA explorer (static)

This repository powers a static GitHub Pages site that renders an offense vs.
defense EPA scatter plot directly from a JSON file. No Flask server is needed
once the data is bundled, and the browser never queries SQLite.

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
EPA into `data/epa.sqlite` (build-time cache), exports the JSON consumed by the
static chart to `data/epa.json`, and commits the updated artifacts back to the
repository. The GitHub Actions UI shows **Run workflow** only after the
workflow file exists on the default branch, you have write access, and Actions
are enabled for the repo.

## GitHub Pages Settings

Open **Settings → Pages** and select **Deploy from a branch → main → /(root)**
so GitHub Pages serves `index.html` and `data/epa.json` directly from the
repository without an extra build step.

### Run the update locally

> **Heads up on network access**
>
> Both the local and GitHub Actions update paths download weekly play-by-play
> parquet files from the `nflverse` releases on GitHub. If your environment
> blocks outbound HTTPS (for example, via a corporate proxy that returns a
> `403` when hitting `https://github.com`), the local commands will fail before
> any SQLite or JSON artifacts are produced. In that case, trigger the
> **Update EPA data** workflow from GitHub instead—Actions runners have internet
> access and will refresh the data even when your local machine cannot.

```bash
python -m scripts.fetch_epa --season 2024 --db data/epa.sqlite --include-playoffs
python -m scripts.export_epa_json --db data/epa.sqlite --output data/epa.json
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

### Manually run a full backfill (2000–2025)

To regenerate every season from 2000 through 2025 in one go:

1. Open **Actions → Update EPA data → Run workflow**.
2. Set `mode` to `backfill_range`.
3. Enter `season_start: 2000` and `season_end: 2025`.

The workflow will iterate through each season, rebuild the SQLite cache, and
export an updated `data/epa.json` covering the full range.

### Trigger the workflow from the CLI

If the **Run workflow** button is hidden in the Actions UI, you can still kick
off the job with the GitHub CLI (requires a token that permits `workflow`
scope, e.g., `GH_TOKEN`):

```bash
./scripts/trigger_update_workflow.sh                          # update_current
./scripts/trigger_update_workflow.sh backfill_season 2023     # specific season
./scripts/trigger_update_workflow.sh backfill_range '' 2000 2024
```

### Trigger the workflow from a GitHub comment (no local shell)

If you have write access but the Actions UI still hides the **Run workflow**
control, comment on any issue or pull request with one of these commands:

- `/update-epa` — runs with the default `update_current` mode on the default
  branch.
- `/update-epa mode=backfill_season season=2023` — rebuilds a specific season.
- `/update-epa mode=backfill_range season_start=2000 season_end=2024` — bulk
  backfill across a range.

Only collaborators/maintainers can trigger runs this way; the bot replies on
the thread to confirm whether it dispatched the workflow or lacked permission.

### Architecture notes

- `data/epa.sqlite` stores cached weekly play-by-play aggregates used during
  workflow or local runs; it is never read by the browser.
- `data/epa.json` is the only runtime dependency for the static page. The
  workflow writes and commits this file alongside the SQLite cache so GitHub
  Pages can serve the freshest numbers.

### SOS-adjusted EPA

- `data/epa.json` now includes a `games` section (two rows per game) with
  plays-weighted offense and defense EPA/play plus play counts. Each row
  exposes: `off_epa_pp`, `def_epa_pp`, `off_plays`, `def_plays`, and the
  combined `net_epa_pp`/`plays` for convenience.
- The browser and Flask views compute a ridge-regularised SRS-style adjustment
  using a selectable opponent strength basis (default: season-to-date through
  the selected end week) and apply opponent **defensive** ratings to offenses
  and opponent **offensive** ratings to defenses. The same toggle also powers
  the SOS-adjusted Hall of Fame page.
- Opponent strength basis options:
  - `season_to_date` (default): ratings use games through the selected end week
    with no future leakage.
  - `window_only`: ratings use only games inside the selected display window
    (more volatile for small ranges).
  - `full_season`: ratings use all games in the season (hindsight).
- Two helper columns accompany the adjusted ratings when the data is
  available:
  - `net_epa_pp_sos_adj`: window’s combined EPA/play plus the plays-weighted
    SOS faced in that window
  - `sos_off_faced`: plays-weighted average **opponent defensive** rating faced
    in the window (used to adjust offense)
  - `sos_def_faced`: plays-weighted average **opponent offensive** rating faced
    in the window (used to adjust defense)
- Early-season noise is tamed with a modest ridge penalty (λ=20 by default) so
  ratings do not overreact to a single blowout.
- After upgrading the schema, re-run the backfill to populate the new per-game
  columns; the SQLite migration defaults to zeros for existing rows.

## Preview locally (optional)

Open `index.html` in your browser (double-click from your file explorer or run
`python -m http.server 8000` and visit `http://localhost:8000`). Use the season
and week range controls to redraw the chart.
