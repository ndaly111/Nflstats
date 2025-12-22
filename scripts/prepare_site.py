"""Build the static site bundle used for GitHub Pages.

The GitHub Actions workflows generate the EPA JSON into ``data/``. This
utility copies the HTML shell and data payloads into ``site/`` so the Pages
artifact is ready to publish. A ``.nojekyll`` marker is also written to
prevent GitHub Pages from stripping the ``data/`` folder.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from shutil import copy2

from .plot_epa_scatter import REPO_ROOT


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assemble the static Pages bundle")
    parser.add_argument(
        "--site-dir",
        type=Path,
        default=REPO_ROOT / "site",
        help="Destination directory for the published site",
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=REPO_ROOT / "index.html",
        help="HTML entrypoint to copy into the site directory",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=REPO_ROOT / "data",
        help="Directory containing EPA JSON payloads to mirror into the site",
    )
    return parser.parse_args()


def copy_data(source_dir: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    if not source_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {source_dir}")

    for json_file in source_dir.glob("*.json"):
        copy2(json_file, dest_dir / json_file.name)


def build_site(site_dir: Path, index_path: Path, data_dir: Path) -> None:
    site_dir.mkdir(parents=True, exist_ok=True)

    if not index_path.exists():
        raise FileNotFoundError(f"Index file not found: {index_path}")
    copy2(index_path, site_dir / "index.html")

    copy_data(data_dir, site_dir / "data")

    # Prevent Jekyll from mangling the data directory on GitHub Pages.
    (site_dir / ".nojekyll").write_text("", encoding="utf-8")


def main() -> None:
    args = parse_args()
    build_site(args.site_dir, args.index, args.data_dir)
    print(f"Static site assembled in {args.site_dir.resolve()}")


if __name__ == "__main__":
    main()
