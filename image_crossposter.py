#!/usr/bin/env python3
"""
image_crossposter.py — Wax | Wane Smart Cross-Poster
=====================================================
Drop images into a folder (or pass them as arguments), and this script:
  1. Detects each image's aspect ratio
  2. Routes it to the correct platforms based on size rules
  3. Generates a platform-appropriate caption per channel
  4. Posts to Pinterest, Facebook, Instagram, and/or LinkedIn
  5. Logs everything to crossposter.log

USAGE (on your Mac):
  python3 image_crossposter.py --images /path/to/img1.png /path/to/img2.jpg \\
                                --topic emf \\
                                --link https://waxandwane.store/collections/emf-protection

TOPICS: emf | crystals | haramoon | wax

CHANNEL ROUTING BY ASPECT RATIO:
  9:16 tall portrait  -> Pinterest only (Stories-style, too tall for IG feed)
  4:5 portrait        -> Pinterest + Instagram + Facebook
  1:1 square          -> Pinterest + Instagram + Facebook + LinkedIn
  16:9 landscape      -> Pinterest + Facebook + LinkedIn (NOT Instagram — IG crops badly)
  4:3 landscape       -> Pinterest + Facebook + LinkedIn
"""

import os, sys, json, time, logging, argparse, textwrap, requests, base64
from pathlib import Path
from PIL import Image
from dotenv import load_dotenv
from datetime import datetime

