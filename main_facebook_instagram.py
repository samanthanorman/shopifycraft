#!/usr/bin/env python3
"""
Shopify Social Autoposter - Facebook & Instagram Edition
Automatically cross-posts new Shopify blog articles to Facebook and Instagram.
"""

import os
import sys
import json
import time
import feedparser
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Define the skill directory and load the .env file from there
SKILL_DIR = Path.home() / 'antigravity_skills' / 'shopify-social-autoposter'
load_dotenv(dotenv_path=SKILL_DIR / '.env')

# Configuration
FACEBOOK_PAGE_ID = os.getenv('FACEBOOK_PAGE_ID')
FACEBOOK_PAGE_TOKEN = os.getenv('FACEBOOK_PAGE_TOKEN')
INSTAGRAM_USER_ID = os.getenv('INSTAGRAM_USER_ID')
INSTAGRAM_ACCESS_TOKEN = os.getenv('INSTAGRAM_ACCESS_TOKEN')
GOOGLE_SHEETS_ID = os.getenv('GOOGLE_SHEETS_ID')
NOTIFICATION_EMAIL = os.getenv('NOTIFICATION_EMAIL', 'samanthanorman.1995@gmail.com')

# Feature flags
ENABLE_FACEBOOK = os.getenv('ENABLE_FACEBOOK', 'true').lower() == 'true'
ENABLE_INSTAGRAM = os.getenv('ENABLE_INSTAGRAM', 'true').lower() == 'true'

# Shopify RSS Feeds (Atom format)
# Updated March 14, 2026 - corrected handles verified against Shopify admin
SHOPIFY_FEEDS = [
    {
        'name': 'Wax | Wane Blog',
        'url': 'https://waxandwane.store/blogs/wax-wane-blog.atom',
        'blog_id': '119979376952',
        'tone': 'warm, poetic, story-driven lifestyle'
    },
    {
        'name': 'HARAMOON - The K-Beauty Blog',
        'url': 'https://waxandwane.store/blogs/why-korean-skincare.atom',
        'blog_id': '115858669880',
        'tone': 'science-meets-self-care, confident, K-beauty culture'
    },
    {
        'name': 'EMF and EMI',
        'url': 'https://waxandwane.store/blogs/electromagnetic-frequency-radiation.atom',
        'blog_id': '115660620088',
        'tone': 'calm, evidence-forward, empowering health'
    },
    {
        'name': 'Crystals - Minerals - Materials Blog',
        'url': 'https://waxandwane.store/blogs/crystals-science-magic.atom',
        'blog_id': '115710034232',
        'tone': 'earthy, reverent, educational with wonder'
    }
]

# Google API Scopes
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/gmail.send'
]

# Local log file to track posted articles
POSTED_LOG_FILE = SKILL_DIR / 'posted_links.txt'

# ─────────────────────────────────────────────────────────────────────────────
# NEWS HEADLINE QUERIES — one search query per blog, used to pull trending
# Google News headlines and weave them into social captions for freshness.
# Uses Google News RSS (completely free, no API key required).
# ─────────────────────────────────────────────────────────────────────────────
NEWS_QUERIES = {
    '119979376952': 'wellness lifestyle beauty trends ritual',          # Wax | Wane Blog
    '115858669880': 'Korean skincare K-beauty glass skin trends',       # HARAMOON
    '115660620088': 'EMF radiation health 5G shielding',                # EMF and EMI
    '115710034232': 'crystal healing minerals gemstones spirituality',  # Crystals
}


def fetch_trending_headline(blog_id):
    """Pull the top trending news headline for a blog topic using Google News RSS.
    Completely free — no API key needed. Returns headline string or None."""
    import urllib.request
    import urllib.parse
    import re
    query = NEWS_QUERIES.get(blog_id)
    if not query:
        return None
    try:
        encoded = urllib.parse.quote(query)
        rss_url = f'https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en'
        req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode('utf-8')
        titles = re.findall(r'<item>.*?<title>(.*?)</title>', raw, re.DOTALL)
        if titles:
            headline = re.sub(r'<!\[CDATA\[|\]\]>', '', titles[0]).strip()
            print(f'  📰 Trending headline: {headline}')
            return headline
    except Exception as e:
        print(f'  ⚠️  Could not fetch news headline: {str(e)[:60]}')
    return None


