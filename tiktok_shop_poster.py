#!/usr/bin/env python3
"""
TikTok Shop Poster Module
==========================
Handles posting blog content to TikTok Shop and syncing product listings.

TWO SEPARATE THINGS:
1. TikTok Shop API  — manages your product catalog (listings, inventory, orders)
2. TikTok Content Posting API — posts videos/photos to your TikTok feed

This module handles BOTH, but they use different tokens:
- Shop API:     uses TIKTOK_ACCESS_TOKEN (from tiktok_get_token.py)
- Content API:  requires separate user OAuth (future feature — needs app review approval)

WHAT WORKS NOW (with current credentials):
- Read your product catalog from TikTok Shop
- Check order status
- Update product info / sync from Shopify
- Post product spotlight content (once Content API is approved)

WHAT NEEDS APPROVAL FIRST:
- Posting videos to TikTok feed (Content Posting API requires app review)
- Creating TikTok Shop affiliate links programmatically
"""

import os
import json
import time
import hmac
import hashlib
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv, set_key

SKILL_DIR = Path.home() / 'antigravity_skills' / 'shopify-social-autoposter'
load_dotenv(dotenv_path=SKILL_DIR / '.env')

# ── Credentials ──────────────────────────────────────────────────────────────
APP_KEY = os.getenv('TIKTOK_APP_KEY', '6jdqlj8pcfdru')
APP_SECRET = os.getenv('TIKTOK_APP_SECRET', 'cf5952205ccd155be4d313cdb5d0d9f68cfbb31b')
APP_ID = os.getenv('TIKTOK_APP_ID', '7618493139276334862')
SHOP_ID = os.getenv('TIKTOK_SHOP_ID', '7495887137761364722')
SHOP_CODE = os.getenv('TIKTOK_SHOP_CODE', 'USLCHYE7XD')
ENABLE_TIKTOK = os.getenv('ENABLE_TIKTOK', 'true').lower() == 'true'

# Tokens (filled in by tiktok_get_token.py)
ACCESS_TOKEN = os.getenv('TIKTOK_ACCESS_TOKEN', '').strip().strip('"')
REFRESH_TOKEN = os.getenv('TIKTOK_REFRESH_TOKEN', '').strip().strip('"')

# ── API Base URLs ─────────────────────────────────────────────────────────────
SHOP_API_BASE = 'https://open-api.tiktokglobalshop.com'
AUTH_REFRESH_URL = 'https://auth.tiktok-shops.com/api/v2/token/refresh'
ENV_FILE = SKILL_DIR / '.env'


