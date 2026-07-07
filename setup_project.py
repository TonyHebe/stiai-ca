"""
setup_project.py
One-time setup: creates directories, downloads Montserrat fonts, copies .env.example.
Run once before using main.py for the first time.
"""

import os
import shutil
import zipfile
from io import BytesIO
from pathlib import Path

import requests

BASE_DIR   = Path(__file__).parent
FONTS_DIR  = BASE_DIR / "assets" / "fonts"
IMAGES_DIR = BASE_DIR / "assets" / "images"
OUTPUT_DIR = BASE_DIR / "output"
POSTED_DIR = BASE_DIR / "posted"
ENV_FILE   = BASE_DIR / ".env"
ENV_EXAMPLE = BASE_DIR / ".env.example"

# Google Fonts static download URLs for Montserrat
FONT_URLS = {
    "Montserrat-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf",
    "Montserrat-Bold.ttf":    "https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf",
}

# Simpler: use the static TTF files from a reliable CDN
FONT_STATIC_URLS = {
    "Montserrat-Regular.ttf": (
        "https://fonts.gstatic.com/s/montserrat/v26/JTUHjIg1_i6t8kCHKm4532VJOt5-QNFgpCtr6Hw5aXp-p7K4KLjztg.woff2"
    ),
    "Montserrat-Bold.ttf": (
        "https://fonts.gstatic.com/s/montserrat/v26/JTUHjIg1_i6t8kCHKm4532VJOt5-QNFgpCuM70w5aXp-p7K4KLjztg.woff2"
    ),
}


def create_dirs() -> None:
    dirs = [FONTS_DIR, IMAGES_DIR, OUTPUT_DIR, POSTED_DIR]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    print("✓  Directories ready.")


def download_fonts() -> None:
    """
    Download Montserrat Regular + Bold from Google Fonts GitHub releases.
    Uses the variable font file and renames it for each weight —
    this works because Pillow reads it as a static TTF.
    """
    # Direct links to the static Montserrat TTF files on GitHub Releases
    ttf_sources = {
        "Montserrat-Regular.ttf": (
            "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Regular.ttf"
        ),
        "Montserrat-Bold.ttf": (
            "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf"
        ),
    }

    all_ok = True
    for filename, url in ttf_sources.items():
        dest = FONTS_DIR / filename
        if dest.exists():
            print(f"✓  {filename} already present.")
            continue
        print(f"  Downloading {filename} …", end="", flush=True)
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            print(f" done ({len(resp.content)//1024} KB)")
        except Exception as exc:
            print(f" FAILED: {exc}")
            all_ok = False

    if not all_ok:
        print(
            "\n  ⚠  Some fonts could not be downloaded automatically.\n"
            "     Download Montserrat-Regular.ttf and Montserrat-Bold.ttf manually from:\n"
            "     https://fonts.google.com/specimen/Montserrat\n"
            f"     and place them in:  {FONTS_DIR}\n"
        )


def copy_env_example() -> None:
    if not ENV_FILE.exists() and ENV_EXAMPLE.exists():
        shutil.copy(ENV_EXAMPLE, ENV_FILE)
        print(f"✓  Created .env from .env.example — fill in your credentials.")
    elif ENV_FILE.exists():
        print("✓  .env already exists.")
    else:
        print("⚠  .env.example not found — create .env manually.")


def verify_install() -> None:
    """Check that required Python packages are importable."""
    missing = []
    for pkg in ("PIL", "requests", "dotenv"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"\n⚠  Missing packages: {', '.join(missing)}")
        print("   Run:  pip install -r requirements.txt\n")
    else:
        print("✓  All Python dependencies installed.")


def main() -> None:
    print("=== Știai Că? — Project Setup ===\n")
    create_dirs()
    download_fonts()
    copy_env_example()
    verify_install()
    print(
        "\n=== Setup complete ===\n"
        "Next steps:\n"
        "  1. Edit .env and add your Facebook Page ID and Page Access Token.\n"
        "     (Optionally add an Unsplash Access Key for automatic backgrounds.)\n"
        "  2. Run:  python main.py --verify\n"
        "     to confirm the Facebook token works.\n"
        "  3. Run:  python main.py --dry-run\n"
        "     to generate the first post image without posting.\n"
        "  4. Run:  python main.py --no-delay\n"
        "     to post immediately.\n"
        "  5. Set up a cron job (see README.md) for automatic scheduling.\n"
    )


if __name__ == "__main__":
    main()
