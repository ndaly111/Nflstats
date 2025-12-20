"""Utilities for accessing EPA play-by-play data and team logo assets.

This module centralizes URL construction and download helpers used across the
project. Only the standard library is required unless the optional
``nfl_data_py`` dependency is used to scrape in-progress seasons.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
import shutil

EPA_BASE_URL = "https://raw.githubusercontent.com/guga31bb/nflfastR-data/master/data"
LOGO_BASE_URL = "https://raw.githubusercontent.com/ryanmcdermott/nfl-logos/master"

LogoFormat = Literal["png", "svg"]


def epa_csv_url(season: int) -> str:
    """Build the nflfastR play-by-play CSV URL for a season."""

    return f"{EPA_BASE_URL}/play_by_play_{season}.csv.gz"


def logo_url(team_abbr: str, fmt: LogoFormat = "png") -> str:
    """Build the URL for a team logo asset."""

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


def download_epa_csv_in_progress(season: int, target_dir: Path | None = None) -> Path:
    """Scrape play-by-play data for a season in progress using ``nfl_data_py``.

    A gzipped CSV is written to the same location where the full-season file
    would live so downstream consumers can remain agnostic of the data source.
    """

    try:
        from nfl_data_py import import_data
    except Exception as exc:  # pragma: no cover - optional dependency
        raise ImportError("nfl_data_py is required to scrape in-progress data") from exc

    directory = target_dir or Path("data")
    destination = directory / f"play_by_play_{season}.csv.gz"

    print(f"Scraping in-progress play-by-play data for {season}...")
    df = import_data.import_pbp_data([season])
    destination.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(destination, index=False, compression="gzip")
    return destination


def download_epa_csv(season: int, target_dir: Path | None = None) -> Path:
    """Download a season's nflfastR play-by-play CSV.

    If the hosted file is unavailable (common for in-progress seasons), the
    function falls back to scraping data via ``nfl_data_py``.
    """

    directory = target_dir or Path("data")
    destination = directory / f"play_by_play_{season}.csv.gz"
    url = epa_csv_url(season)

    try:
        return download_file(url, destination)
    except FileNotFoundError as exc:
        try:
            return download_epa_csv_in_progress(season, target_dir)
        except Exception:
            raise FileNotFoundError(f"Remote file not found at {url}") from exc


def download_team_logo(
    team_abbr: str, fmt: LogoFormat = "png", target_dir: Path | None = None
) -> Path:
    """Download a team logo asset."""

    base_dir = target_dir or Path("assets") / "logos"
    directory = base_dir if fmt == "png" else base_dir / fmt
    url = logo_url(team_abbr, fmt)
    destination = directory / f"{team_abbr.upper()}.{fmt}"
    return download_file(url, destination)


def find_team_logo(
    team_abbr: str, fmt: LogoFormat = "png", search_dir: Path | None = None
) -> Path:
    """Locate a previously downloaded team logo on disk.

    The search covers common directory conventions (``assets/logos`` and
    ``assets/logos/<fmt>``) and accepts either uppercase or lowercase team
    abbreviations. A :class:`FileNotFoundError` is raised when no matching
    asset is found.
    """

    base_dir = search_dir or Path("assets") / "logos"
    search_roots: tuple[Path, ...] = (
        base_dir,
        base_dir / fmt,
    )
    candidate_names = (team_abbr.upper(), team_abbr.lower())

    for root in search_roots:
        for name in candidate_names:
            candidate = root / f"{name}.{fmt}"
            if candidate.exists():
                return candidate

    raise FileNotFoundError(
        f"Logo for {team_abbr} with format '{fmt}' not found under {base_dir}"
    )