# ─── Setup ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
logging.basicConfig(
    filename=BASE_DIR / "crossposter.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ─── Credentials ──────────────────────────────────────────────────────────────
PINTEREST_TOKEN  = os.getenv("PINTEREST_ACCESS_TOKEN", "")
FB_PAGE_ID       = os.getenv("FACEBOOK_PAGE_ID", "")
FB_PAGE_TOKEN    = os.getenv("FACEBOOK_PAGE_TOKEN", "")
IG_USER_ID       = os.getenv("INSTAGRAM_USER_ID", "")
IG_TOKEN         = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
ENABLE_PINTEREST = os.getenv("ENABLE_PINTEREST", "true").lower() == "true"
ENABLE_FACEBOOK  = os.getenv("ENABLE_FACEBOOK", "true").lower() == "true"
ENABLE_INSTAGRAM = os.getenv("ENABLE_INSTAGRAM", "true").lower() == "true"
ENABLE_LINKEDIN  = os.getenv("ENABLE_LINKEDIN", "false").lower() == "true"
LINKEDIN_TOKEN   = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_ORG_ID  = os.getenv("LINKEDIN_ORG_ID", "")

# ─── Pinterest Board IDs ───────────────────────────────────────────────────────
PINTEREST_BOARDS = {
    "emf":      os.getenv("PINTEREST_BOARD_EMF",      "1095148903078119084"),
    "crystals": os.getenv("PINTEREST_BOARD_CRYSTALS", "1095148903077985940"),
    "haramoon": os.getenv("PINTEREST_BOARD_HARAMOON", "1095148903077903600"),
    "wax":      os.getenv("PINTEREST_BOARD_WAX_WANE", "1095148903077605529"),
}

# ─── Caption Templates ────────────────────────────────────────────────────────
CAPTIONS = {
    "emf": {
        "pinterest": (
            "{title}\n\n"
            "Your devices are always on — and so is the invisible energy they emit. "
            "EMF-protective cases and shielding textiles that actually work, backed by science. "
            "Shop the collection at waxandwane.store\n\n"
            "#EMFProtection #EMFShielding #EMFAwareness #DigitalWellness "
            "#5GProtection #WifiRadiation #ShieldingTextiles #WaxAndWane"
        ),
        "instagram": (
            "{title}\n\n"
            "Your phone is always on. So is the invisible energy it emits. "
            "We carry science-backed EMF shielding — cases, pouches, and textiles "
            "that actually reduce your exposure. Link in bio.\n\n"
            "#EMF #EMFProtection #DigitalWellness #WaxAndWane"
        ),
        "facebook": (
            "{title}\n\n"
            "Did you know your Wi-Fi router, phone, and smart meter emit electromagnetic fields "
            "24 hours a day? The science on long-term exposure is still developing — "
            "but the precautionary options are here now.\n\n"
            "Explore our EMF shielding collection: {link}\n\n"
            "#EMFProtection #EMFAwareness #WaxAndWane #DigitalHealth"
        ),
        "linkedin": (
            "{title}\n\n"
            "As smart devices proliferate in homes and workplaces, awareness of electromagnetic "
            "field (EMF) exposure is growing. Shielding textiles using conductive silver-ink mesh "
            "have demonstrated >30 dB reduction in lab testing — qualifying as 'excellent' for "
            "general EMI applications.\n\n"
            "Wax | Wane carries a curated selection of science-backed EMF protection products: {link}\n\n"
            "#EMF #ElectromagneticHealth #WellnessTech #FutureOfWork"
        ),
    },
    "crystals": {
        "pinterest": (
            "{title}\n\n"
            "Every crystal carries a story written over millions of years. "
            "Ethically sourced minerals, raw specimens, and crystal home decor. "
            "Shop at waxandwane.store\n\n"
            "#Crystals #CrystalHealing #Minerals #Shungite #CrystalCollector "
            "#WaxAndWane #CrystalShop"
        ),
        "instagram": (
            "{title}\n\n"
            "Millions of years in the making. Ethically sourced crystals and minerals "
            "for your space and practice. Link in bio.\n\n"
            "#Crystals #CrystalHealing #Shungite #WaxAndWane"
        ),
        "facebook": (
            "{title}\n\n"
            "From Shungite mined in Karelia, Russia to raw Selenite towers — "
            "every piece in our crystal collection is ethically sourced and chosen "
            "for both beauty and energetic quality.\n\n"
            "Browse the collection: {link}\n\n"
            "#Crystals #CrystalHealing #WaxAndWane"
        ),
        "linkedin": (
            "{title}\n\n"
            "The wellness and crystal market continues to grow as consumers seek "
            "grounding and intentional living practices. Wax | Wane curates ethically "
            "sourced minerals and crystal specimens for home, office, and personal use.\n\n"
            "{link}\n\n"
            "#WellnessTrends #CrystalWellness #EthicalSourcing"
        ),
    },
    "haramoon": {
        "pinterest": (
            "{title}\n\n"
            "Korean dermatology meets clean beauty. HARAMOON — fragrance-free, "
            "vegan, EWG-verified skincare formulated for sensitive and reactive skin. "
            "Shop at waxandwane.store\n\n"
            "#HARAMOON #KoreanSkincare #GlassSkin #CleanBeauty #VeganSkincare "
            "#KBeauty #FragranceFree #WaxAndWane"
        ),
        "instagram": (
            "{title}\n\n"
            "Glass skin starts with the right routine. HARAMOON — Korean derma cosmetics, "
            "fragrance-free, vegan, EWG verified. Link in bio.\n\n"
            "#HARAMOON #KoreanSkincare #GlassSkin #WaxAndWane"
        ),
        "facebook": (
            "{title}\n\n"
            "HARAMOON is Korean skincare built for sensitive skin — no fragrance, "
            "no parabens, EWG verified, and pH balanced. The kind of formula your skin "
            "actually wants.\n\n"
            "Shop HARAMOON: {link}\n\n"
            "#HARAMOON #KBeauty #KoreanSkincare #WaxAndWane"
        ),
        "linkedin": (
            "{title}\n\n"
            "The global K-beauty market is projected to reach $21B by 2026. "
            "HARAMOON brings Korean dermatology-grade skincare to the US market — "
            "fragrance-free, vegan, and EWG verified. Available exclusively through Wax | Wane.\n\n"
            "{link}\n\n"
            "#KBeauty #KoreanSkincare #BeautyIndustry #WaxAndWane"
        ),
    },
    "wax": {
        "pinterest": (
            "{title}\n\n"
            "Wax | Wane — where crystals, clean beauty, and EMF protection meet. "
            "Curated for the curious, the intentional, and the beautifully weird. "
            "Shop at waxandwane.store\n\n"
            "#WaxAndWane #CrystalShop #EMFProtection #KBeauty #IntentionalLiving"
        ),
        "instagram": (
            "{title}\n\n"
            "Crystals. Clean beauty. EMF protection. All in one place. "
            "Wax | Wane — shop the link in bio.\n\n"
            "#WaxAndWane #IntentionalLiving #CrystalShop"
        ),
        "facebook": (
            "{title}\n\n"
            "Wax | Wane is your one-stop shop for crystals, Korean skincare, "
            "and EMF protection products — all ethically sourced and science-informed.\n\n"
            "Shop now: {link}\n\n"
            "#WaxAndWane #CrystalShop #EMFProtection #HARAMOON"
        ),
        "linkedin": (
            "{title}\n\n"
            "Wax | Wane is a modern wellness brand at the intersection of crystal science, "
            "clean Korean beauty, and EMF protection. Available on Shopify, Amazon, Walmart, "
            "TikTok Shop, and Pinterest.\n\n"
            "{link}\n\n"
            "#WellnessBrand #Ecommerce #WaxAndWane"
        ),
    },
}

# ─── Default product links per topic ──────────────────────────────────────────
DEFAULT_LINKS = {
    "emf":      "https://waxandwane.store/collections/emf-protection",
    "crystals": "https://waxandwane.store/collections/crystals",
    "haramoon": "https://waxandwane.store/collections/haramoon",
    "wax":      "https://waxandwane.store",
}

# ─── Smart Title + Alt Text Helpers ─────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

def _read_image_title(path, topic):
    """Use Gemini vision to extract the headline/title text from the image.
    Falls back to a clean filename-based title if Gemini is unavailable."""
    fallback = str(path.stem).replace("_", " ").replace("-", " ").title()
    if not GEMINI_API_KEY:
        return fallback
    try:
        with open(str(path), "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        # Detect mime type
        suffix = path.suffix.lower()
        mime = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                '.webp': 'image/webp', '.gif': 'image/gif'}.get(suffix, 'image/jpeg')
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Read the main headline or title text from this image. Return ONLY the title text, nothing else. If there is no clear title, return a 5-7 word description of what the image is about."},
                    {"inline_data": {"mime_type": mime, "data": img_b64}}
                ]
            }]
        }
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
            json=payload, timeout=20
        )
        if r.status_code == 200:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            # Clean up: remove quotes, limit length
            text = text.strip('"\' \n').split('\n')[0][:120]
            log.info(f"Gemini title: {text}")
            return text
    except Exception as e:
        log.warning(f"Gemini title extraction failed: {e}")
    return fallback


