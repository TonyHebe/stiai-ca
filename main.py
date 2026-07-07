"""
main.py
Orchestrator for the Știai Că? Facebook auto-poster.

Workflow:
  1. Sleep a random delay (0 … MAX_RANDOM_DELAY_SECONDS) so posts never land
     at the exact same minute when the cron fires.
  2. If the unposted queue is below LOW_CONTENT_THRESHOLD, auto-generate new
     curiosities via content_generator (requires OPENAI_API_KEY).
  3. Pick the next unpublished curiosity from curiosities.json.
  4. Obtain a background image (local file → Unsplash download → error).
  5. Generate the styled post image with image_generator.
  6. Post to Facebook with facebook_poster.
  7. Mark the curiosity as posted; persist state.

Usage:
  python main.py              # normal run (with random delay)
  python main.py --no-delay   # skip the random delay (useful for testing)
  python main.py --dry-run    # generate image but do NOT post to Facebook
  python main.py --verify     # only verify Facebook credentials, then exit
"""

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import facebook_poster
import image_generator

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR         = Path(__file__).parent
CURIOSITIES_FILE = BASE_DIR / "content" / "curiosities.json"
IMAGES_DIR       = BASE_DIR / "assets" / "images"
OUTPUT_DIR       = BASE_DIR / "output"
POSTED_LOG       = BASE_DIR / "posted" / "posted_log.json"

# ── Env vars ─────────────────────────────────────────────────────────────────
PAGE_ID       = os.getenv("FACEBOOK_PAGE_ID", "")
ACCESS_TOKEN  = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "")
UNSPLASH_KEY  = os.getenv("UNSPLASH_ACCESS_KEY", "")
OPENAI_KEY    = os.getenv("OPENAI_API_KEY", "")
MAX_DELAY     = int(os.getenv("MAX_RANDOM_DELAY_SECONDS", "3600"))

# Auto-generate new content when fewer than this many unposted entries remain
LOW_CONTENT_THRESHOLD = int(os.getenv("LOW_CONTENT_THRESHOLD", "3"))
# How many new curiosities to generate when the queue is low
GENERATE_BATCH_SIZE   = int(os.getenv("GENERATE_BATCH_SIZE", "5"))
MAX_POSTS_PER_DAY     = int(os.getenv("MAX_POSTS_PER_DAY", "0"))  # 0 = unlimited
TIMEZONE              = os.getenv("TIMEZONE", "Europe/Bucharest")


# ── State helpers ─────────────────────────────────────────────────────────────

