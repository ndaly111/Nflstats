# Nflstats

## Project Structure

- `data/`: Raw downloads such as play-by-play CSVs.
- `scripts/`: Reusable data fetch and cleaning utilities.
- `plots/`: Generated visualizations and analysis outputs.
- `assets/logos/`: Local cache for team logos saved as `<TEAM>.png` with uniform sizing (generated, not committed).

## Environment

This project uses Python with `pandas`, `matplotlib`, and `seaborn` for data
exploration and plotting. Install dependencies into a virtual environment of
your choice:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you prefer a one-command workflow, the provided `Makefile` exposes common
targets (see [Run end-to-end](#run-end-to-end)).

## Usage Notes

- Download raw play-by-play data into `data/` and populate team logos under
  `assets/logos/` using the helpers in `sources.py` or the convenience scripts
  below.
- Cache 256x256 transparent team logos with `scripts/download_logos.py` (or the
  [`make logos`](#run-end-to-end) target). The script resizes downloaded assets
  when online and otherwise generates labeled placeholders so plots always have
  consistent-sized logo files.
- Place ad-hoc or scheduled ETL notebooks/scripts in `scripts/`.
- Save generated figures and charts to `plots/` for easy sharing.

## Data Sources

### Expected Points Added (EPA)
- **Provider:** nflfastR weekly CSVs via the maintained `nflverse-data` snapshot on GitHub.
- **Endpoint:** `https://github.com/nflverse/nflverse-data/tree/master/data` with per-season play-by-play files (e.g., `https://raw.githubusercontent.com/nflverse/nflverse-data/master/data/play_by_play_2023.csv.gz`).
- **Offline fallback:** A minimal plain-text sample file lives at `data/play_by_play_sample.csv` and is gzipped on the fly when
  the live download is unavailable (for example, in offline CI).
- **Required parameters:**
  - Season year embedded in filename (e.g., `play_by_play_2023.csv.gz`).
  - Optional downstream filters applied after download (week, team, offense/defense splits).
- **Update cadence:** Files updated weekly in-season after games conclude (typically within 24 hours); historical seasons are static snapshots.

### Team Logos
- **Source:** GitHub-hosted SVG/PNG set from `https://github.com/ryanmcdermott/nfl-logos`.
- **Access:** Direct raw file URLs under `https://raw.githubusercontent.com/ryanmcdermott/nfl-logos/master/` (e.g., `png/<team>.png` or `svg/<team>.svg`).
- **Attribution/Licensing:** Repository notes assets are for informational/educational use and originate from public logo vectors; verify trademark usage before production deployment.

## Setup and data refresh

Fetch a season of play-by-play data and aggregate EPA/play by team:

```bash
python -m scripts.fetch_epa --season 2023
```

Download or synthesize normalized team logos for plotting:

```bash
python -m scripts.download_logos --output-dir assets/logos --size 256
```

Both commands default to saving under `data/` and `assets/logos/`. Re-run them
when a new nflfastR release drops to refresh the source data.

### Restrict to specific weeks or win-probability windows

The EPA fetcher can mirror common analytics views—such as weeks 8-15 with win
probabilities between 10-90%—using its filtering flags:

```bash
python -m scripts.fetch_epa --season 2022 --week-start 8 --week-end 15 --min-wp 0.1 --max-wp 0.9
```

By default postseason plays are excluded; pass `--include-playoffs` to keep
them. These filters are applied before calculating per-team offensive and
defensive EPA/play.

## Generate the EPA scatter plot

With the aggregated data and logos in place, render the offense vs defense
scatter chart:

```bash
python -m scripts.plot_epa_scatter --season 2023 --week "Weeks 1-10" --output plots/epa_scatter.png
```

The script will read `data/team_epa_<season>.csv` by default and saves PNG
output to `plots/epa_scatter.png`, optionally alongside SVG/PDF copies via
`--svg`/`--pdf`. Use `--invert-y` to flip the defensive EPA axis so better
defenses appear higher on the chart. Combine this with the filters above to
mirror the example tiers chart:

```bash
python -m scripts.plot_epa_scatter --season 2022 --week "Weeks 8-15 (win prob 10-90%)" --invert-y --output plots/epa_scatter_2022_w8_15.png
```

### One-step team tiers chart (nflreadpy)

For a single-command version that pulls play-by-play data through `nflreadpy`,
filters competitive run/pass plays, aggregates EPA/play, and plots logos, run:

```bash
python team_tiers.py --season 2024 --week-start 8 --week-end 15 --output plots/team_tiers_2024.png
```

Key flags mirror the example tiers chart:

- `--wp-min`/`--wp-max`: win-probability window (defaults to 10-90%).
- `--play-types`: list of play types to include (defaults to `run pass`).
- `--down-min`/`--down-max`: down filters (defaults to 1-4).
- `--invert-y`/`--no-invert-y`: flip the defensive EPA axis so better defenses trend upward (default: inverted).

Aggregated data is saved alongside the plot (default `data/team_epa_<season>_tiers.csv`).

## Run end-to-end

A lightweight `Makefile` provides shortcuts for common tasks. Override the
`SEASON` variable on the command line to switch years.

```bash
make logos                # Cache logos into assets/logos (placeholders if offline)
make fetch-epa SEASON=2023 WEEK_START=8 WEEK_END=15 MIN_WP=0.1 MAX_WP=0.9  # Download + summarize with filters
make plot-epa SEASON=2023 WEEK_LABEL="Weeks 8-15 (win prob 10-90%)" INVERT_Y=1  # Render plots/epa_scatter.png with labels and inverted y-axis
make refresh SEASON=2023    # Run all the above in order
```

The Make targets use `python -m scripts.<task>` so they work in both virtual
environments and system installs.

## Required Data Fields
To support EPA reporting by team and time period, the ingest should capture:
- **Team identifier:** Club code matching nflfastR team abbreviations (e.g., `KC`, `PHI`).
- **Offensive EPA/play:** Aggregate or per-play `epa` values when the team is on offense.
- **Defensive EPA/play:** Aggregate or per-play `epa` values when the team is on defense (opponent offense).
- **Season filter:** Ability to select a given season year from the play-by-play dataset.
- **Week filter:** Ability to limit computations to specific weeks within a season.

## Notes
- EPA calculations and team splits are derived from the nflfastR play-by-play dataset after download.
- Logo filenames now use uppercase team abbreviations (e.g., `assets/logos/KC.png`).

## Implementation Helpers
Use `sources.py` to work with the documented endpoints directly:

```python
from pathlib import Path
from sources import download_epa_csv, download_team_logo

# Download gzipped play-by-play CSV for 2023 into ./data
epa_path = download_epa_csv(2023)

# Download and normalize all logos to ./assets/logos
from scripts.download_logos import cache_all_logos, TEAM_ABBREVIATIONS

cache_all_logos(TEAM_ABBREVIATIONS, Path("assets") / "logos", canvas_size=256)

print("EPA file saved to", epa_path)
print("Logos saved to assets/logos")
```
