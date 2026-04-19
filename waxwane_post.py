#!/usr/bin/env python3
"""
Wax | Wane — Run-Whenever Queue Poster
=======================================
Posts the next item from your queue to Instagram + Facebook.
Run it whenever you want — it picks up where it left off.

SETUP (one time only on your Mac):
  Run this in terminal:
    echo 'source ~/.waxwane_env' >> ~/.zshrc && source ~/.zshrc

  Then create ~/.waxwane_env with your tokens (already done if you ran setup):
    cat ~/.waxwane_env

USAGE:
  python3 ~/waxwane_post.py            # Post the next item in the queue
  python3 ~/waxwane_post.py --preview  # Preview all pending posts
  python3 ~/waxwane_post.py --status   # Show what's posted vs pending
  python3 ~/waxwane_post.py --list     # List all posts in queue with numbers
  python3 ~/waxwane_post.py --skip     # Skip the next post (mark as skipped)

QUEUE FILE:
  ~/waxwane_queue.json — edit this to add new posts anytime
  Each post needs: id, brand, label, type (single/carousel), images (list of URLs), caption
"""

import os
import sys
import json
import time
import requests
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────
# CREDENTIALS (hardcoded + env override)
# ─────────────────────────────────────────────
IG_TOKEN      = os.environ.get("IG_TOKEN",      "EAASgzu1LdvABRJPUrCLFfT6SBuUyeJu3QV2PQexpOE7Xfvlo0rvdbIQVzdZCEp7eqDo7vxegIn8y52cnLYCntTHKE3mlx4fhoECAyp0SanD0Ju9XCdRFEBzCKdSUE0nB5SHuAndO6dNJEz0VVjTvvscTVTaffV8twSu1gLBk0ZCt0DYtkG0gSE1sZBcJQZDZD")
IG_USER_ID    = os.environ.get("IG_USER_ID",    "17841458399612807")
FB_PAGE_ID    = os.environ.get("FB_PAGE_ID",    "203171376205580")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN", "EAASgzu1LdvABRFou790AZAdQdTlernJZACPM0dRcDgP12LiNhHFND1ztu01Hr8CnkW4sH9zvivJqRi5rQryscOio5KFXO2xRZCPYonnZBFVfO4lJZB9LUq8NdGjtT9dHHDTv8woZAEYUFoaDz6FmBSRlKdfP20HZBsZBEq1MH4w4uWIMJTRzKZB1fso3ZB7xOKZCFNzBq502jMZD")

QUEUE_FILE = Path.home() / "waxwane_queue.json"
STATE_FILE = Path.home() / ".waxwane_post_state.json"

# ─────────────────────────────────────────────
# RETRY HELPER — survives WiFi blips
# ─────────────────────────────────────────────
def api_post(url, data, retries=4, backoff=10):
    """POST with automatic retry on connection errors."""
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(url, data=data, timeout=30)
            r.raise_for_status()
            return r
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout):
            if attempt == retries:
                raise
            wait = backoff * attempt
            print(f"  Network hiccup (attempt {attempt}/{retries}). Retrying in {wait}s...")
            time.sleep(wait)
        except requests.exceptions.HTTPError:
            raise

# ─────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────
def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))

def load_queue():
    if not QUEUE_FILE.exists():
        print(f"\n  No queue file found at {QUEUE_FILE}")
        print("  Ask Manus to build you a new queue batch, or create waxwane_queue.json manually.")
        sys.exit(0)
    return json.loads(QUEUE_FILE.read_text())

# ─────────────────────────────────────────────
# POSTING
# ─────────────────────────────────────────────
def ig_post_single(image_url, caption):
    r = api_post(
        f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media",
        data={"image_url": image_url, "caption": caption, "access_token": IG_TOKEN}
    )
    container_id = r.json()["id"]
    time.sleep(3)
    r2 = api_post(
        f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish",
        data={"creation_id": container_id, "access_token": IG_TOKEN}
    )
    return r2.json().get("id")

def ig_post_carousel(image_urls, caption):
    child_ids = []
    for url in image_urls:
        r = api_post(
            f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media",
            data={"image_url": url, "is_carousel_item": "true", "access_token": IG_TOKEN}
        )
        child_ids.append(r.json()["id"])
        time.sleep(2)
    r2 = api_post(
        f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media",
        data={
            "media_type": "CAROUSEL",
            "children": ",".join(child_ids),
            "caption": caption,
            "access_token": IG_TOKEN
        }
    )
    container_id = r2.json()["id"]
    time.sleep(3)
    r3 = api_post(
        f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish",
        data={"creation_id": container_id, "access_token": IG_TOKEN}
    )
    return r3.json().get("id")

