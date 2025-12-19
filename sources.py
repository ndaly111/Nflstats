"""Utilities for accessing EPA and logo assets from documented sources.

This module keeps code and documentation aligned by encapsulating the URLs
and download helpers described in the README. Only the standard library is
used to avoid extra runtime dependencies.
"""
from pathlib import Path
import gzip
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
import shutil

# The nflfastR data repository moved to the `nflverse` organization. The previous
# `guga31bb/nflfastR-data` location is no longer updated and returns 404s for
# newer seasons, so point to the maintained source instead.
EPA_BASE_URL = "https://raw.githubusercontent.com/nflverse/nflverse-data/master/data"
LOGO_BASE_URL = "https://raw.githubusercontent.com/ryanmcdermott/nfl-logos/master"

LogoFormat = Literal["png", "svg"]


def epa_csv_url(season: int) -> str:
    """Build the nflfastR play-by-play CSV URL for a season.

    Args:
        season: Season year (e.g., 2023).

    Returns:
        Fully qualified HTTPS URL for the gzipped CSV file.
    """
    return f"{EPA_BASE_URL}/play_by_play_{season}.csv.gz"


def logo_url(team_abbr: str, fmt: LogoFormat = "png") -> str:
    """Build the URL for a team logo asset.

    Args:
        team_abbr: Team abbreviation (e.g., "KC", "PHI").
        fmt: File format extension (png or svg).

    Returns:
        HTTPS URL for the requested logo asset.
    """
    normalized_team = team_abbr.lower()
    return f"{LOGO_BASE_URL}/{fmt}/{normalized_team}.{fmt}"


def download_file(url: str, destination: Path) -> Path:
    """Download a remote asset to a destination path.

    Parent directories are created automatically. The function streams the
    response directly to disk to keep memory usage predictable for large EPA
    CSV files.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        with urlopen(url) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output)
    except HTTPError as exc:
        if exc.code == 404:
            raise FileNotFoundError(f"Remote file not found at {url}") from exc
        raise
    except URLError as exc:
        raise ConnectionError(f"Failed to reach {url}: {exc.reason}") from exc

    return destination


def download_epa_csv(
    season: int, target_dir: Path | None = None, *, fallback_sample: Path | None = None
) -> Path:
    """Download a season's nflfastR play-by-play CSV.

    Args:
        season: Season year to retrieve.
        target_dir: Optional directory for the downloaded file. Defaults to
            a local "data" directory under the repository root.
        fallback_sample: Optional local gzipped CSV to copy into place when the
            remote download fails (useful for offline runs).

    Returns:
        Path to the downloaded gzipped CSV file.
    """
    directory = target_dir or Path("data")
    url = epa_csv_url(season)
    destination = directory / f"play_by_play_{season}.csv.gz"

    try:
        return download_file(url, destination)
    except (FileNotFoundError, ConnectionError):
        if fallback_sample and fallback_sample.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            if fallback_sample.suffix == ".gz":
                shutil.copy(fallback_sample, destination)
            else:
                with fallback_sample.open("rb") as source, gzip.open(destination, "wb") as gz_target:
                    shutil.copyfileobj(source, gz_target)
            return destination
        raise


def download_team_logo(team_abbr: str, fmt: LogoFormat = "png", target_dir: Path | None = None) -> Path:
    """Download a team logo asset.

    Args:
        team_abbr: Team abbreviation matching logo filenames (e.g., "KC").
        fmt: Desired logo format (png or svg).
        target_dir: Optional directory for downloaded logos. Defaults to the
            "assets/logos" directory under the repository root.

    Returns:
        Path to the downloaded logo file.
    """
    directory = target_dir or Path("assets") / "logos" / fmt
    url = logo_url(team_abbr, fmt)
    destination = directory / f"{team_abbr.lower()}.{fmt}"
    return download_file(url, destination)