def load_curiosities() -> list[dict]:
    with open(CURIOSITIES_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def save_curiosities(data: list[dict]) -> None:
    with open(CURIOSITIES_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def append_posted_log(entry: dict) -> None:
    POSTED_LOG.parent.mkdir(parents=True, exist_ok=True)
    log = []
    if POSTED_LOG.exists():
        with open(POSTED_LOG, encoding="utf-8") as fh:
            log = json.load(fh)
    log.append(entry)
    with open(POSTED_LOG, "w", encoding="utf-8") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=2)


def posts_today() -> int:
    """Count how many posts were made today (in TIMEZONE)."""
    if not POSTED_LOG.exists():
        return 0
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(TIMEZONE)
    except Exception:
        tz = None

    today = datetime.now(tz).date() if tz else datetime.now().date()
    with open(POSTED_LOG, encoding="utf-8") as fh:
        log = json.load(fh)

    count = 0
    for entry in log:
        posted_at = entry.get("posted_at", "")
        if not posted_at:
            continue
        try:
            dt = datetime.fromisoformat(posted_at)
            if tz and dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
            elif tz:
                dt = dt.astimezone(tz)
            if dt.date() == today:
                count += 1
        except ValueError:
            continue
    return count


def pick_next(curiosities: list[dict]) -> dict | None:
    """Return the first unposted curiosity, or None if all are done."""
    unposted = [c for c in curiosities if not c.get("posted")]
    if not unposted:
        return None
    return unposted[0]


def maybe_refill_queue(curiosities: list[dict]) -> list[dict]:
    """
    If fewer than LOW_CONTENT_THRESHOLD unposted entries remain and
    OPENAI_API_KEY is set, auto-generate GENERATE_BATCH_SIZE new curiosities.
    Returns the (potentially updated) curiosities list.
    """
    unposted_count = sum(1 for c in curiosities if not c.get("posted"))
    if unposted_count >= LOW_CONTENT_THRESHOLD:
        return curiosities

    if not OPENAI_KEY:
        print(
            f"[main] Queue low ({unposted_count} remaining). "
            "Set OPENAI_API_KEY in .env to enable auto-generation."
        )
        return curiosities

    print(
        f"[main] Queue low ({unposted_count} remaining). "
        f"Auto-generating {GENERATE_BATCH_SIZE} new curiosities (GPT text + DALL-E image)..."
    )
    try:
        import content_generator
        content_generator.generate_curiosities(count=GENERATE_BATCH_SIZE)
        return load_curiosities()
    except Exception as exc:
        print(f"[main] Auto-generation failed: {exc}")
        return curiosities


# ── Background image resolution ──────────────────────────────────────────────

def resolve_background(curiosity: dict) -> str:
    """
    Returns a local path to a background image for *curiosity*.

    Priority:
      1. Explicit local file listed in curiosity["image_file"]
      2. Auto-cached download from Unsplash (requires UNSPLASH_ACCESS_KEY)
      3. Any *.jpg / *.jpeg / *.png in assets/images/ (random pick)
    """
    # 1. Explicit local file
    if curiosity.get("image_file"):
        local = IMAGES_DIR / curiosity["image_file"]
        if local.exists():
            return str(local)
        print(f"[main] Warning: image_file '{curiosity['image_file']}' not found, falling back.")

    # 2. Cached Unsplash download
    cache_name = f"bg_{curiosity['id']}.jpg"
    cache_path = IMAGES_DIR / cache_name
    if cache_path.exists():
        return str(cache_path)

    if UNSPLASH_KEY and curiosity.get("image_keywords"):
        print(f"[main] Downloading background from Unsplash: {curiosity['image_keywords']}")
        try:
            return image_generator.download_background(
                keywords=curiosity["image_keywords"],
                unsplash_key=UNSPLASH_KEY,
                save_path=str(cache_path),
            )
        except Exception as exc:
            print(f"[main] Unsplash download failed: {exc}")

    # 3. Random local fallback
    candidates = list(IMAGES_DIR.glob("*.jpg")) + list(IMAGES_DIR.glob("*.jpeg")) + list(IMAGES_DIR.glob("*.png"))
    if candidates:
        chosen = random.choice(candidates)
        print(f"[main] Using random local background: {chosen.name}")
        return str(chosen)

    raise FileNotFoundError(
        "No background image available. Either set UNSPLASH_ACCESS_KEY in .env or "
        f"place a photo in {IMAGES_DIR}/"
    )


# ── Main flow ─────────────────────────────────────────────────────────────────

def run(dry_run: bool = False) -> None:
    if not PAGE_ID or not ACCESS_TOKEN:
        sys.exit(
            "[main] ERROR: FACEBOOK_PAGE_ID and FACEBOOK_PAGE_ACCESS_TOKEN must be set in .env"
        )

    if MAX_POSTS_PER_DAY > 0 and not dry_run:
        today_count = posts_today()
        if today_count >= MAX_POSTS_PER_DAY:
            print(
                f"[main] Daily limit reached ({today_count}/{MAX_POSTS_PER_DAY}). "
                "Skipping — will try again at next cron trigger."
            )
            return

    curiosities = load_curiosities()

    # Refill queue with AI-generated content when running low
    curiosities = maybe_refill_queue(curiosities)

    item = pick_next(curiosities)

    if item is None:
        print("[main] All curiosities have been posted. Add new entries to curiosities.json.")
        # Reset all to unposted and start over
        for c in curiosities:
            c["posted"] = False
        save_curiosities(curiosities)
        item = pick_next(curiosities)
        print(f"[main] Cycle reset — starting over with: {item['title']}")

    print(f"[main] Selected: [{item['id']}] {item['title']}")

    # Resolve background image
    bg_path = resolve_background(item)
    print(f"[main] Background: {bg_path}")

    # Generate post image
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
    img_name  = f"{item['id']}_{ts}.jpg"
    img_path  = str(OUTPUT_DIR / img_name)

    image_generator.generate_post_image(
        background_path=bg_path,
        title=item["title"],
        image_text=item["image_text"],
        output_path=img_path,
    )

    if dry_run:
        print(f"[main] DRY RUN — image saved to {img_path} but NOT posted to Facebook.")
        return

    # Post to Facebook
    result = facebook_poster.post_photo_to_page(
        page_id=PAGE_ID,
        access_token=ACCESS_TOKEN,
        image_path=img_path,
        caption=item["caption"],
    )

    # Mark as posted
    item["posted"] = True
    save_curiosities(curiosities)
    append_posted_log({
        "id":          item["id"],
        "title":       item["title"],
        "posted_at":   datetime.now().isoformat(),
        "fb_post_id":  result.get("post_id") or result.get("id"),
        "image_file":  img_name,
    })
    print(f"[main] Done ✓  ({item['title']})")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Știai Că? Facebook auto-poster")
    parser.add_argument("--no-delay",  action="store_true", help="Skip random pre-post delay")
    parser.add_argument("--dry-run",   action="store_true", help="Generate image only, do not post")
    parser.add_argument("--verify",    action="store_true", help="Verify Facebook credentials and exit")
    args = parser.parse_args()

    if args.verify:
        ok = facebook_poster.verify_credentials(PAGE_ID, ACCESS_TOKEN)
        sys.exit(0 if ok else 1)

    if not args.no_delay and MAX_DELAY > 0:
        delay = random.randint(0, MAX_DELAY)
        wake  = datetime.now().strftime("%H:%M:%S")
        print(f"[main] Random delay: sleeping {delay}s (started at {wake})")
        time.sleep(delay)

    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
