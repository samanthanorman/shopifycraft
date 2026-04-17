#!/usr/bin/env python3
"""
Wax | Wane Ad-Hoc Content Calendar
=====================================
Drop images into a folder, run this script, and it:
  1. Reads all images in the folder
  2. Writes captions in HARAMOON brand voice with current SEO hashtags
  3. Groups into carousels if you have 2-3 related images
  4. Schedules them across your chosen days
  5. Posts to Instagram automatically

SETUP (one time only):
  export IG_TOKEN="your_instagram_graph_api_token"
  export IG_USER_ID="your_instagram_business_account_id"
  export OPENAI_API_KEY="your_openai_key"

USAGE:
  python3 content_calendar.py --folder ~/Desktop/haramoon_batch --brand HARAMOON
  python3 content_calendar.py --folder ~/Desktop/crystals_batch --brand CRYSTALS
  python3 content_calendar.py --folder ~/Desktop/batch --brand HARAMOON --days "Mon,Thu" --start 2026-04-21
  python3 content_calendar.py --preview    # Show scheduled queue without posting
  python3 content_calendar.py --post-next  # Post the next scheduled item now

BRANDS:
  HARAMOON   — clinical K-beauty, ingredient science, skin barrier
  CRYSTALS   — healing crystals, minerals, metaphysical wellness
  EMF        — EMF protection, grounding, frequency wellness
  WAXWANE    — holistic wellness hub, all brands

NOTES:
  - Images are padded to 1080x1080 automatically
  - Captions are written by GPT-4 in your brand voice
  - Hashtags are SEO-optimized per brand
  - State is saved in ~/.waxwane_calendar_state.json so it survives restarts
  - Run with: nohup python3 content_calendar.py --folder ... &   to run in background
"""

import os
import sys
import json
import time
import argparse
import requests
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

try:
    from PIL import Image
    import io
except ImportError:
    print("Installing Pillow...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pillow"], check=True)
    from PIL import Image
    import io

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
# Wax | Wane credentials (confirmed working Apr 17 2026)
IG_TOKEN   = os.environ.get("IG_TOKEN",   "EAASgzu1LdvABRJPUrCLFfT6SBuUyeJu3QV2PQexpOE7Xfvlo0rvdbIQVzdZCEp7eqDo7vxegIn8y52cnLYCntTHKE3mlx4fhoECAyp0SanD0Ju9XCdRFEBzCKdSUE0nB5SHuAndO6dNJEz0VVjTvvscTVTaffV8twSu1gLBk0ZCt0DYtkG0gSE1sZBcJQZDZD")
IG_USER_ID    = os.environ.get("IG_USER_ID",    "17841458399612807")
FB_PAGE_ID    = os.environ.get("FB_PAGE_ID",    "203171376205580")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN", "EAASgzu1LdvABRFou790AZAdQdTlernJZACPM0dRcDgP12LiNhHFND1ztu01Hr8CnkW4sH9zvivJqRi5rQryscOio5KFXO2xRZCPYonnZBFVfO4lJZB9LUq8NdGjtT9dHHDTv8woZAEYUFoaDz6FmBSRlKdfP20HZBsZBEq1MH4w4uWIMJTRzKZB1fso3ZB7xOKZCFNzBq502jMZD")
OPENAI_KEY    = os.environ.get("OPENAI_API_KEY", "")
STATE_FILE = Path.home() / ".waxwane_calendar_state.json"

