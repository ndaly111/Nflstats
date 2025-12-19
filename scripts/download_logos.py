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
import struct
import sys
import zlib
from io import BytesIO
from pathlib import Path
from typing import Iterable, Optional
from urllib.error import URLError
from urllib.request import urlopen

try:  # Optional dependency for rich download + resize
    import requests
except ImportError:  # pragma: no cover - optional
    requests = None  # type: ignore

try:  # Optional dependency for resize + format conversion
    from PIL import Image
except ImportError:  # pragma: no cover - optional
    Image = None  # type: ignore

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

# Simple 5x7 bitmap font for uppercase letters
FONT_5X7 = {
    "A": ["  #  ", " # # ", "#   #", "#####", "#   #", "#   #", "#   #"],
    "B": ["#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "],
    "C": [" ### ", "#   #", "#    ", "#    ", "#    ", "#   #", " ### "],
    "D": ["#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "],
    "E": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"],
    "F": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "],
    "G": [" ### ", "#   #", "#    ", "# ###", "#   #", "#   #", " ### "],
    "H": ["#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "I": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "#####"],
    "J": ["#####", "    #", "    #", "    #", "#   #", "#   #", " ### "],
    "K": ["#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"],
    "L": ["#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"],
    "M": ["#   #", "## ##", "# # #", "#   #", "#   #", "#   #", "#   #"],
    "N": ["#   #", "##  #", "# # #", "#  ##", "#   #", "#   #", "#   #"],
    "O": [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "P": ["#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "],
    "Q": [" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"],
    "R": ["#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"],
    "S": [" ### ", "#   #", "#    ", " ### ", "    #", "#   #", " ### "],
    "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "],
    "U": ["#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "V": ["#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "],
    "W": ["#   #", "#   #", "#   #", "# # #", "# # #", "## ##", "#   #"],
    "X": ["#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"],
    "Y": ["#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "],
    "Z": ["#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"],
}


def download_logo_bytes(team_abbr: str) -> Optional[bytes]:
    """Attempt to download logo bytes using urllib or requests."""

    url = logo_url(team_abbr, fmt="png")
    try:
        if requests is not None:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.content
        with urlopen(url) as response:
            return response.read()
    except (URLError, OSError, Exception):
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


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)


def placeholder_logo(team_abbr: str, canvas_size: int) -> bytes:
    """Generate a simple placeholder PNG with the team abbreviation."""

    glyph_width, glyph_height = 5, 7
    text_width = len(team_abbr) * (glyph_width + 1) - 1
    scale = max(4, min(canvas_size // (text_width + 2), canvas_size // (glyph_height + 2)))

    width = height = canvas_size
    pixels = [[(0, 0, 0, 0) for _ in range(width)] for _ in range(height)]

    # Background color derived from abbreviation hash for visual variety.
    hue = int(hashlib.sha256(team_abbr.encode()).hexdigest(), 16)
    base_r = (hue >> 16) & 0xFF
    base_g = (hue >> 8) & 0xFF
    base_b = hue & 0xFF
    for y in range(height):
        for x in range(width):
            alpha = 200
            pixels[y][x] = (base_r, base_g, base_b, alpha)

    start_x = max(0, (width - text_width * scale) // 2)
    start_y = max(0, (height - glyph_height * scale) // 2)

    abbr = team_abbr.upper()
    for idx, char in enumerate(abbr):
        pattern = FONT_5X7.get(char)
        if not pattern:
            continue
        for row, line in enumerate(pattern):
            for col, symbol in enumerate(line):
                if symbol != "#":
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        px = start_x + (idx * (glyph_width + 1) + col) * scale + dx
                        py = start_y + row * scale + dy
                        if 0 <= px < width and 0 <= py < height:
                            pixels[py][px] = (255, 255, 255, 255)

    raw_rows = b"".join(b"\x00" + bytes([c for pixel in row for c in pixel]) for row in pixels)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", ihdr) + png_chunk(b"IDAT", zlib.compress(raw_rows, 9)) + png_chunk(b"IEND", b"")


def cache_team_logo(team_abbr: str, output_dir: Path, canvas_size: int) -> Path:
    """Download, resize, and cache a team logo PNG."""

    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{team_abbr.upper()}.png"

    raw_bytes = download_logo_bytes(team_abbr)
    if raw_bytes and Image is not None:
        try:
            logo = Image.open(BytesIO(raw_bytes))
            normalized = standardized_logo(logo, canvas_size)
            normalized.save(destination, format="PNG")
            return destination
        except Exception:
            pass

    if raw_bytes:
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