ALT_TEXT_TEMPLATES = {
    "emf":      "{title} — EMF shielding and protection products from Wax and Wane",
    "crystals": "{title} — ethically sourced crystals and minerals from Wax and Wane",
    "haramoon": "{title} — HARAMOON Korean derma skincare from Wax and Wane",
    "wax":      "{title} — Wax and Wane wellness store",
}

def _build_alt_text(title, topic, filename):
    """Build descriptive, SEO-rich alt text for the image."""
    template = ALT_TEXT_TEMPLATES.get(topic, ALT_TEXT_TEMPLATES["wax"])
    return template.format(title=title)[:500]


# ─── Routing Rules ────────────────────────────────────────────────────────────
def detect_ratio(path):
    """Returns a ratio label based on image dimensions."""
    img = Image.open(path)
    w, h = img.size
    ratio = w / h
    if ratio > 1.7:
        return "16:9"
    elif ratio > 1.1:
        return "4:3"
    elif ratio > 0.9:
        return "1:1"
    elif ratio > 0.7:
        return "4:5"
    else:
        return "9:16"

ROUTING = {
    # ratio    : (pinterest, instagram, facebook, linkedin)
    "9:16":     (True,  False, False, False),
    "4:5":      (True,  True,  True,  False),
    "1:1":      (True,  True,  True,  True),
    "16:9":     (True,  False, True,  True),
    "4:3":      (True,  False, True,  True),
}

