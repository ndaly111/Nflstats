from pathlib import Path

from epa_od_fetcher import compute_team_epa, download_pbp


def main() -> None:
    year = 2023
    print(f"Downloading PBP data for {year} ...")
    pbp = download_pbp(year)

    print("Computing EPA by team ...")
    team_epa = compute_team_epa(pbp)
    print(team_epa)

    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"nfl_{year}_team_epa.csv"
    team_epa.to_csv(output_path)
    print(f"Saved {output_path}")


if __name__ == "__main__":
    main()