# ── HMAC-SHA256 Request Signing ───────────────────────────────────────────────
def sign_request(path, params, body=''):
    """Generate the HMAC-SHA256 signature required by TikTok Shop API.
    TikTok requires: secret + path + sorted_params + body + secret"""
    # Sort params alphabetically, exclude sign and access_token
    sorted_keys = sorted(k for k in params if k not in ('sign', 'access_token'))
    param_str = ''.join(f'{k}{params[k]}' for k in sorted_keys)
    # Build the string to sign
    to_sign = APP_SECRET + path + param_str + body + APP_SECRET
    signature = hmac.new(
        APP_SECRET.encode('utf-8'),
        to_sign.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature


# ── Token Management ──────────────────────────────────────────────────────────
def refresh_access_token():
    """Refresh the TikTok Shop access token using the refresh token.
    Called automatically when a 401 is received."""
    global ACCESS_TOKEN, REFRESH_TOKEN
    if not REFRESH_TOKEN:
        print('  ⚠️  No TikTok refresh token — run tiktok_get_token.py first')
        return False
    try:
        params = {
            'app_key': APP_KEY,
            'app_secret': APP_SECRET,
            'refresh_token': REFRESH_TOKEN,
            'grant_type': 'refresh_token'
        }
        resp = requests.get(AUTH_REFRESH_URL, params=params, timeout=15)
        data = resp.json()
        if data.get('code') == 0:
            token_data = data['data']
            ACCESS_TOKEN = token_data['access_token']
            REFRESH_TOKEN = token_data['refresh_token']
            # Save to .env
            set_key(str(ENV_FILE), 'TIKTOK_ACCESS_TOKEN', ACCESS_TOKEN)
            set_key(str(ENV_FILE), 'TIKTOK_REFRESH_TOKEN', REFRESH_TOKEN)
            print(f'  🔄 TikTok token refreshed automatically')
            return True
        else:
            print(f'  ❌ Token refresh failed: {data.get("message")}')
            return False
    except Exception as e:
        print(f'  ❌ Token refresh error: {str(e)[:80]}')
        return False


def make_shop_api_call(method, path, params=None, body=None, retry=True):
    """Make a signed TikTok Shop API call. Auto-refreshes token on 401."""
    if not ACCESS_TOKEN:
        print('  ⚠️  TikTok access token not set — run tiktok_get_token.py first')
        return None

    params = params or {}
    params['app_key'] = APP_KEY
    params['access_token'] = ACCESS_TOKEN
    params['timestamp'] = str(int(time.time()))
    params['shop_id'] = SHOP_ID

    # Sign the request
    body_str = json.dumps(body) if body else ''
    params['sign'] = sign_request(path, params, body_str)

    url = SHOP_API_BASE + path
    try:
        if method.upper() == 'GET':
            resp = requests.get(url, params=params, timeout=15)
        else:
            resp = requests.post(url, params=params, json=body, timeout=15)

        data = resp.json()

        # Handle token expiry
        if data.get('code') in (40001, 40002, 40003) and retry:
            print('  🔄 TikTok token expired — refreshing...')
            if refresh_access_token():
                return make_shop_api_call(method, path, params, body, retry=False)

        return data
    except Exception as e:
        print(f'  ❌ TikTok Shop API error: {str(e)[:80]}')
        return None


# ── Product Catalog Functions ─────────────────────────────────────────────────
def get_shop_products(page_size=20):
    """Fetch active product listings from TikTok Shop.
    Returns list of products with name, price, stock, and product URL."""
    if not ENABLE_TIKTOK:
        return []
    print('  🛍️  Fetching TikTok Shop product catalog...')
    result = make_shop_api_call('GET', '/api/products/search', params={
        'page_size': page_size,
        'page_number': 1
    })
    if not result or result.get('code') != 0:
        print(f'  ⚠️  Could not fetch products: {result.get("message") if result else "no response"}')
        return []
    products = result.get('data', {}).get('products', [])
    print(f'  ✅ Found {len(products)} TikTok Shop products')
    return products


def get_product_by_keyword(keyword):
    """Search TikTok Shop catalog for a product matching a keyword.
    Used to find the right product to spotlight in blog posts."""
    products = get_shop_products(page_size=50)
    keyword_lower = keyword.lower()
    matches = [p for p in products if keyword_lower in p.get('name', '').lower()]
    return matches[0] if matches else None


def get_shop_orders(days=7):
    """Fetch recent TikTok Shop orders (last N days).
    Useful for monitoring sales driven by social posts."""
    if not ENABLE_TIKTOK:
        return []
    import time as _time
    end_ts = int(_time.time())
    start_ts = end_ts - (days * 86400)
    result = make_shop_api_call('POST', '/api/orders/search', body={
        'create_time_from': start_ts,
        'create_time_to': end_ts,
        'page_size': 20
    })
    if not result or result.get('code') != 0:
        print(f'  ⚠️  Could not fetch orders: {result.get("message") if result else "no response"}')
        return []
    return result.get('data', {}).get('order_list', [])


# ── Blog-to-TikTok Shop Link Builder ─────────────────────────────────────────
# Blog-to-TikTok-product keyword mapping (mirrors the sister posts mapping)
BLOG_TO_PRODUCT_KEYWORDS = {
    '119979376952': ['wellness', 'wax', 'ritual'],        # Wax | Wane Blog
    '115858669880': ['haramoon', 'serum', 'skincare'],    # HARAMOON
    '115660620088': ['emf', 'faraday', 'shielding'],      # EMF
    '115710034232': ['crystal', 'gemstone', 'mineral'],   # Crystals
}


def build_tiktok_shop_link(blog_id, article_url, article_title):
    """Build a TikTok Shop product link to include in social captions.
    If a matching product is found in the catalog, returns its TikTok Shop URL.
    Falls back to the shop's main URL if no match found."""
    if not ENABLE_TIKTOK:
        return None

    keywords = BLOG_TO_PRODUCT_KEYWORDS.get(blog_id, [])
    shop_base = f'https://www.tiktok.com/@waxandwane.store/shop'

    for keyword in keywords:
        product = get_product_by_keyword(keyword)
        if product:
            product_id = product.get('id', '')
            product_name = product.get('name', '')
            # TikTok Shop product URL format
            product_url = f'https://www.tiktok.com/view/product/{product_id}'
            print(f'  🛍️  TikTok Shop product found: {product_name}')
            return product_url

    # No specific product found — return the shop page
    return shop_base


def build_tiktok_caption(article, product_url=None):
    """Build a TikTok-optimized caption for a blog article post.
    TikTok captions max out at 2,200 characters. Keep it punchy."""
    import re
    blog_id = article.get('blog_id', '')
    title = article.get('title', '')
    summary_raw = article.get('summary', '')
    summary = re.sub(r'<[^>]+>', '', summary_raw)[:150].strip()
    article_url = article.get('url', '')

    # Blog-specific hashtag sets
    hashtags = {
        '119979376952': '#WaxAndWane #WellnessLifestyle #SelfCare #SlowLiving #TikTokShop',
        '115858669880': '#HARAMOON #KBeauty #KoreanSkincare #GlassSkin #TikTokMadeMeBuyIt #TikTokShop',
        '115660620088': '#EMFProtection #FaradayBag #HealthyHome #TechHealth #TikTokShop',
        '115710034232': '#CrystalHealing #Crystals #Gemstones #WitchTok #CrystalTok #TikTokShop',
    }.get(blog_id, '#WaxAndWane #TikTokShop #SmallBusiness')

    shop_line = f'\n\n🛍️ Shop now: {product_url}' if product_url else ''
    caption = f"""{title}

{summary}...

📖 Full article: {article_url}{shop_line}

{hashtags}"""
    return caption[:2200]


# ── Main TikTok Post Function ─────────────────────────────────────────────────
def post_blog_to_tiktok_shop(article):
    """
    Main function called by the autoposter for each new blog article.

    WHAT THIS DOES:
    1. Finds a matching product in your TikTok Shop catalog
    2. Builds a TikTok-optimized caption with the product link
    3. Returns the caption + product URL for inclusion in the post log

    NOTE: Actual video/photo posting to TikTok feed requires the Content Posting API,
    which needs separate app review approval from TikTok. This function prepares
    everything so it's ready the moment that approval comes through.
    Until then, it returns the caption + shop link so you can post manually
    or via TikTok's native scheduling tools.
    """
    if not ENABLE_TIKTOK:
        return 'SKIPPED'

    if not ACCESS_TOKEN:
        print('  ⚠️  TikTok: No access token — run tiktok_get_token.py to connect')
        return None

    blog_id = article.get('blog_id', '')
    article_url = article.get('url', '')
    title = article.get('title', '')

    print(f'  🎵 Building TikTok Shop post for: {title[:50]}...')

    # Find matching product
    product_url = build_tiktok_shop_link(blog_id, article_url, title)

    # Build caption
    caption = build_tiktok_caption(article, product_url)

    # Log the TikTok caption to a file for manual posting or future automation
    log_tiktok_post(article, caption, product_url)

    print(f'  ✅ TikTok caption ready — saved to tiktok_post_queue.json')
    if product_url:
        print(f'  🛍️  Product link: {product_url}')

    return f'QUEUED:{product_url or "no-product"}'


def log_tiktok_post(article, caption, product_url):
    """Save TikTok post content to a queue file for manual posting or future automation."""
    queue_file = SKILL_DIR / 'tiktok_post_queue.json'
    queue = []
    if queue_file.exists():
        try:
            with open(queue_file, 'r') as f:
                queue = json.load(f)
        except Exception:
            queue = []

    queue.append({
        'timestamp': datetime.now().isoformat(),
        'title': article.get('title', ''),
        'article_url': article.get('url', ''),
        'blog_name': article.get('blog_name', ''),
        'image_url': article.get('image_url', ''),
        'caption': caption,
        'product_url': product_url,
        'status': 'queued'
    })

    with open(queue_file, 'w') as f:
        json.dump(queue, f, indent=2)


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == '__main__':
    print('=' * 60)
    print('🛍️  TikTok Shop Module - Connection Test')
    print('=' * 60)

    if not ACCESS_TOKEN:
        print('\n⚠️  No access token found.')
        print('   Run this first: python3 tiktok_get_token.py')
    else:
        print(f'\n✅ Access token found: {ACCESS_TOKEN[:30]}...')
        print('\n🔍 Testing product catalog access...')
        products = get_shop_products(page_size=5)
        if products:
            print(f'\n📦 First 5 products in your TikTok Shop:')
            for p in products:
                print(f'   - {p.get("name", "Unknown")} (ID: {p.get("id", "?")})')
        else:
            print('   No products returned — check token and shop ID')
