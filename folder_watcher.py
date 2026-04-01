#!/usr/bin/env python3
"""
folder_watcher.py — Wax | Wane "Ready to Publish" Folder Watcher
=================================================================
Monitors a folder on your Mac for new images and videos.
When new files appear, it queues them and posts up to MAX_POSTS_PER_DAY
per day, spaced out evenly.

HOW IT WORKS:
  1. You drop images (or videos) into your "Ready to Publish" folder
  2. This script runs every hour (via launchd on your Mac)
  3. It checks for files not yet in the posted log
  4. If under the daily limit, it posts the next file in queue
  5. It logs every post so nothing gets double-posted

FOLDER NAMING CONVENTION (optional but recommended):
  Put the topic in the filename or a subfolder:
    emf_mindful_tech_boundaries.png      -> topic: emf
    crystals_shungite_infographic.jpg    -> topic: crystals
    haramoon_glass_skin_routine.png      -> topic: haramoon
    wax_product_catalog_banner.jpg       -> topic: wax (default)

  Or use subfolders:
    Ready to Publish/emf/image.png
    Ready to Publish/crystals/image.jpg

SUPPORTED FORMATS:
  Images: .jpg .jpeg .png .webp .gif
  Videos: .mp4 .mov .avi  (posted to Facebook only — IG video requires separate API)

SETUP (one-time on your Mac):
  1. Set WATCH_FOLDER in .env:
     WATCH_FOLDER=/Users/samanthanorman/Desktop/Ready to Publish
  2. Pull this script from GitHub
  3. Register the hourly scheduler (see instructions below)
"""

import os, sys, json, time, logging, requests, base64
from pathlib import Path
from datetime import datetime, date
from dotenv import load_dotenv