def fb_post(image_url, caption):
    try:
        r = api_post(
            f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos",
            data={"url": image_url, "caption": caption, "access_token": FB_PAGE_TOKEN}
        )
        fb_id = r.json().get("post_id", r.json().get("id", ""))
        print(f"  Facebook: https://www.facebook.com/{FB_PAGE_ID}/posts/{fb_id.split('_')[-1] if '_' in str(fb_id) else fb_id}")
    except Exception as e:
        print(f"  Facebook: skipped ({e})")

def post_it(post):
    print(f"\n  [{post.get('brand','Wax|Wane')}] Posting: {post['label']} ...")
    try:
        if post["type"] == "carousel":
            post_id = ig_post_carousel(post["images"], post["caption"])
        else:
            post_id = ig_post_single(post["images"][0], post["caption"])
        print(f"  Instagram: https://www.instagram.com/p/{post_id}/")
        fb_post(post["images"][0], post["caption"])
        return post_id
    except Exception as e:
        print(f"\n  ERROR posting {post['label']}: {e}")
        raise

# ─────────────────────────────────────────────
# MODES
# ─────────────────────────────────────────────
def preview():
    posts = load_queue()
    state = load_state()
    pending = [p for p in posts if p["id"] not in state]
    done    = [p for p in posts if p["id"] in state and state[p["id"]].get("status") == "posted"]
    skipped = [p for p in posts if p["id"] in state and state[p["id"]].get("status") == "skipped"]
    print(f"\n===== WAX|WANE QUEUE PREVIEW =====")
    print(f"  Total: {len(posts)} | Pending: {len(pending)} | Posted: {len(done)} | Skipped: {len(skipped)}\n")
    for i, p in enumerate(posts, 1):
        s = state.get(p["id"])
        if s and s.get("status") == "posted":
            tag = "POSTED "
        elif s and s.get("status") == "skipped":
            tag = "SKIPPED"
        else:
            tag = "PENDING"
        brand = p.get("brand", "Wax|Wane")
        print(f"  [{i:02d}] {tag} | {brand:10s} | {p['label'][:55]}")
        if not s:
            print(f"         Caption: {p['caption'][:90]}...")
    print()

def status():
    posts = load_queue()
    state = load_state()
    pending = [p for p in posts if p["id"] not in state]
    done    = [p for p in posts if p["id"] in state and state[p["id"]].get("status") == "posted"]
    print(f"\n===== WAX|WANE POST STATUS =====")
    print(f"  {len(done)} posted | {len(pending)} pending\n")
    for p in done:
        s = state[p["id"]]
        print(f"  POSTED  {p['label'][:50]} — {s.get('posted_at','')[:10]}")
    for p in pending:
        print(f"  PENDING {p['label'][:50]}")
    print()

def list_queue():
    posts = load_queue()
    state = load_state()
    print(f"\n===== QUEUE ({len(posts)} items) =====\n")
    for i, p in enumerate(posts, 1):
        s = state.get(p["id"])
        tag = "POSTED" if (s and s.get("status") == "posted") else ("SKIP" if (s and s.get("status") == "skipped") else "next" if not any(p2["id"] not in state for p2 in posts[:i-1]) else "    ")
        print(f"  {i:02d}. [{tag:6s}] {p.get('brand',''):10s} {p['label'][:50]}")
    print()

def post_next():
    posts = load_queue()
    state = load_state()
    for p in posts:
        if p["id"] not in state:
            post_id = post_it(p)
            state[p["id"]] = {
                "status": "posted",
                "posted_at": datetime.now().isoformat(),
                "post_id": post_id
            }
            save_state(state)
            remaining = sum(1 for x in posts if x["id"] not in state)
            print(f"\n  Done! {remaining} posts remaining in queue.")
            print(f"  Run again to post the next one.")
            return
    print("\n  All posts in queue have been published!")
    print(f"  Ask Manus to build a new batch and drop it in {QUEUE_FILE}")

def skip_next():
    posts = load_queue()
    state = load_state()
    for p in posts:
        if p["id"] not in state:
            state[p["id"]] = {"status": "skipped", "skipped_at": datetime.now().isoformat()}
            save_state(state)
            print(f"\n  Skipped: {p['label']}")
            print(f"  Run again to post the next one.")
            return
    print("\n  Nothing to skip — queue is empty.")

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "--preview":
        preview()
    elif arg == "--status":
        status()
    elif arg == "--list":
        list_queue()
    elif arg == "--skip":
        skip_next()
    else:
        post_next()
