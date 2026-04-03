#!/usr/bin/env python3
"""
TikTok Shop Token Generator
============================
Run this ONCE to get your TikTok Shop access token and save it to .env.
After that, the auto-refresh in the main scripts handles renewals.

HOW TO USE:
1. Open this URL in your browser and log in as the Wax and Wane shop seller:
   https://services.tiktokshops.us/open/authorize?service_id=7618493139276334862

2. After you click "Authorize", TikTok will redirect you to a URL that looks like:
   https://your-redirect-url.com/?code=TTP_xxxxxxxx&state=...

3. Copy the code value (everything after code= and before &state)

4. Paste it when this script asks for it.

5. The script saves your access_token and refresh_token to .env automatically.
"""

import os
import sys
import requests
import hashlib
import hmac
import time
from pathlib import Path
from dotenv import load_dotenv, set_key

SKILL_DIR = Path.home() / 'antigravity_skills' / 'shopify-social-autoposter'
ENV_FILE = SKILL_DIR / '.env'
load_dotenv(dotenv_path=ENV_FILE)

APP_KEY = os.getenv('TIKTOK_APP_KEY', '6jdqlj8pcfdru')
APP_SECRET = os.getenv('TIKTOK_APP_SECRET', 'cf5952205ccd155be4d313cdb5d0d9f68cfbb31b')
APP_ID = os.getenv('TIKTOK_APP_ID', '7618493139276334862')

AUTH_URL = f'https://services.tiktokshops.us/open/authorize?service_id={APP_ID}'
TOKEN_URL = 'https://auth.tiktok-shops.com/api/v2/token/get'
REFRESH_URL = 'https://auth.tiktok-shops.com/api/v2/token/refresh'


def get_token_from_auth_code(auth_code):
    """Exchange an auth_code for an access_token and refresh_token."""
    params = {
        'app_key': APP_KEY,
        'app_secret': APP_SECRET,
        'auth_code': auth_code,
        'grant_type': 'authorized_code'
    }
    resp = requests.get(TOKEN_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get('code') != 0:
        print(f'\n❌ TikTok API error: {data.get("message")} (code {data.get("code")})')
        print('   Make sure you copied the full auth_code from the redirect URL.')
        return None
    return data.get('data', {})


def refresh_access_token(refresh_token):
    """Use a refresh_token to get a new access_token (call before it expires)."""
    params = {
        'app_key': APP_KEY,
        'app_secret': APP_SECRET,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token'
    }
    resp = requests.get(REFRESH_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get('code') != 0:
        print(f'\n❌ Refresh failed: {data.get("message")} (code {data.get("code")})')
        return None
    return data.get('data', {})


def save_tokens(token_data):
    """Write access_token and refresh_token to .env file."""
    access_token = token_data.get('access_token', '')
    refresh_token = token_data.get('refresh_token', '')
    expire_ts = token_data.get('access_token_expire_in', 0)
    shop_name = token_data.get('seller_name', 'Unknown')

    set_key(str(ENV_FILE), 'TIKTOK_ACCESS_TOKEN', access_token)
    set_key(str(ENV_FILE), 'TIKTOK_REFRESH_TOKEN', refresh_token)

    import datetime
    expire_dt = datetime.datetime.fromtimestamp(expire_ts).strftime('%Y-%m-%d %H:%M') if expire_ts else 'unknown'

    print(f'\n✅ Tokens saved to .env!')
    print(f'   Shop: {shop_name}')
    print(f'   Access token expires: {expire_dt}')
    print(f'   Access token: {access_token[:30]}...')
    print(f'\n🔄 The scripts will auto-refresh your token before it expires.')
    print(f'   If you ever need to re-authorize, just run this script again.')


def main():
    print('=' * 60)
    print('🛍️  TikTok Shop Token Generator - Wax and Wane')
    print('=' * 60)

    # Check if we already have a refresh token and try to use it
    existing_refresh = os.getenv('TIKTOK_REFRESH_TOKEN', '').strip()
    if existing_refresh and existing_refresh != '""':
        print(f'\n🔄 Found existing refresh token. Attempting to renew access token...')
        token_data = refresh_access_token(existing_refresh)
        if token_data:
            save_tokens(token_data)
            return
        else:
            print('   Refresh failed — proceeding with full re-authorization.\n')

    # Full OAuth flow
    print(f'\n📋 STEP 1: Open this URL in your browser:')
    print(f'\n   {AUTH_URL}\n')
    print('   Log in as the Wax and Wane TikTok Shop seller and click "Authorize".')
    print('   TikTok will redirect you to a URL — copy the code= value from that URL.')
    print('   The code looks like: TTP_xxxxxxxxxxxxxxxx')
    print()

    auth_code = input('📋 STEP 2: Paste the auth_code here and press Enter: ').strip()
    if not auth_code:
        print('❌ No code entered. Exiting.')
        sys.exit(1)

    # Strip any accidental URL prefix if they pasted the whole redirect URL
    if 'code=' in auth_code:
        auth_code = auth_code.split('code=')[1].split('&')[0]
        print(f'   (Extracted code: {auth_code})')

    print(f'\n🔑 Exchanging auth code for access token...')
    token_data = get_token_from_auth_code(auth_code)
    if not token_data:
        sys.exit(1)

    save_tokens(token_data)
    print('\n🎉 Done! Your TikTok Shop API is now connected.')
    print('   The autoposter scripts will use this token automatically.')


if __name__ == '__main__':
    main()