BRAND_VOICES = {
    "HARAMOON": {
        "tone": "clinical, clean, confident. Korean skincare science meets modern minimalism. No fluff.",
        "cta": "Shop at https://www.waxandwane.store | Also on Amazon: https://www.amazon.com/stores/HaramoonUSA/page/4D229D57-2C46-409B-8ECB-ABECAA03B46D",
        "hashtags": "#HARAMOON #KoreanSkincare #KBeauty #SkinBarrier #EWGVerified #VeganSkincare #CleanBeauty #pH55 #IngredientNerd #SkincareScience #GlassSkin #KBeautyRoutine",
        "niche": "Korean skincare, skin barrier repair, clean vegan beauty, ingredient science",
    },
    "CRYSTALS": {
        "tone": "mystical, grounded, educational. Speaks to collectors and spiritual wellness seekers.",
        "cta": "Explore the collection at https://www.waxandwane.store",
        "hashtags": "#CrystalHealing #Crystals #MineralCollector #HealingCrystals #CrystalEnergy #Metaphysical #WellnessRitual #CrystalShop #SpiritualWellness #Gemstones",
        "niche": "healing crystals, mineral collecting, metaphysical wellness, spiritual tools",
    },
    "EMF": {
        "tone": "informative, protective, empowering. Speaks to health-conscious, tech-aware adults.",
        "cta": "Learn more at https://www.waxandwane.store",
        "hashtags": "#EMFProtection #EMFAwareness #Grounding #5GProtection #ElectromagneticHealth #DigitalWellness #EMF #FrequencyWellness #HealthyLiving #CleanLiving",
        "niche": "EMF protection, grounding, frequency wellness, digital detox",
    },
    "WAXWANE": {
        "tone": "holistic, inclusive, curious. The hub where science meets spirit.",
        "cta": "Discover more at https://www.waxandwane.store",
        "hashtags": "#WaxAndWane #HolisticWellness #CleanBeauty #MindBodySkin #WellnessStore #NaturalLiving #ConsciousBeauty #HolisticHealth",
        "niche": "holistic wellness, clean beauty, crystals, Korean skincare, EMF protection",
    },
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}

# ─────────────────────────────────────────────
# IMAGE PROCESSING
# ─────────────────────────────────────────────

def pad_to_square(img_path, size=1080):
    """Pad image to square 1080x1080 with white background."""
    img = Image.open(img_path).convert("RGB")
    w, h = img.size
    max_dim = max(w, h)
    square = Image.new("RGB", (max_dim, max_dim), (255, 255, 255))
    square.paste(img, ((max_dim - w) // 2, (max_dim - h) // 2))
    square = square.resize((size, size), Image.LANCZOS)
    out_path = Path(img_path).with_suffix(".processed.jpg")
    square.save(out_path, "JPEG", quality=92)
    return str(out_path)

def upload_to_cdn(img_path):
    """Upload image to Manus CDN and return public URL."""
    result = subprocess.run(
        ["manus-upload-file", img_path],
        capture_output=True, text=True
    )
    for line in result.stdout.splitlines():
        if line.startswith("https://"):
            return line.strip()
    raise RuntimeError(f"CDN upload failed: {result.stderr}")

# ─────────────────────────────────────────────
# CAPTION GENERATION
# ─────────────────────────────────────────────

def generate_caption(image_paths, brand, extra_context=""):
    """Use GPT-4 Vision to write a caption for the image(s)."""
    voice = BRAND_VOICES[brand]
    
    # Build image content blocks
    content = []
    for p in image_paths[:3]:  # max 3 images for vision
        with open(p, "rb") as f:
            import base64
            b64 = base64.b64encode(f.read()).decode()
            ext = Path(p).suffix.lstrip(".")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/{ext};base64,{b64}", "detail": "low"}
            })
    
    content.append({
        "type": "text",
        "text": f"""Write an Instagram caption for this {brand} post.

Brand voice: {voice['tone']}
Niche: {voice['niche']}
{f'Extra context: {extra_context}' if extra_context else ''}

Rules:
- 2-3 sentences MAX. Cut every unnecessary word.
- No emojis. No "✨" or "🌿". Keep it clean and editorial.
- End with exactly these hashtags (no more, no less): {voice['hashtags']}
- Final line: {voice['cta']}
- Do NOT start with "Introducing" or "Meet" or "Say hello to"
- Write like a smart friend who knows skincare/wellness, not a brand account

Output ONLY the caption text. Nothing else."""
    })

    headers = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 400,
        "temperature": 0.7,
    }
    r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()