# ─── Setup ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
logging.basicConfig(
    filename=BASE_DIR / "folder_watcher.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────
WATCH_FOLDER     = Path(os.getenv("WATCH_FOLDER", str(Path.home() / "Desktop" / "Ready to Publish")))
POSTED_LOG       = BASE_DIR / "posted_files.json"
MAX_POSTS_PER_DAY = int(os.getenv("MAX_POSTS_PER_DAY", "3"))

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTS = {".mp4", ".mov", ".avi"}
ALL_EXTS   = IMAGE_EXTS | VIDEO_EXTS

# ─── Topic detection ──────────────────────────────────────────────────────────
TOPIC_KEYWORDS = {
    "emf":      ["emf", "emi", "radiation", "shielding", "5g", "wifi", "electromagnetic", "terahertz", "faraday"],
    "crystals": ["crystal", "crystals", "shungite", "selenite", "mineral", "gem", "stone", "quartz"],
    "haramoon": ["haramoon", "korean", "kbeauty", "skincare", "serum", "glass", "skin"],
    "wax":      ["wax", "wane", "catalog", "product", "store"],
}

DEFAULT_LINKS = {
    "emf":      "https://waxandwane.store/collections/emf-protection",
    "crystals": "https://waxandwane.store/collections/crystals",
    "haramoon": "https://waxandwane.store/collections/haramoon",
    "wax":      "https://waxandwane.store",
}

def detect_topic(path: Path) -> str:
    """Detect topic from filename or parent folder name."""
    text = (path.stem + " " + path.parent.name).lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return topic
    return "wax"  # default

# ─── Posted log helpers ───────────────────────────────────────────────────────
def load_posted_log() -> dict:
    if POSTED_LOG.exists():
        try:
            return json.loads(POSTED_LOG.read_text())
        except Exception:
            pass
    return {"posted": [], "daily_counts": {}}

def save_posted_log(data: dict):
    POSTED_LOG.write_text(json.dumps(data, indent=2))

def already_posted(path: Path, data: dict) -> bool:
    return str(path) in data.get("posted", [])

def mark_posted(path: Path, data: dict):
    data.setdefault("posted", []).append(str(path))
    today = str(date.today())
    data.setdefault("daily_counts", {})[today] = data["daily_counts"].get(today, 0) + 1
    save_posted_log(data)

def posts_today(data: dict) -> int:
    today = str(date.today())
    return data.get("daily_counts", {}).get(today, 0)

# ─── Video posting (Facebook only) ────────────────────────────────────────────
def post_video_to_facebook(path: Path, caption: str) -> bool:
    FB_PAGE_ID    = os.getenv("FACEBOOK_PAGE_ID", "")
    FB_PAGE_TOKEN = os.getenv("FACEBOOK_PAGE_TOKEN", "")
    if not FB_PAGE_TOKEN:
        log.info("Facebook disabled — skipping video")
        return False
    try:
        with open(str(path), "rb") as f:
            r = requests.post(
                f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/videos",
                data={"description": caption[:5000], "access_token": FB_PAGE_TOKEN},
                files={"source": f},
                timeout=120,
            )
        if r.status_code == 200:
            log.info(f"Facebook video OK — {r.json().get('id','?')}")
            return True
        log.error(f"Facebook video FAIL {r.status_code}: {r.text[:300]}")
    except Exception as e:
        log.error(f"Facebook video exception: {e}")
    return False

# ─── Main watcher loop ────────────────────────────────────────────────────────
def main():
    if not WATCH_FOLDER.exists():
        log.error(f"Watch folder not found: {WATCH_FOLDER}")
        print(f"ERROR: Watch folder not found: {WATCH_FOLDER}")
        print(f"Set WATCH_FOLDER in your .env file or create the folder.")
        sys.exit(1)

    data = load_posted_log()
    count_today = posts_today(data)

    if count_today >= MAX_POSTS_PER_DAY:
        log.info(f"Daily limit reached ({count_today}/{MAX_POSTS_PER_DAY}) — nothing to post today")
        print(f"Daily limit reached ({count_today}/{MAX_POSTS_PER_DAY}). Come back tomorrow.")
        return

    # Collect all unposted files, sorted by modification time (oldest first = FIFO queue)
    all_files = sorted(
        [f for f in WATCH_FOLDER.rglob("*") if f.suffix.lower() in ALL_EXTS and f.is_file()],
        key=lambda f: f.stat().st_mtime
    )
    unposted = [f for f in all_files if not already_posted(f, data)]

    if not unposted:
        log.info("No new files in watch folder")
        print("No new files to post.")
        return

    slots_remaining = MAX_POSTS_PER_DAY - count_today
    to_post = unposted[:slots_remaining]

    print(f"\nWax | Wane Folder Watcher — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Watch folder: {WATCH_FOLDER}")
    print(f"Unposted files: {len(unposted)} | Posting today: {len(to_post)} (limit {MAX_POSTS_PER_DAY}/day)")
    print("=" * 60)

    # Import the cross-poster's process_image function
    sys.path.insert(0, str(BASE_DIR))
    from image_crossposter import process_image

    for f in to_post:
        topic = detect_topic(f)
        link  = DEFAULT_LINKS[topic]
        ext   = f.suffix.lower()

        print(f"\n  [{f.name}]  topic={topic}")

        if ext in VIDEO_EXTS:
            # Videos: Facebook only
            from image_crossposter import CAPTIONS
            caps = CAPTIONS.get(topic, CAPTIONS["wax"])
            title = f.stem.replace("_", " ").replace("-", " ").title()
            caption = caps["facebook"].format(title=title, link=link)
            ok = post_video_to_facebook(f, caption)
            print(f"  Results: Facebook (video): {'OK' if ok else 'FAIL'}")
            log.info(f"VIDEO {f.name} -> Facebook: {'OK' if ok else 'FAIL'}")
        else:
            # Images: use full cross-poster routing
            process_image(f, topic, link)

        mark_posted(f, data)
        time.sleep(2)

    print(f"\nDone. {len(to_post)} file(s) posted today. Check folder_watcher.log for details.")


if __name__ == "__main__":
    main()
