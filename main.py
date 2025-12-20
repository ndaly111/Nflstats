import os
from epa_od_fetcher import download_pbp, compute_team_epa
from plotepa import plot_epa

def main():
    year_str = os.getenv("NFL_SEASON", "2025").strip()
    try:
        year = int(year_str)
    except ValueError:
        raise SystemExit(f"Invalid NFL_SEASON env var: {year_str!r} (must be an int like 2025)")

    print(f"Downloading PBP data for {year} ...")
    pbp = download_pbp(year)

    print("Computing EPA by team ...")
    team_epa = compute_team_epa(pbp)

    print("\n=== TEAM EPA (Offense + Defense) ===")
    print(team_epa.sort_values("EPA_off_per_play", ascending=False).to_string())

    out_csv = f"nfl_{year}_team_epa.csv"
    team_epa.to_csv(out_csv)
    print(f"\nSaved {out_csv}")

    print("Generating EPA scatter plot ...")
    output_plot = plot_epa(out_csv)
    print(f"Saved plot to {output_plot}")

if __name__ == "__main__":
    main()