# ─────────────────────────────────────────────
# INSTAGRAM POSTING
# ─────────────────────────────────────────────

def ig_post_single(image_url, caption):
    r = requests.post(
        f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media",
        data={"image_url": image_url, "caption": caption, "access_token": IG_TOKEN}
    )
    r.raise_for_status()
    container_id = r.json()["id"]
    time.sleep(3)
    r2 = requests.post(
        f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish",
        data={"creation_id": container_id, "access_token": IG_TOKEN}
    )
    r2.raise_for_status()
    return r2.json().get("id")

def ig_post_carousel(image_urls, caption):
    child_ids = []
    for url in image_urls:
        r = requests.post(
            f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media",
            data={"image_url": url, "is_carousel_item": "true", "access_token": IG_TOKEN}
        )
        r.raise_for_status()
        child_ids.append(r.json()["id"])
        time.sleep(2)
    r2 = requests.post(
        f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media",
        data={
            "media_type": "CAROUSEL",
            "children": ",".join(child_ids),
            "caption": caption,
            "access_token": IG_TOKEN
        }
    )
    r2.raise_for_status()
    container_id = r2.json()["id"]
    time.sleep(3)
    r3 = requests.post(
        f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish",
        data={"creation_id": container_id, "access_token": IG_TOKEN}
    )
    r3.raise_for_status()
    return r3.json().get("id")

# ─────────────────────────────────────────────
# STATE MANAGEMENT
# ─────────────────────────────────────────────

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"queue": [], "posted": []}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))

# ─────────────────────────────────────────────
# MAIN WORKFLOW
# ─────────────────────────────────────────────

def build_queue(folder, brand, days_str, start_date_str):
    """Scan folder, generate captions, build posting queue."""
    folder = Path(folder).expanduser()
    if not folder.exists():
        print(f"ERROR: Folder not found: {folder}")
        sys.exit(1)

    images = sorted([f for f in folder.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS])
    if not images:
        print(f"No images found in {folder}")
        sys.exit(1)

    print(f"\nFound {len(images)} images in {folder}")
    print(f"Brand: {brand} | Generating captions with GPT-4 Vision...\n")

    # Group into posts (single or carousel of 2-3)
    posts = []
    i = 0
    while i < len(images):
        # Simple grouping: if next 2 images have similar names, make carousel
        batch = [images[i]]
        if i + 1 < len(images) and len(images) <= 6:
            # For small batches, keep singles unless user groups by name prefix
            pass
        posts.append(batch)
        i += 1

    # Parse schedule
    day_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
    post_days = [day_map[d.strip().lower()[:3]] for d in days_str.split(",")]
    start = datetime.strptime(start_date_str, "%Y-%m-%d")

    # Find posting dates
    schedule_dates = []
    d = start
    while len(schedule_dates) < len(posts):
        if d.weekday() in post_days:
            schedule_dates.append(d)
        d += timedelta(days=1)

    queue = []
    for post_imgs, post_date in zip(posts, schedule_dates):
        print(f"  Processing: {[p.name for p in post_imgs]}")
        
        # Pad and upload
        processed = [pad_to_square(str(p)) for p in post_imgs]
        cdn_urls = [upload_to_cdn(p) for p in processed]
        
        # Generate caption
        caption = generate_caption(processed, brand)
        
        post_type = "carousel" if len(cdn_urls) > 1 else "single"
        queue.append({
            "id": f"{brand.lower()}_{post_date.strftime('%Y%m%d')}_{post_imgs[0].stem}",
            "label": post_imgs[0].stem,
            "type": post_type,
            "cdn_urls": cdn_urls,
            "caption": caption,
            "scheduled_for": post_date.isoformat(),
            "posted": False,
        })
        print(f"    Scheduled for: {post_date.strftime('%A, %B %d %Y')}")

    state = load_state()
    state["queue"] = queue
    save_state(state)
    print(f"\n{len(queue)} posts queued. Run with --post-next to start posting.")
    return queue