def ping_google_after_post(article_url):
    """Submit the new article URL to search engines via IndexNow.
    IndexNow is the modern standard (replaces deprecated Google sitemap ping).
    Supported by Bing, Yandex, and Google. No API key setup required.
    Returns True if accepted, False otherwise (non-critical — posts still go out)."""
    import urllib.request
    import json
    try:
        payload = json.dumps({
            'host': 'waxandwane.store',
            'key': 'waxwane2026',
            'keyLocation': 'https://waxandwane.store/waxwane2026.txt',
            'urlList': [article_url]
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://api.indexnow.org/indexnow',
            data=payload,
            headers={'Content-Type': 'application/json; charset=utf-8', 'User-Agent': 'Mozilla/5.0'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status in (200, 202):
                print(f'  🏓 IndexNow accepted — search engines notified for: {article_url}')
                return True
            else:
                print(f'  ⚠️  IndexNow returned HTTP {resp.status}')
    except Exception as e:
        print(f'  ⚠️  IndexNow ping failed (non-critical): {str(e)[:60]}')
    return False


# ─────────────────────────────────────────────────────────────────────────────
# PINTEREST MODULE
# Posts new blog articles as Pins. Each pin uses the blog's og:image,
# a keyword-rich description, and links directly back to the article.
# Requires a valid Pinterest access token in .env (refresh every 60 days).
# ─────────────────────────────────────────────────────────────────────────────

PINTEREST_HASHTAGS = {
    '119979376952': '#WellnessLifestyle #SelfCare #BeautyRitual #WaxAndWane #SlowLiving',
    '115858669880': '#KBeauty #KoreanSkincare #GlassSkin #SkincareRoutine #HARAMOON',
    '115660620088': '#EMFProtection #HealthyHome #5GHealth #EMFShielding #CleanLiving',
    '115710034232': '#CrystalHealing #Crystals #Gemstones #MineralCollection #CrystalMagic',
}


def post_to_pinterest(article):
    """Create a Pinterest Pin for a blog article.
    Token must be refreshed every 60 days via Pinterest Developer Portal.
    Returns Pin URL on success, None on failure."""
    if not ENABLE_PINTEREST:
        print("  Pinterest posting disabled")
        return "SKIPPED"
    if not PINTEREST_ACCESS_TOKEN:
        print("  Pinterest token not configured - skipping")
        return None
    try:
        import re as _re
        blog_id = article.get('blog_id', '')
        board_id = PINTEREST_BOARDS.get(blog_id)
        hashtags = PINTEREST_HASHTAGS.get(blog_id, '#WaxAndWane #Lifestyle')
        summary_clean = _re.sub(r'<[^>]+>', '', article.get('summary', ''))[:200].strip()
        description = (article['title'] + "\n\n" + summary_clean + "\n\n" + hashtags)[:500]
        if not article.get('image_url'):
            print("  No image found - Pinterest requires an image, skipping")
            return None
        pin_data = {
            "title": article['title'][:100],
            "description": description,
            "link": article['url'],
            "media_source": {"source_type": "image_url", "url": article['image_url']}
        }
        if board_id:
            pin_data["board_id"] = board_id
        response = requests.post(
            'https://api.pinterest.com/v5/pins',
            headers={'Authorization': f'Bearer {PINTEREST_ACCESS_TOKEN}', 'Content-Type': 'application/json'},
            json=pin_data, timeout=15
        )
        if response.status_code in (200, 201):
            pin_id = response.json().get('id', '')
            pin_url = f"https://www.pinterest.com/pin/{pin_id}/"
            print(f"  Pinterest Pin created: {pin_url}")
            return pin_url
        elif response.status_code == 401:
            print("  Pinterest token expired - update PINTEREST_ACCESS_TOKEN in .env")
            print("  Get a new token: https://developers.pinterest.com/tools/api-explorer/")
            return None
        else:
            print(f"  Pinterest API error {response.status_code}: {response.text[:200]}")
            return None
    except Exception as e:
        print(f"  Error posting to Pinterest: {str(e)}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# EVERGREEN REPOST MODULE
# Picks one older blog post per run and reposts it to all platforms.
# Evergreen = posts older than 30 days, not reposted within 90 days.
# Rotates across all 4 blogs so each gets equal airtime.
# Runs Saturday 10am via com.shopify.evergreen.plist (separate scheduler).
# ─────────────────────────────────────────────────────────────────────────────

EVERGREEN_LOG_FILE = SKILL_DIR / 'evergreen_repost_log.json'
EVERGREEN_MIN_AGE_DAYS = 30
EVERGREEN_COOLDOWN_DAYS = 90


def load_evergreen_log():
    """Load the evergreen repost history (URL -> last repost ISO timestamp)."""
    if EVERGREEN_LOG_FILE.exists():
        with open(EVERGREEN_LOG_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_evergreen_log(log):
    """Save the evergreen repost history."""
    with open(EVERGREEN_LOG_FILE, 'w') as f:
        json.dump(log, f, indent=2)


def pick_evergreen_article():
    """Scan all 4 RSS feeds and pick the best candidate for reposting.
    Prefers articles not reposted recently, rotating across all 4 blogs."""
    import email.utils
    from datetime import timezone
    log = load_evergreen_log()
    now = datetime.now(timezone.utc)
    candidates = []
    for feed_config in SHOPIFY_FEEDS:
        try:
            feed = feedparser.parse(feed_config['url'])
            for entry in feed.entries:
                url = entry.link
                published_str = entry.get('published', '')
                try:
                    pub_tuple = email.utils.parsedate(published_str)
                    pub_date = datetime(*pub_tuple[:6], tzinfo=timezone.utc)
                except Exception:
                    continue
                age_days = (now - pub_date).days
                if age_days < EVERGREEN_MIN_AGE_DAYS:
                    continue
                last_repost = log.get(url)
                if last_repost:
                    days_since = (now - datetime.fromisoformat(last_repost)).days
                    if days_since < EVERGREEN_COOLDOWN_DAYS:
                        continue
                candidates.append({
                    'title': entry.title,
                    'url': url,
                    'summary': entry.get('summary', ''),
                    'published': published_str,
                    'blog_name': feed_config['name'],
                    'blog_id': feed_config['blog_id'],
                    'age_days': age_days,
                    'image_url': None
                })
        except Exception as e:
            print(f"  Could not scan {feed_config['name']} for evergreen: {e}")
    if not candidates:
        return None
    def sort_key(c):
        last = log.get(c['url'])
        days_since = (now - datetime.fromisoformat(last)).days if last else 9999
        return (-days_since, -c['age_days'])
    candidates.sort(key=sort_key)
    best = candidates[0]
    try:
        import re as _re
        response = requests.get(best['url'], timeout=10)
        if response.status_code == 200:
            og = _re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\'>]+)["\']', response.text, _re.IGNORECASE)
            if og:
                best['image_url'] = og.group(1)
    except Exception:
        pass
    return best


def mark_evergreen_reposted(url):
    """Record that an evergreen article was just reposted."""
    log = load_evergreen_log()
    log[url] = datetime.now().isoformat()
    save_evergreen_log(log)


def run_evergreen_repost():
    """Entry point for the Saturday evergreen scheduler.
    Picks one article, posts it to all platforms, logs the repost."""
    print("=" * 60)
    print("Shopify Evergreen Reposter - Saturday Rotation")
    print("=" * 60)
    article = pick_evergreen_article()
    if not article:
        print("No evergreen candidates found today - all posts are too new or recently reposted.")
        return
    print(f"Evergreen pick: {article['title']} ({article['age_days']} days old)")
    print(f"Blog: {article['blog_name']}")
    print(f"URL: {article['url']}")
    autoposter = ShopifyAutoposter()
    autoposter.authenticate_google()
    fb_url = autoposter.post_to_facebook(article)
    time.sleep(2)
    ig_url = autoposter.post_to_instagram(article)
    time.sleep(2)
    pin_url = post_to_pinterest(article)
    time.sleep(2)
    autoposter.log_to_google_sheets(article, fb_url, ig_url, pin_url)
    mark_evergreen_reposted(article['url'])
    ping_google_after_post(article['url'])
    print("Evergreen repost complete!")
    print(f"  Facebook:  {fb_url or 'skipped/failed'}")
    print(f"  Instagram: {ig_url or 'skipped/failed'}")
    print(f"  Pinterest: {pin_url or 'skipped/failed'}")


class ShopifyAutoposter:
    """Main automation class for cross-posting Shopify blog articles."""
    
    def __init__(self):
        """Initialize the autoposter with API credentials."""
        self.facebook_page_id = FACEBOOK_PAGE_ID
        self.facebook_page_token = FACEBOOK_PAGE_TOKEN
        self.instagram_user_id = INSTAGRAM_USER_ID
        self.instagram_token = INSTAGRAM_ACCESS_TOKEN
        self.google_creds = None
        self.sheets_service = None
        self.gmail_service = None
        self.posted_links = self._load_posted_links()
        self.facebook_enabled = ENABLE_FACEBOOK
        self.instagram_enabled = ENABLE_INSTAGRAM
        
    def _load_posted_links(self):
        """Load the list of already-posted article URLs from local log."""
        if POSTED_LOG_FILE.exists():
            with open(POSTED_LOG_FILE, 'r') as f:
                return set(line.strip() for line in f if line.strip())
        return set()
    
    def _save_posted_link(self, url):
        """Save a newly posted article URL to the local log."""
        POSTED_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(POSTED_LOG_FILE, 'a') as f:
            f.write(f"{url}\n")
        self.posted_links.add(url)
    
    def authenticate_google(self):
        """Authenticate with Google APIs (Sheets and Gmail)."""
        creds = None
        token_path = SKILL_DIR / 'token.json'
        credentials_path = SKILL_DIR / 'credentials.json'
        
        # Load existing token if available
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        
        # If no valid credentials, authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not credentials_path.exists():
                    print(f"❌ ERROR: Google credentials.json not found at {credentials_path}")
                    print("Please download your OAuth credentials from Google Cloud Console")
                    sys.exit(1)
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_path), SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for future runs
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        
        self.google_creds = creds
        self.sheets_service = build('sheets', 'v4', credentials=creds)
        self.gmail_service = build('gmail', 'v1', credentials=creds)
        print("✅ Google APIs authenticated successfully")
    
    def check_rss_feeds(self):
        """Check all Shopify RSS feeds for new articles."""
        new_articles = []
        
        for feed_config in SHOPIFY_FEEDS:
            print(f"\n📡 Checking feed: {feed_config['name']}")
            try:
                feed = feedparser.parse(feed_config['url'])
                
                if feed.bozo:
                    print(f"⚠️  Warning: Feed parsing issue for {feed_config['name']}")
                
                for entry in feed.entries:
                    article_url = entry.link
                    
                    # Skip if already posted
                    if article_url in self.posted_links:
                        continue
                    
                    # Extract article data
                    article = {
                        'title': entry.title,
                        'url': article_url,
                        'summary': entry.get('summary', ''),
                        'published': entry.get('published', ''),
                        'blog_name': feed_config['name'],
                        'blog_id': feed_config['blog_id']
                    }
                    
                    # Extract featured image using web scraping (most reliable method)
                    article['image_url'] = None
                    try:
                        print(f"    🔍 Fetching images from blog post URL: {article_url}")
                        response = requests.get(article_url, timeout=10)
                        if response.status_code == 200:
                            import re
                            # Look for og:image meta tag (most reliable for featured images)
                            og_image = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\'>]+)["\']', response.text, re.IGNORECASE)
                            if og_image:
                                article['image_url'] = og_image.group(1)
                                print(f"    ✅ Found og:image: {article['image_url']}")
                            else:
                                print(f"    ⚠️  No og:image meta tag found")
                        else:
                            print(f"    ⚠️  HTTP {response.status_code} when fetching {article_url}")
                    except Exception as e:
                        print(f"    ⚠️  Could not fetch images from URL: {str(e)}")
                    
                    new_articles.append(article)
                    print(f"  ✨ New article found: {article['title']}")
            
            except Exception as e:
                print(f"❌ Error checking feed {feed_config['name']}: {str(e)}")
        
        return new_articles
    
    def post_to_facebook(self, article):
        """Post article to Facebook Page."""
        if not self.facebook_enabled:
            print("  ⏭️  Facebook posting disabled")
            return "SKIPPED"
        
        if not self.facebook_page_id or not self.facebook_page_token:
            print("  ⚠️  Facebook credentials not configured")
            return None
        
        try:
            # Facebook Graph API endpoint for posting photos
            url = f"https://graph.facebook.com/v25.0/{self.facebook_page_id}/photos"
            
            # Pull trending news headline for this blog topic (free, no API key)
            trending = fetch_trending_headline(article.get('blog_id', ''))
            news_line = f"\n\n📰 Trending now: {trending}" if trending else ""

            # Prepare post data — weave in trending headline if available
            caption = f"{article['title']}\n\n{article['summary'][:200]}...{news_line}\n\nRead more: {article['url']}"
            
            data = {
                'access_token': self.facebook_page_token,
                'caption': caption
            }
            
            # Add image if available
            if article.get('image_url'):
                data['url'] = article['image_url']
            else:
                print("  ⚠️  No image found, posting text only")
                # Use feed endpoint for text-only posts
                url = f"https://graph.facebook.com/v25.0/{self.facebook_page_id}/feed"
                data = {
                    'access_token': self.facebook_page_token,
                    'message': caption,
                    'link': article['url']
                }
            
            response = requests.post(url, data=data)
            response.raise_for_status()
            
            result = response.json()
            post_id = result.get('post_id') or result.get('id')
            fb_url = f"https://www.facebook.com/{post_id}"
            print(f"  📘 Facebook post created: {fb_url}")
            return fb_url
        
        except requests.exceptions.HTTPError as e:
            print(f"  ❌ Facebook API error: {e}")
            print(f"  Response: {response.text}")
            return None
        except Exception as e:
            print(f"  ❌ Error posting to Facebook: {str(e)}")
            return None
    
    def post_to_instagram(self, article):
        """Post article to Instagram Business Account."""
        if not self.instagram_enabled:
            print("  ⏭️  Instagram posting disabled")
            return "SKIPPED"
        
        if not self.instagram_user_id or not self.instagram_token:
            print("  ⚠️  Instagram credentials not configured")
            return None
        
        if not article.get('image_url'):
            print("  ⚠️  No image found, Instagram requires images")
            return None
        
        try:
            # Step 1: Create media container
            container_url = f"https://graph.facebook.com/v25.0/{self.instagram_user_id}/media"
            
            caption = f"{article['title']}\n\n{article['summary'][:100]}...\n\nLink in bio! 🔗"
            
            container_data = {
                'image_url': article['image_url'],
                'caption': caption,
                'access_token': self.instagram_token
            }
            
            print("  📸 Creating Instagram media container...")
            container_response = requests.post(container_url, data=container_data)
            container_response.raise_for_status()
            container_result = container_response.json()
            container_id = container_result['id']
            
            # Step 2: Publish the container
            publish_url = f"https://graph.facebook.com/v25.0/{self.instagram_user_id}/media_publish"
            publish_data = {
                'creation_id': container_id,
                'access_token': self.instagram_token
            }
            
            # Wait a moment for the container to be ready
            time.sleep(2)
            
            print("  📸 Publishing Instagram post...")
            publish_response = requests.post(publish_url, data=publish_data)
            publish_response.raise_for_status()
            publish_result = publish_response.json()
            media_id = publish_result['id']
            
            ig_url = f"https://www.instagram.com/p/{media_id}/"
            print(f"  📷 Instagram post created: {ig_url}")
            return ig_url
        
        except requests.exceptions.HTTPError as e:
            print(f"  ❌ Instagram API error: {e}")
            try:
                error_detail = e.response.json()
                print(f"  Error details: {error_detail}")
            except:
                print(f"  Response: {e.response.text}")
            return None
        except Exception as e:
            print(f"  ❌ Error posting to Instagram: {str(e)}")
            return None
    
    def log_to_google_sheets(self, article, facebook_url, instagram_url):
        """Log the cross-posted article to Google Sheets."""
        if not GOOGLE_SHEETS_ID:
            print("  ⚠️  No Google Sheets ID configured, skipping logging")
            return
        
        try:
            # Prepare row data
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Determine status for each platform
            fb_status = "Disabled" if facebook_url == "SKIPPED" else ("Success" if facebook_url else "Failed")
            ig_status = "Disabled" if instagram_url == "SKIPPED" else ("Success" if instagram_url else "Failed")
            pin_status = "Disabled" if pinterest_url == "SKIPPED" else ("Success" if pinterest_url else "No image / Failed")
            
            row_data = [
                timestamp,
                article['blog_name'],
                article['title'],
                article['url'],
                article.get('published', ''),
                facebook_url if facebook_url and facebook_url != "SKIPPED" else 'N/A',
                fb_status,
                instagram_url if instagram_url and instagram_url != "SKIPPED" else 'N/A',
                ig_status,
                pinterest_url if pinterest_url and pinterest_url != "SKIPPED" else 'N/A',
                pin_status
            ]
            
            # Append to sheet
            body = {'values': [row_data]}
            result = self.sheets_service.spreadsheets().values().append(
                spreadsheetId=GOOGLE_SHEETS_ID,
                range='Sheet1!A:K',
                valueInputOption='RAW',
                body=body
            ).execute()
            
            print(f"  📊 Logged to Google Sheets")
        
        except HttpError as e:
            print(f"  ❌ Google Sheets API error: {e}")
        except Exception as e:
            print(f"  ❌ Error logging to Google Sheets: {str(e)}")
    
    def send_notification_email(self, article, facebook_url, instagram_url):
        """Send email notification about the cross-post."""
        if not NOTIFICATION_EMAIL:
            return
        
        try:
            subject = f"✅ Blog Post Published: {article['title']}"
            
            # Determine status messages
            fb_msg = "Disabled" if facebook_url == "SKIPPED" else (facebook_url if facebook_url else "Failed")
            ig_msg = "Disabled" if instagram_url == "SKIPPED" else (instagram_url if instagram_url else "Failed")
            pin_msg = "Disabled" if pinterest_url == "SKIPPED" else (pinterest_url if pinterest_url else "No image / Failed")
            
            body = f"""
Your blog post has been detected and published to social media!

📝 Title: {article['title']}
🌐 Blog: {article['blog_name']}
🔗 Post URL: {article['url']}

Social Media Posts:
📘 Facebook: {fb_msg}
📷 Instagram: {ig_msg}
📌 Pinterest: {pin_msg}

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---
Shopify Social Autoposter - Facebook & Instagram Edition
"""
            
            # Create email message
            from email.mime.text import MIMEText
            import base64
            
            message = MIMEText(body)
            message['to'] = NOTIFICATION_EMAIL
            message['subject'] = subject
            
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            self.gmail_service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            print(f"  📧 Notification email sent to {NOTIFICATION_EMAIL}")
        
        except Exception as e:
            print(f"  ⚠️  Could not send email: {str(e)}")
    
    def process_article(self, article):
        """Process a single article: post to platforms and log."""
        print(f"\n🚀 Processing: {article['title']}")
        
        # Post to Facebook
        facebook_url = self.post_to_facebook(article)
        time.sleep(2)  # Rate limiting
        
        # Post to Instagram
        instagram_url = self.post_to_instagram(article)
        time.sleep(2)  # Rate limiting
        
        # Log to Google Sheets
        self.log_to_google_sheets(article, facebook_url, instagram_url)
        
        # Send notification email
        self.send_notification_email(article, facebook_url, instagram_url)
        
        # Mark as posted
        self._save_posted_link(article['url'])

        # Ping Google to fast-track indexing of the new post (free, no API key)
        ping_google_after_post(article['url'])

        print(f"✅ Completed processing: {article['title']}")
    
    def run(self):
        """Main execution method."""
        print("=" * 60)
        print("🤖 Shopify Social Autoposter - Facebook & Instagram")
        print("=" * 60)
        
        # Show platform status
        if self.facebook_enabled:
            if not self.facebook_page_id or not self.facebook_page_token:
                print("⚠️  WARNING: Facebook enabled but credentials missing")
        else:
            print("ℹ️  Facebook posting is DISABLED")
        
        if self.instagram_enabled:
            if not self.instagram_user_id or not self.instagram_token:
                print("⚠️  WARNING: Instagram enabled but credentials missing")
        else:
            print("ℹ️  Instagram posting is DISABLED")
        
        # Authenticate with Google
        self.authenticate_google()
        
        # Check for new articles
        new_articles = self.check_rss_feeds()
        
        if not new_articles:
            print("\n✨ No new articles found. All caught up!")
            return
        
        print(f"\n📢 Found {len(new_articles)} new article(s) to process")
        
        # Process each article
        for article in new_articles:
            self.process_article(article)
            time.sleep(3)  # Rate limiting between articles
        
        print("\n" + "=" * 60)
        print(f"🎉 Automation complete! Processed {len(new_articles)} article(s)")
        print("=" * 60)


if __name__ == "__main__":
    import sys
    if '--evergreen' in sys.argv:
        run_evergreen_repost()
    else:
        autoposter = ShopifyAutoposter()
        autoposter.run()