# ─── Upload helpers ────────────────────────────────────────────────────────────
def upload_image_to_imgur(path):
    """Upload image to Imgur (anonymous, free) and return public URL.
    Auto-converts .webp to .jpg since Imgur does not accept webp."""
    path = str(path)
    if path.lower().endswith('.webp'):
        from PIL import Image as _PIL
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        tmp.close()
        _PIL.open(path).convert('RGB').save(tmp.name, 'JPEG', quality=92)
        path = tmp.name
    with open(path, "rb") as f:
        data = f.read()
    r = requests.post(
        "https://api.imgur.com/3/image",
        headers={"Authorization": "Client-ID 546c25a59c58ad7"},
        files={"image": data},
        timeout=30,
    )
    if r.status_code == 200:
        url = r.json()["data"]["link"]
        log.info(f"Imgur upload OK: {url}")
        return url
    log.error(f"Imgur upload failed: {r.status_code} {r.text[:200]}")
    return None

# ─── Platform Posters ─────────────────────────────────────────────────────────
def post_to_pinterest(image_url, caption, board_id, link, alt_text=""):
    if not ENABLE_PINTEREST or not PINTEREST_TOKEN:
        log.info("Pinterest disabled or no token — skipping")
        return False
    payload = {
        "board_id": board_id,
        "media_source": {"source_type": "image_url", "url": image_url},
        "title": caption[:100],
        "description": caption[:500],
        "link": link,
        "alt_text": alt_text[:500] if alt_text else caption[:100],
    }
    r = requests.post(
        "https://api.pinterest.com/v5/pins",
        headers={"Authorization": f"Bearer {PINTEREST_TOKEN}", "Content-Type": "application/json"},
        json=payload,
        timeout=20,
    )
    if r.status_code in (200, 201):
        pin_id = r.json().get("id", "?")
        log.info(f"Pinterest OK — pin {pin_id}")
        return True
    log.error(f"Pinterest FAIL {r.status_code}: {r.text[:300]}")
    return False


def post_to_facebook(image_url, caption):
    if not ENABLE_FACEBOOK or not FB_PAGE_TOKEN:
        log.info("Facebook disabled — skipping")
        return False
    r = requests.post(
        f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos",
        data={"url": image_url, "caption": caption, "access_token": FB_PAGE_TOKEN},
        timeout=20,
    )
    if r.status_code == 200:
        log.info(f"Facebook OK — post {r.json().get('id','?')}")
        return True
    log.error(f"Facebook FAIL {r.status_code}: {r.text[:300]}")
    return False


def post_to_instagram(image_url, caption):
    if not ENABLE_INSTAGRAM or not IG_TOKEN:
        log.info("Instagram disabled — skipping")
        return False
    # Step 1: create container
    r1 = requests.post(
        f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media",
        data={"image_url": image_url, "caption": caption[:2200], "access_token": IG_TOKEN},
        timeout=20,
    )
    if r1.status_code != 200:
        log.error(f"Instagram container FAIL {r1.status_code}: {r1.text[:300]}")
        return False
    container_id = r1.json().get("id")
    time.sleep(3)
    # Step 2: publish
    r2 = requests.post(
        f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish",
        data={"creation_id": container_id, "access_token": IG_TOKEN},
        timeout=20,
    )
    if r2.status_code == 200:
        log.info(f"Instagram OK — post {r2.json().get('id','?')}")
        return True
    log.error(f"Instagram publish FAIL {r2.status_code}: {r2.text[:300]}")
    return False


