#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   BLOG IMAGE PROCESSOR — Permanent Mac Script                               ║
║   Wax|Wane & HARAMOON K-Beauty                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║   WHAT THIS DOES (plain English):                                           ║
║   1. You drop an image into the "input" folder next to this script          ║
║   2. Run this script once from Terminal                                     ║
║   3. It rotates & crops the image to Shopify blog size (1200x628)          ║
║   4. Saves the result to the "output" folder                               ║
║   5. Logs everything to your Google Drive master spreadsheet               ║
║   6. Pushes the processed image to GitHub automatically                    ║
║   That's it. No Manus needed. No tokens spent.                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║   HOW TO RUN (copy-paste into Terminal):                                   ║
║   cd ~/Desktop/blog-image-processor && python3 run_on_mac.py              ║
║                                                                             ║
║   Or with a specific image:                                                ║
║   python3 run_on_mac.py --image my-ingredient-photo.png                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║   FIRST TIME SETUP (one-time only):                                        ║
║   pip3 install Pillow gspread google-auth                                  ║
║   Then fill in your config values in the CONFIG section below              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — Fill these in once. Never change them again unless something breaks.
# ─────────────────────────────────────────────────────────────────────────────

CONFIG = {
    # The ID of your Master Automation Log spreadsheet in Google Drive
    # Find it in the URL: docs.google.com/spreadsheets/d/THIS_PART/edit
    "GOOGLE_SHEET_ID": "1NWx-XcBkO7ps1kVClr0w5crnG3uQAtwZayialUbHqJ8",

    # Path to your Google Service Account JSON key file
    # (See SETUP GUIDE in GitHub for how to get this — it's a one-time download)
    "GOOGLE_CREDENTIALS_FILE": "~/Desktop/blog-image-processor/google-credentials.json",

    # Your GitHub repo details
    "GITHUB_REPO_PATH": "~/shopifycraft",          # Where you cloned the repo on your Mac
    "GITHUB_BRANCH": "samanthanorman-patch-1",

    # Blog image output dimensions (Shopify standard)
    "TARGET_WIDTH": 1200,
    "TARGET_HEIGHT": 628,

    # Rotation: "both" gives you left AND right versions to choose from
    # Change to "right" or "left" if you always know which direction you want
    "ROTATION_DIRECTION": "both",
}

# ─────────────────────────────────────────────────────────────────────────────
# DO NOT EDIT BELOW THIS LINE — This is the engine room
# ─────────────────────────────────────────────────────────────────────────────

import argparse
import os
import sys
import subprocess
import datetime
from pathlib import Path

# Check for required packages
try:
    from PIL import Image
except ImportError:
    print("❌ Missing package: Pillow")
    print("   Fix: pip3 install Pillow")
    sys.exit(1)

try:
    import gspread
    from google.oauth2.service_account import Credentials
    SHEETS_AVAILABLE = True
except ImportError:
    print("⚠️  Google Sheets logging disabled (packages not installed)")
    print("   To enable: pip3 install gspread google-auth")
    SHEETS_AVAILABLE = False


SCRIPT_DIR = Path(__file__).parent.resolve()
INPUT_DIR  = SCRIPT_DIR / "input"
OUTPUT_DIR = SCRIPT_DIR / "output"


def rotate_and_crop(img, direction, target_w, target_h):
    """Rotate image and center-crop to target dimensions."""
    results = []
    rotations = []
    if direction in ("right", "both"):
        rotations.append(("right", img.rotate(-90, expand=True)))
    if direction in ("left", "both"):
        rotations.append(("left", img.rotate(90, expand=True)))

    for label, rotated in rotations:
        orig_w, orig_h = rotated.size
        scale = max(target_w / orig_w, target_h / orig_h)
        new_w, new_h = int(orig_w * scale), int(orig_h * scale)
        resized = rotated.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - target_w) // 2
        top  = (new_h - target_h) // 2
        cropped = resized.crop((left, top, left + target_w, top + target_h))
        results.append((label, cropped))
    return results


def log_to_google_sheets(row_data):
    """Append a row to the 'Images Processed' tab of the master log."""
    if not SHEETS_AVAILABLE:
        print("   (Google Sheets logging skipped — packages not installed)")
        return

    creds_path = Path(CONFIG["GOOGLE_CREDENTIALS_FILE"]).expanduser()
    if not creds_path.exists():
        print(f"   ⚠️  Google credentials file not found at: {creds_path}")
        print("      Sheets logging skipped. See SETUP GUIDE in GitHub.")
        return

    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds  = Credentials.from_service_account_file(str(creds_path), scopes=scopes)
        client = gspread.authorize(creds)
        sheet  = client.open_by_key(CONFIG["GOOGLE_SHEET_ID"])
        ws     = sheet.worksheet("Images Processed")
        ws.append_row(row_data, value_input_option="USER_ENTERED")
        print("   ✅ Logged to Google Sheets")
    except Exception as e:
        print(f"   ⚠️  Sheets logging failed: {e}")