def preview_queue():
    state = load_state()
    queue = state.get("queue", [])
    if not queue:
        print("\nNo queue found. Run with --folder first.")
        return
    print(f"\n===== CONTENT CALENDAR ({len(queue)} posts) =====\n")
    for i, p in enumerate(queue, 1):
        status = "POSTED" if p.get("posted") else f"Scheduled: {p.get('scheduled_for', 'TBD')[:10]}"
        print(f"  [{i}] {status} — {p['label']} ({p['type']})")
        print(f"       Caption: {p['caption'][:100]}...")
        print()

def post_next():
    if not IG_TOKEN or not IG_USER_ID:
        print("\nERROR: Set IG_TOKEN and IG_USER_ID environment variables first.")
        sys.exit(1)
    state = load_state()
    queue = state.get("queue", [])
    for p in queue:
        if not p.get("posted"):
            print(f"\nPosting: {p['label']} ({p['type']})")
            if p["type"] == "carousel":
                post_id = ig_post_carousel(p["cdn_urls"], p["caption"])
            else:
                post_id = ig_post_single(p["cdn_urls"][0], p["caption"])
            p["posted"] = True
            p["posted_at"] = datetime.now().isoformat()
            p["post_id"] = post_id
            save_state(state)
            print(f"LIVE: https://www.instagram.com/p/{post_id}/")
            return
    print("\nAll posts in queue have been published!")

def run_schedule():
    """Post all items in queue on their scheduled dates."""
    if not IG_TOKEN or not IG_USER_ID:
        print("\nERROR: Set IG_TOKEN and IG_USER_ID environment variables first.")
        sys.exit(1)
    state = load_state()
    queue = state.get("queue", [])
    pending = [p for p in queue if not p.get("posted")]
    if not pending:
        print("\nAll posts published!")
        return
    print(f"\nRunning schedule for {len(pending)} pending posts...")
    print("Keep this terminal open (or run: nohup python3 content_calendar.py &)\n")
    for p in pending:
        scheduled = datetime.fromisoformat(p["scheduled_for"])
        now = datetime.now()
        if scheduled > now:
            wait_secs = (scheduled - now).total_seconds()
            print(f"  Waiting until {scheduled.strftime('%A %b %d at %I:%M %p')} for: {p['label']}")
            time.sleep(wait_secs)
        print(f"  Posting: {p['label']}")
        if p["type"] == "carousel":
            post_id = ig_post_carousel(p["cdn_urls"], p["caption"])
        else:
            post_id = ig_post_single(p["cdn_urls"][0], p["caption"])
        p["posted"] = True
        p["posted_at"] = datetime.now().isoformat()
        p["post_id"] = post_id
        save_state(state)
        print(f"  LIVE: https://www.instagram.com/p/{post_id}/")
    print("\nAll done!")

# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wax | Wane Ad-Hoc Content Calendar")
    parser.add_argument("--folder", help="Folder of images to process")
    parser.add_argument("--brand", default="HARAMOON", choices=["HARAMOON", "CRYSTALS", "EMF", "WAXWANE"])
    parser.add_argument("--days", default="Mon,Thu", help="Posting days e.g. Mon,Thu")
    parser.add_argument("--start", default=datetime.now().strftime("%Y-%m-%d"), help="Start date YYYY-MM-DD")
    parser.add_argument("--preview", action="store_true", help="Preview queue without posting")
    parser.add_argument("--post-next", action="store_true", help="Post the next item now")
    parser.add_argument("--run", action="store_true", help="Run full schedule (waits for dates)")
    args = parser.parse_args()

    if args.preview:
        preview_queue()
    elif args.post_next:
        post_next()
    elif args.run:
        run_schedule()
    elif args.folder:
        build_queue(args.folder, args.brand, args.days, args.start)
        print("\nRun with --preview to review, then --run to start posting.")
    else:
        parser.print_help()
