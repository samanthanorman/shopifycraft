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
            
            # Prepare post data
            caption = f"{article['title']}\n\n{article['summary'][:200]}...\n\nRead more: {article['url']}"
            
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
            
            row_data = [
                timestamp,
                article['blog_name'],
                article['title'],
                article['url'],
                article.get('published', ''),
                facebook_url if facebook_url and facebook_url != "SKIPPED" else 'N/A',
                fb_status,
                instagram_url if instagram_url and instagram_url != "SKIPPED" else 'N/A',
                ig_status
            ]
            
            # Append to sheet
            body = {'values': [row_data]}
            result = self.sheets_service.spreadsheets().values().append(
                spreadsheetId=GOOGLE_SHEETS_ID,
                range='Sheet1!A:I',
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
            
            body = f"""
Your blog post has been detected and published to social media!

📝 Title: {article['title']}
🌐 Blog: {article['blog_name']}
🔗 Post URL: {article['url']}

Social Media Posts:
📘 Facebook: {fb_msg}
📷 Instagram: {ig_msg}

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
    autoposter = ShopifyAutoposter()
    autoposter.run()
