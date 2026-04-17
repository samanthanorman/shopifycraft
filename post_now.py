#!/usr/bin/env python3
"""
HARAMOON Instagram Batch Poster
================================
Run this script on your Mac to post 5 HARAMOON posts to @waxandwane Instagram.
Posts are staggered 48 hours apart starting from whenever you run this.

SETUP (one time only):
  1. Find your Instagram token:
       grep -r "INSTAGRAM\|IG_TOKEN\|access_token" ~/.env ~/automations ~/Desktop 2>/dev/null | head -20
  2. Set it below OR export it in terminal first:
       export IG_TOKEN="your_token_here"
       export IG_USER_ID="your_instagram_user_id"

USAGE:
  python3 post_now.py              # Schedule all 5 posts (48hr apart)
  python3 post_now.py --now        # Post the next unposted one immediately
  python3 post_now.py --preview    # Show all posts without posting
  python3 post_now.py --status     # Show what's been posted vs pending
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path

# ─────────────────────────────────────────────
# CONFIGURATION — edit these if needed
# ─────────────────────────────────────────────
# Wax | Wane credentials (confirmed working Apr 17 2026)
# Instagram: @waxandwane.store (ID: 17841458399612807) linked to Niche Wellness Facebook Page
# Token: Meta Conversions API System User token — has full Instagram + Facebook posting rights
IG_TOKEN   = os.environ.get("IG_TOKEN",   "EAASgzu1LdvABRJPUrCLFfT6SBuUyeJu3QV2PQexpOE7Xfvlo0rvdbIQVzdZCEp7eqDo7vxegIn8y52cnLYCntTHKE3mlx4fhoECAyp0SanD0Ju9XCdRFEBzCKdSUE0nB5SHuAndO6dNJEz0VVjTvvscTVTaffV8twSu1gLBk0ZCt0DYtkG0gSE1sZBcJQZDZD")
IG_USER_ID = os.environ.get("IG_USER_ID", "17841458399612807")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "203171376205580")  # Niche Wellness Facebook Page
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN", "EAASgzu1LdvABRFou790AZAdQdTlernJZACPM0dRcDgP12LiNhHFND1ztu01Hr8CnkW4sH9zvivJqRi5rQryscOio5KFXO2xRZCPYonnZBFVfO4lJZB9LUq8NdGjtT9dHHDTv8woZAEYUFoaDz6FmBSRlKdfP20HZBsZBEq1MH4w4uWIMJTRzKZB1fso3ZB7xOKZCFNzBq502jMZD")
STATE_FILE = Path.home() / ".haramoon_posts_state.json"

# ─────────────────────────────────────────────
# THE 5 POSTS (images already on CDN, captions written)
# ─────────────────────────────────────────────
POSTS = [
    {
        "id": "post_1_peptides_carousel",
        "label": "Peptides vs Ceramides vs Niacinamide (Carousel)",
        "type": "carousel",
        "images": [
            "https://files.manuscdn.com/user_upload_by_module/session_file/310419663029718527/VBKRempSIzxClHdn.jpg",
            "https://files.manuscdn.com/user_upload_by_module/session_file/310419663029718527/LEobRARgFOCICxQa.jpg",
            "https://files.manuscdn.com/user_upload_by_module/session_file/310419663029718527/PbQOljIDrYUpeXUW.jpg",
        ],
        "caption": (
            "Your skin barrier runs on three ingredients. Here's what each one actually does — "
            "and why HARAMOON formulas are built around all three.\n\n"
            "Swipe to learn the science behind the skin barrier.\n\n"
            "#KoreanSkincare #SkincareScience #Peptides #Ceramides #Niacinamide "
            "#SkinBarrier #HARAMOONSkincare #CleanBeauty #EWGVerified #VeganSkincare "
            "#KBeauty #IngredientNerd\n\n"
            "Shop at https://www.waxandwane.store | Also on Amazon: "
            "https://www.amazon.com/stores/HaramoonUSA/page/4D229D57-2C46-409B-8ECB-ABECAA03B46D"
        ),
    },
    {
        "id": "post_2_deep_sea_toner",
        "label": "Deep Sea Water Toner Infographic",
        "type": "single",
        "images": [
            "https://files.manuscdn.com/user_upload_by_module/session_file/310419663029718527/mWKuwwOWNCcWOHnY.jpg",
        ],
        "caption": (
            "7 types of hyaluronic acid. Deep sea minerals. pH 5.5. EWG Verified. Vegan.\n\n"
            "The HARAMOON Derma Super Dam Toner doesn't just hydrate — it rebuilds your moisture barrier "
            "from the inside out. One layer at a time.\n\n"
            "#DeepSeaWater #HyaluronicAcid #KoreanToner #SkinBarrier #HARAMOON "
            "#KBeautyToner #pH55 #EWGVerified #VeganSkincare #KoreanSkincare\n\n"
            "Shop at https://www.waxandwane.store | Also on Amazon: "
            "https://www.amazon.com/stores/HaramoonUSA/page/4D229D57-2C46-409B-8ECB-ABECAA03B46D"
        ),
    },
    {
        "id": "post_3_strongest_barrier",
        "label": "Your Skin's Strongest Barrier — Dam Cream",
        "type": "single",
        "images": [
            "https://files.manuscdn.com/user_upload_by_module/session_file/310419663029718527/fMuEElMChJZZDQlv.jpg",
        ],
        "caption": (
            "Modern stressors — pollution, blue light, stress — are quietly wrecking your skin barrier every day.\n\n"
            "The HARAMOON Derma Limpide Dam Cream was formulated for exactly that. Science-backed hydration "
            "that protects, repairs, and holds.\n\n"
            "#SkinBarrier #BarrierRepair #HARAMOON #KoreanMoisturizer #CentellaCream "
            "#KBeauty #SensitiveSkin #CleanBeauty #VeganSkincare #KoreanSkincare\n\n"
            "Shop at https://www.waxandwane.store | Also on Amazon: "
            "https://www.amazon.com/stores/HaramoonUSA/page/4D229D57-2C46-409B-8ECB-ABECAA03B46D"
        ),
    },
    {
        "id": "post_4_routine_carousel",
        "label": "The Full HARAMOON Routine (Carousel)",
        "type": "carousel",
        "images": [
            "https://files.manuscdn.com/user_upload_by_module/session_file/310419663029718527/qpqyYSnbgcXeSFPZ.jpg",
            "https://files.manuscdn.com/user_upload_by_module/session_file/310419663029718527/eVyogaJCsbEYktVq.jpg",
        ],
        "caption": (
            "Cleanse without stripping. Hydrate without heaviness. Protect without clogging.\n\n"
            "The complete HARAMOON skin barrier routine — 4 steps, all EWG Verified, all pH 5.5 balanced. "
            "Swipe for the full lineup.\n\n"
            "#KoreanSkincareRoutine #SkinBarrierSolution #HARAMOON #4StepSkincare "
            "#KBeautyRoutine #PHBalanced #EWGVerified #VeganSkincare #KoreanSkincare #CleanBeauty\n\n"
            "Shop at https://www.waxandwane.store | Also on Amazon: "
            "https://www.amazon.com/stores/HaramoonUSA/page/4D229D57-2C46-409B-8ECB-ABECAA03B46D"
        ),
    },
    {
        "id": "post_5_ph55_reset",
        "label": "The pH 5.5 Reset — Super Dam Toner",
        "type": "single",
        "images": [
            "https://files.manuscdn.com/user_upload_by_module/session_file/310419663029718527/XvvtWNEipNjqUPvr.jpg",
        ],
        "caption": (
            "Jeju mineral water meets 7-layer hyaluronic acid. Swipe to refresh. Pat to hydrate.\n\n"
            "The HARAMOON Super Dam Toner resets your skin's pH to 5.5 — the sweet spot for barrier health — "
            "while flooding every layer with moisture.\n\n"
            "#pH55Toner #JejuWater #HyaluronicAcid #HARAMOON #KoreanToner "
            "#SkinReset #KBeauty #BarrierCare #VeganSkincare #KoreanSkincare\n\n"
            "Shop at https://www.waxandwane.store | Also on Amazon: "
            "https://www.amazon.com/stores/HaramoonUSA/page/4D229D57-2C46-409B-8ECB-ABECAA03B46D"
        ),
    },
]

# ─────────────────────────────────────────────
# EMAIL ERROR NOTIFICATIONS
# Set NOTIFY_EMAIL to your email to get alerts when a post fails
# ─────────────────────────────────────────────
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "")  # e.g. "samantha@gmail.com"

def send_error_email(subject, body):
    """Send an error notification email using Gmail SMTP (no extra setup needed)."""
    if not NOTIFY_EMAIL:
        return
    import smtplib
    from email.mime.text import MIMEText
    # Uses macOS sendmail or Gmail app password
    # To enable: set GMAIL_APP_PASSWORD env var (Settings > Security > App Passwords)
    gmail_user = os.environ.get("GMAIL_USER", NOTIFY_EMAIL)
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not gmail_pass:
        # Fallback: try macOS sendmail
        import subprocess
        msg = f"Subject: {subject}\n\n{body}"
        try:
            subprocess.run(["sendmail", NOTIFY_EMAIL], input=msg.encode(), timeout=10)
        except Exception:
            pass
        return
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = gmail_user
        msg["To"] = NOTIFY_EMAIL
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(gmail_user, gmail_pass)
            s.send_message(msg)
        print(f"  Email alert sent to {NOTIFY_EMAIL}")
    except Exception as e:
        print(f"  Email alert failed: {e}")

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))

def ig_post_single(image_url, caption):
    """Post a single image to Instagram via Graph API."""
    # Step 1: Create container
    r = requests.post(
        f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media",
        data={"image_url": image_url, "caption": caption, "access_token": IG_TOKEN}
    )
    r.raise_for_status()
    container_id = r.json()["id"]
    time.sleep(3)
    # Step 2: Publish
    r2 = requests.post(
        f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish",
        data={"creation_id": container_id, "access_token": IG_TOKEN}
    )
    r2.raise_for_status()
    return r2.json().get("id")

def ig_post_carousel(image_urls, caption):
    """Post a carousel to Instagram via Graph API."""
    child_ids = []
    for url in image_urls:
        r = requests.post(
            f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media",
            data={"image_url": url, "is_carousel_item": "true", "access_token": IG_TOKEN}
        )
        r.raise_for_status()
        child_ids.append(r.json()["id"])
        time.sleep(2)
    # Create carousel container
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
    # Publish
    r3 = requests.post(
        f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish",
        data={"creation_id": container_id, "access_token": IG_TOKEN}
    )
    r3.raise_for_status()
    return r3.json().get("id")

def fb_post(image_url, caption):
    """Cross-post a single image to the Niche Wellness Facebook Page."""
    try:
        r = requests.post(
            f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos",
            data={"url": image_url, "caption": caption, "access_token": FB_PAGE_TOKEN}
        )
        if r.status_code == 200:
            fb_id = r.json().get("post_id", r.json().get("id", ""))
            print(f"  Facebook: https://www.facebook.com/{FB_PAGE_ID}/posts/{fb_id.split('_')[-1] if '_' in str(fb_id) else fb_id}")
        else:
            print(f"  Facebook: skipped ({r.status_code} — {r.json().get('error', {}).get('message', 'unknown error')})")
    except Exception as e:
        print(f"  Facebook: skipped (error: {e})")

def post_it(post):
    """Post a single post object to Instagram + Facebook."""
    print(f"\n  Posting: {post['label']} ...")
    try:
        if post["type"] == "carousel":
            post_id = ig_post_carousel(post["images"], post["caption"])
        else:
            post_id = ig_post_single(post["images"][0], post["caption"])
        print(f"  Instagram: https://www.instagram.com/p/{post_id}/")
        # Cross-post first image to Facebook too
        fb_post(post["images"][0], post["caption"])
        return post_id
    except Exception as e:
        err_msg = f"Post failed: {post['label']}\nError: {e}\nTime: {datetime.now().isoformat()}"
        print(f"  ERROR: {e}")
        send_error_email(f"[HARAMOON] Post Failed: {post['label']}", err_msg)
        raise

# ─────────────────────────────────────────────
# MODES
# ─────────────────────────────────────────────

def preview():
    print("\n===== PREVIEW: 5 HARAMOON Posts =====\n")
    for i, p in enumerate(POSTS, 1):
        print(f"Post {i}: {p['label']} ({p['type']}, {len(p['images'])} image(s))")
        print(f"  Caption preview: {p['caption'][:120]}...")
        print()

def status():
    state = load_state()
    print("\n===== POST STATUS =====\n")
    for i, p in enumerate(POSTS, 1):
        s = state.get(p["id"])
        if s:
            print(f"  [{i}] POSTED  — {p['label']}")
            print(f"       Posted at: {s.get('posted_at')} | ID: {s.get('post_id')}")
        else:
            print(f"  [{i}] PENDING — {p['label']}")
    print()

def post_next_now():
    """Post the next unposted item immediately."""
    if not IG_TOKEN or not IG_USER_ID:
        print("\nERROR: IG_TOKEN and IG_USER_ID must be set.")
        print("Run:  export IG_TOKEN='your_token'  &&  export IG_USER_ID='your_id'")
        sys.exit(1)
    state = load_state()
    for p in POSTS:
        if p["id"] not in state:
            post_id = post_it(p)
            state[p["id"]] = {"posted_at": datetime.now().isoformat(), "post_id": post_id}
            save_state(state)
            print(f"\n  Done! Run again to post the next one.")
            return
    print("\n  All 5 posts have already been published!")

def schedule_all():
    """Schedule all 5 posts 48 hours apart using macOS launchd or simple sleep loop."""
    if not IG_TOKEN or not IG_USER_ID:
        print("\nERROR: IG_TOKEN and IG_USER_ID must be set.")
        print("Run:  export IG_TOKEN='your_token'  &&  export IG_USER_ID='your_id'")
        sys.exit(1)
    state = load_state()
    pending = [p for p in POSTS if p["id"] not in state]
    if not pending:
        print("\nAll 5 posts already published!")
        return
    print(f"\nScheduling {len(pending)} posts, 48 hours apart.")
    print("Keep this terminal window open (or run with: nohup python3 post_now.py &)\n")
    for i, p in enumerate(pending):
        if i > 0:
            wait_hours = 48
            print(f"\n  Waiting {wait_hours} hours before next post...")
            time.sleep(wait_hours * 3600)
        post_id = post_it(p)
        state[p["id"]] = {"posted_at": datetime.now().isoformat(), "post_id": post_id}
        save_state(state)
    print("\n  All posts published!")

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "--preview":
        preview()
    elif arg == "--status":
        status()
    elif arg == "--now":
        post_next_now()
    else:
        schedule_all()
