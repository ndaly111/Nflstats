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

## Usage Notes

- Download raw play-by-play data into `data/` and populate team logos under
  `assets/logos/` using the helpers in `sources.py`.
- Cache 256x256 transparent team logos with `scripts/download_logos.py`.
  The script resizes downloaded assets when online and otherwise generates
  labeled placeholders so plots always have consistent-sized logo files.
- Place ad-hoc or scheduled ETL notebooks/scripts in `scripts/`.
- Save generated figures and charts to `plots/` for easy sharing.

## Data Sources

### Expected Points Added (EPA)
- **Provider:** nflfastR weekly CSVs via GitHub Releases (public data snapshot).
- **Endpoint:** `https://github.com/guga31bb/nflfastR-data/tree/master/data` with per-season play-by-play files (e.g., `https://raw.githubusercontent.com/guga31bb/nflfastR-data/master/data/play_by_play_2023.csv.gz`).
- **Required parameters:**
  - Season year embedded in filename (e.g., `play_by_play_2023.csv.gz`).
  - Optional downstream filters applied after download (week, team, offense/defense splits).
- **Update cadence:** Files updated weekly in-season after games conclude (typically within 24 hours); historical seasons are static snapshots.

### Team Logos
- **Source:** GitHub-hosted SVG/PNG set from `https://github.com/ryanmcdermott/nfl-logos`.
- **Access:** Direct raw file URLs under `https://raw.githubusercontent.com/ryanmcdermott/nfl-logos/master/` (e.g., `png/<team>.png` or `svg/<team>.svg`).
- **Attribution/Licensing:** Repository notes assets are for informational/educational use and originate from public logo vectors; verify trademark usage before production deployment.

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