def push_to_github(output_files):
    """Commit and push processed images to GitHub."""
    repo_path = Path(CONFIG["GITHUB_REPO_PATH"]).expanduser()
    if not repo_path.exists():
        print(f"   ⚠️  GitHub repo not found at: {repo_path}")
        print("      Skipping GitHub push. Clone the repo there first.")
        return

    # Copy output files into the repo's output folder
    repo_output = repo_path / "blog-automation" / "blog-image-processor" / "output"
    repo_output.mkdir(parents=True, exist_ok=True)

    import shutil
    for f in output_files:
        dest = repo_output / Path(f).name
        shutil.copy2(f, dest)
        print(f"   Copied to repo: {dest.name}")

    try:
        subprocess.run(["git", "-C", str(repo_path), "add", "blog-automation/"], check=True)
        msg = f"chore: auto-processed blog image(s) {datetime.date.today()} [skip ci]"
        result = subprocess.run(
            ["git", "-C", str(repo_path), "commit", "-m", msg],
            capture_output=True, text=True
        )
        if "nothing to commit" in result.stdout:
            print("   ℹ️  GitHub: nothing new to commit")
            return
        subprocess.run(
            ["git", "-C", str(repo_path), "push", "origin", CONFIG["GITHUB_BRANCH"]],
            check=True
        )
        print("   ✅ Pushed to GitHub")
    except subprocess.CalledProcessError as e:
        print(f"   ⚠️  GitHub push failed: {e}")
        print("      Make sure you've cloned the repo and are logged into GitHub Desktop.")


def main():
    parser = argparse.ArgumentParser(description="Process blog featured image.")
    parser.add_argument("--image",     default=None,  help="Filename in input/ folder")
    parser.add_argument("--direction", default=CONFIG["ROTATION_DIRECTION"],
                        choices=["right", "left", "both"])
    parser.add_argument("--blog",      default="",    help="Blog name (e.g. HARAMOON)")
    parser.add_argument("--title",     default="",    help="Blog post title")
    args = parser.parse_args()

    # Find image to process
    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    if args.image:
        candidates = [INPUT_DIR / args.image]
    else:
        candidates = sorted(INPUT_DIR.glob("*.png")) + \
                     sorted(INPUT_DIR.glob("*.jpg")) + \
                     sorted(INPUT_DIR.glob("*.jpeg")) + \
                     sorted(INPUT_DIR.glob("*.webp"))
        candidates = [c for c in candidates if c.name != ".gitkeep"]

    if not candidates:
        print("❌ No images found in the input/ folder.")
        print(f"   Drop an image into: {INPUT_DIR}")
        sys.exit(1)

    input_path = candidates[0]
    print(f"\n🖼️  Processing: {input_path.name}")
    print(f"   Direction: {args.direction}")
    print(f"   Target: {CONFIG['TARGET_WIDTH']}x{CONFIG['TARGET_HEIGHT']}px")
    print("-" * 60)

    img = Image.open(input_path)
    original_size = img.size
    results = rotate_and_crop(img, args.direction, CONFIG["TARGET_WIDTH"], CONFIG["TARGET_HEIGHT"])

    output_files = []
    for label, cropped in results:
        out_name = f"{input_path.stem}_blog_{label}.png"
        out_path = OUTPUT_DIR / out_name
        cropped.save(out_path)
        print(f"   ✅ Saved ({label}): {out_name}")
        output_files.append(str(out_path))

    print("-" * 60)

    # Log to Google Sheets
    print("📊 Logging to Google Sheets...")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    output_right = next((Path(f).name for f in output_files if "_right" in f), "")
    output_left  = next((Path(f).name for f in output_files if "_left"  in f), "")
    row = [
        now,
        input_path.name,
        "",  # Drive link (original) — fill manually or via Manus
        args.direction,
        output_right,
        output_left,
        "",  # Drive link (processed) — fill manually or via Manus
        f"{CONFIG['TARGET_WIDTH']}x{CONFIG['TARGET_HEIGHT']}",
        "Blog Featured Image",
        args.title or "",
        "",  # Notes
    ]
    log_to_google_sheets(row)

    # Push to GitHub
    print("🐙 Pushing to GitHub...")
    push_to_github(output_files)

    print("\n🎉 Done!")
    print(f"   Output folder: {OUTPUT_DIR}")
    print(f"   Log: https://docs.google.com/spreadsheets/d/{CONFIG['GOOGLE_SHEET_ID']}/edit")


if __name__ == "__main__":
    main()
