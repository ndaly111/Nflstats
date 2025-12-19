"""Download NFL team logos and normalize them to consistent dimensions.

When online access and optional dependencies (requests + Pillow) are available,
this script downloads transparent PNGs from the documented logo repository and
centers them on a square canvas. If downloads fail—such as in offline
environments—it falls back to generating labeled placeholder PNGs so plotting
scripts still have consistent, keyed assets to use.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from io import BytesIO
from pathlib import Path
from typing import Iterable, Optional

import requests
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sources import logo_url

TEAM_ABBREVIATIONS: tuple[str, ...] = (
    "ARI",
    "ATL",
    "BAL",
    "BUF",
    "CAR",
    "CHI",
    "CIN",
    "CLE",
    "DAL",
    "DEN",
    "DET",
    "GB",
    "HOU",
    "IND",
    "JAX",
    "KC",
    "LAC",
    "LAR",
    "LV",
    "MIA",
    "MIN",
    "NE",
    "NO",
    "NYG",
    "NYJ",
    "PHI",
    "PIT",
    "SEA",
    "SF",
    "TB",
    "TEN",
    "WAS",
)

DEFAULT_SIZE = 256


def download_logo_bytes(team_abbr: str) -> Optional[bytes]:
    """Attempt to download logo bytes using ``requests``."""

    url = logo_url(team_abbr, fmt="png")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.content
    except requests.RequestException:
        return None


def standardized_logo(image: Image.Image, canvas_size: int) -> Image.Image:  # type: ignore[name-defined]
    """Resize a logo to fit on a square transparent canvas."""

    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    working = image.convert("RGBA")
    working.thumbnail((canvas_size, canvas_size), Image.LANCZOS)

    x_offset = (canvas_size - working.width) // 2
    y_offset = (canvas_size - working.height) // 2
    canvas.paste(working, (x_offset, y_offset), mask=working)
    return canvas


def placeholder_logo(team_abbr: str, canvas_size: int) -> bytes:
    """Generate a simple placeholder PNG with the team abbreviation."""

    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    hue = int(hashlib.sha256(team_abbr.encode()).hexdigest(), 16)
    base_r = (hue >> 16) & 0xFF
    base_g = (hue >> 8) & 0xFF
    base_b = hue & 0xFF
    background = (base_r, base_g, base_b, 230)
    draw.rectangle([(0, 0), (canvas_size, canvas_size)], fill=background)

    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", size=max(24, canvas_size // 4))
    except OSError:
        font = ImageFont.load_default()

    text = team_abbr.upper()
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    x_offset = (canvas_size - text_width) // 2
    y_offset = (canvas_size - text_height) // 2

    draw.text((x_offset, y_offset), text, fill=(255, 255, 255, 255), font=font)
    buffer = BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


def cache_team_logo(team_abbr: str, output_dir: Path, canvas_size: int) -> Path:
    """Download, resize, and cache a team logo PNG."""

    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{team_abbr.upper()}.png"

    raw_bytes = download_logo_bytes(team_abbr)
    if raw_bytes:
        try:
            logo = Image.open(BytesIO(raw_bytes))
            normalized = standardized_logo(logo, canvas_size)
            normalized.save(destination, format="PNG")
            return destination
        except Exception:
            destination.write_bytes(raw_bytes)
            return destination

    placeholder = placeholder_logo(team_abbr, canvas_size)
    destination.write_bytes(placeholder)
    return destination


def cache_all_logos(teams: Iterable[str], output_dir: Path, canvas_size: int) -> None:
    for team in teams:
        path = cache_team_logo(team, output_dir, canvas_size)
        print(f"Saved {team} logo to {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--size",
        type=int,
        default=DEFAULT_SIZE,
        help="Square canvas size in pixels for the resized logos (default: 256).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("assets") / "logos",
        help="Directory to place normalized logo PNGs.",
    )
    parser.add_argument(
        "--teams",
        nargs="*",
        default=TEAM_ABBREVIATIONS,
        help="Optional subset of team abbreviations to download.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cache_all_logos(args.teams, args.output_dir, args.size)


if __name__ == "__main__":
    main()