def post_to_linkedin(image_url, caption):
    """Post to LinkedIn company page (requires LINKEDIN_ACCESS_TOKEN + LINKEDIN_ORG_ID in .env)."""
    if not ENABLE_LINKEDIN or not LINKEDIN_TOKEN or not LINKEDIN_ORG_ID:
        log.info("LinkedIn disabled or credentials missing — skipping")
        return False
    # Step 1: register upload
    reg = requests.post(
        "https://api.linkedin.com/v2/assets?action=registerUpload",
        headers={"Authorization": f"Bearer {LINKEDIN_TOKEN}", "Content-Type": "application/json"},
        json={
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": f"urn:li:organization:{LINKEDIN_ORG_ID}",
                "serviceRelationships": [{"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}],
            }
        },
        timeout=20,
    )
    if reg.status_code != 200:
        log.error(f"LinkedIn register FAIL {reg.status_code}: {reg.text[:200]}")
        return False
    upload_url = reg.json()["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
    asset_urn  = reg.json()["value"]["asset"]
    # Step 2: upload image bytes
    img_bytes = requests.get(image_url, timeout=20).content
    requests.put(upload_url, data=img_bytes, headers={"Authorization": f"Bearer {LINKEDIN_TOKEN}"}, timeout=30)
    # Step 3: create post
    post_r = requests.post(
        "https://api.linkedin.com/v2/ugcPosts",
        headers={"Authorization": f"Bearer {LINKEDIN_TOKEN}", "Content-Type": "application/json"},
        json={
            "author": f"urn:li:organization:{LINKEDIN_ORG_ID}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": caption[:3000]},
                    "shareMediaCategory": "IMAGE",
                    "media": [{"status": "READY", "media": asset_urn}],
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        },
        timeout=20,
    )
    if post_r.status_code in (200, 201):
        log.info(f"LinkedIn OK — post {post_r.json().get('id','?')}")
        return True
    log.error(f"LinkedIn FAIL {post_r.status_code}: {post_r.text[:300]}")
    return False


# ─── Main ─────────────────────────────────────────────────────────────────────
def process_image(path, topic, link, title=""):
    path = Path(path)
    if not path.exists():
        log.error(f"File not found: {path}")
        print(f"  SKIP — file not found: {path}")
        return

    ratio = detect_ratio(path)
    do_pin, do_ig, do_fb, do_li = ROUTING.get(ratio, (True, False, True, False))
    board_id = PINTEREST_BOARDS.get(topic, PINTEREST_BOARDS["wax"])
    link = link or DEFAULT_LINKS.get(topic, "https://waxandwane.store")
    caps = CAPTIONS.get(topic, CAPTIONS["wax"])
    if not title:
        title = _read_image_title(path, topic)
    alt_text = _build_alt_text(title, topic, path.name)

    print(f"\n  [{path.name}]  ratio={ratio}")
    print(f"  Routing -> Pinterest:{do_pin} | Instagram:{do_ig} | Facebook:{do_fb} | LinkedIn:{do_li}")

    # Upload to Imgur for a public URL
    print(f"  Uploading to CDN...", end=" ", flush=True)
    image_url = upload_image_to_imgur(path)
    if not image_url:
        print("FAILED — skipping this image")
        return
    print(f"OK ({image_url})")

    results = {}

    if do_pin:
        cap = caps["pinterest"].format(title=title, link=link)
        ok = post_to_pinterest(image_url, cap, board_id, link, alt_text)
        results["Pinterest"] = "OK" if ok else "FAIL"
        time.sleep(1)

    if do_fb:
        cap = caps["facebook"].format(title=title, link=link)
        ok = post_to_facebook(image_url, cap)
        results["Facebook"] = "OK" if ok else "FAIL"
        time.sleep(1)

    if do_ig:
        cap = caps["instagram"].format(title=title, link=link)
        ok = post_to_instagram(image_url, cap)
        results["Instagram"] = "OK" if ok else "FAIL"
        time.sleep(2)

    if do_li:
        cap = caps["linkedin"].format(title=title, link=link)
        ok = post_to_linkedin(image_url, cap)
        results["LinkedIn"] = "OK" if ok else "FAIL"
        time.sleep(1)

    summary = " | ".join(f"{k}: {v}" for k, v in results.items())
    print(f"  Results: {summary}")
    log.info(f"DONE {path.name} [{ratio}] -> {summary}")


def main():
    parser = argparse.ArgumentParser(description="Wax | Wane Smart Cross-Poster")
    parser.add_argument("--images", nargs="+", required=True, help="Image file paths")
    parser.add_argument("--topic", choices=["emf", "crystals", "haramoon", "wax"], default="emf")
    parser.add_argument("--link", default="", help="Product/collection URL to include in captions")
    parser.add_argument("--title", default="", help="Optional title override for captions")
    args = parser.parse_args()

    print(f"\nWax | Wane Cross-Poster — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Topic: {args.topic.upper()} | Images: {len(args.images)}")
    print("=" * 60)

    for img_path in args.images:
        process_image(img_path, args.topic, args.link, args.title)

    print("\nDone. Check crossposter.log for details.")


if __name__ == "__main__":
    main()
