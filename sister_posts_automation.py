#!/usr/bin/env python3
"""
Sister Posts Automation - Smart Product Spotlight
Runs on Mondays and Wednesdays, automatically detecting products
mentioned in the most recent blog post and creating matching product posts.

Flow:
1. Reads the most recently posted blog article from posted_links.txt
2. Scrapes that blog post for product mentions and links
3. Pulls product images from Shopify
4. Posts a product spotlight to Facebook and Instagram
"""

import os
import sys
import re
import json
import requests
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import feedparser

# Define the skill directory and load the .env file from there
SKILL_DIR = Path.home() / 'antigravity_skills' / 'shopify-social-autoposter'
load_dotenv(dotenv_path=SKILL_DIR / '.env')

# Configuration
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
FACEBOOK_PAGE_TOKEN = os.getenv("FACEBOOK_PAGE_TOKEN")
INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL")
ENABLE_FACEBOOK = os.getenv("ENABLE_FACEBOOK", "true").lower() == "true"
ENABLE_INSTAGRAM = os.getenv("ENABLE_INSTAGRAM", "true").lower() == "true"

STORE_URL = "https://waxandwane.store"
POSTED_LOG_FILE = SKILL_DIR / 'posted_links.txt'
SISTER_LOG_FILE = SKILL_DIR / 'sister_posted_links.txt'
SISTER_QUEUE_FILE = SKILL_DIR / 'sister_queue_index.txt'  # Tracks which blog post to do next

# Product keyword mapping - maps keywords in blog posts to product info
PRODUCT_KEYWORDS = {
    'haramoon': {
        'name': 'HARAMOON K-Beauty Collection',
        'shop_url': f'{STORE_URL}/collections/haramoon',
        'hashtags': '#HARAMOON #KBeauty #KoreanSkincare #GlowingSkin #SkinBarrier #GlassSkin #SkincareRoutine #KBeautyCommunity #WaxAndWane',
        'emoji': '✨💙'
    },
    'faraday': {
        'name': 'Faraday Bag EMF Protection',
        'shop_url': f'{STORE_URL}/collections/emf-protection',
        'hashtags': '#FaradayBag #EMFProtection #TechHealth #DigitalWellness #5GProtection #EMFShielding #WaxAndWane',
        'emoji': '🛡️⚡'
    },
    'emf': {
        'name': 'EMF Protection Collection',
        'shop_url': f'{STORE_URL}/collections/emf-protection',
        'hashtags': '#EMFProtection #FaradayBag #TechHealth #DigitalWellness #5GProtection #WaxAndWane',
        'emoji': '🛡️⚡'
    },
    'moonstone': {
        'name': 'Moonstone Crystal Collection',
        'shop_url': f'{STORE_URL}/collections/crystals',
        'hashtags': '#Moonstone #Crystals #CrystalHealing #Wellness #Spirituality #CrystalEnergy #WaxAndWane',
        'emoji': '🌙💎'
    },
    'crystal': {
        'name': 'Crystal & Wellness Collection',
        'shop_url': f'{STORE_URL}/collections/crystals',
        'hashtags': '#Crystals #CrystalHealing #Wellness #Spirituality #CrystalEnergy #Mindfulness #WaxAndWane',
        'emoji': '💎✨'
    },
    'skincare': {
        'name': 'HARAMOON K-Beauty Skincare',
        'shop_url': f'{STORE_URL}/collections/haramoon',
        'hashtags': '#Skincare #KBeauty #HARAMOON #GlowingSkin #SkincareRoutine #SkinBarrier #WaxAndWane',
        'emoji': '✨💙'
    },
    'serum': {
        'name': 'HARAMOON Skincare Serums',
        'shop_url': f'{STORE_URL}/collections/haramoon',
        'hashtags': '#Serum #KBeauty #HARAMOON #GlowingSkin #SkincareRoutine #AntiAging #WaxAndWane',
        'emoji': '✨💙'
    }
}


def get_next_unposted_blog():
    """Get the next blog post that hasn't had a sister post yet.
    
    Cycles through ALL blog posts from the RSS feeds in order,
    skipping any that already have a sister post. This ensures
    every blog post eventually gets a product spotlight.
    """
    
    # Fetch all blog posts from RSS feeds
    # Updated March 14, 2026 - corrected handles verified against Shopify admin
    feeds = [
        'https://waxandwane.store/blogs/wax-wane-blog.atom',
        'https://waxandwane.store/blogs/why-korean-skincare.atom',                    # HARAMOON K-Beauty
        'https://waxandwane.store/blogs/electromagnetic-frequency-radiation.atom',    # EMF and EMI
        'https://waxandwane.store/blogs/crystals-science-magic.atom',                 # Crystals - Minerals - Materials
    ]
    
    all_posts = []
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                if entry.link not in all_posts:
                    all_posts.append(entry.link)
        except Exception as e:
            print(f"⚠️  Could not fetch feed {feed_url}: {e}")
    
    if not all_posts:
        print("❌ No blog posts found in RSS feeds")
        return None
    
    # Load which posts already have sister posts
    sister_posted = load_sister_posted_links()
    
    # Find the next post that hasn't been sister-posted yet
    for post_url in all_posts:
        if post_url not in sister_posted:
            print(f"📋 Queue: {len(all_posts)} total posts, {len(sister_posted)} already done")
            print(f"➡️  Next up: {post_url}")
            return post_url
    
    # All posts have been done - reset the queue and start over!
    print("🔄 All blog posts have been spotlighted! Resetting queue to cycle again...")
    # Clear the sister posted log to start fresh
    with open(SISTER_LOG_FILE, 'w') as f:
        f.write('')
    # Return the first post
    return all_posts[0] if all_posts else None


def get_most_recent_blog_post():
    """Legacy function - now calls get_next_unposted_blog for queue-based behavior"""
    return get_next_unposted_blog()


def load_sister_posted_links():
    """Load already sister-posted blog URLs to avoid duplicates"""
    if SISTER_LOG_FILE.exists():
        with open(SISTER_LOG_FILE, 'r') as f:
            return set(line.strip() for line in f if line.strip() and not line.strip().startswith('#'))
    return set()


def save_sister_posted_link(url):
    """Save a URL as sister-posted"""
    with open(SISTER_LOG_FILE, 'a') as f:
        f.write(f"{url}\n")


def scrape_blog_post(url):
    """Scrape a blog post to find product mentions and featured image"""
    try:
        print(f"🔍 Scraping blog post: {url}")
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; ShopifyAutoposter/1.0)'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Get the blog post title
        title = ''
        title_tag = soup.find('h1') or soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
        
        # Get the featured image (og:image)
        image_url = ''
        og_image = soup.find('meta', property='og:image')
        if og_image:
            image_url = og_image.get('content', '')
        
        # Get all text content to detect product keywords
        body_text = soup.get_text().lower()
        
        # Find which products are mentioned
        detected_products = []
        for keyword, product_info in PRODUCT_KEYWORDS.items():
            if keyword in body_text:
                detected_products.append(product_info)
        
        # Remove duplicates (same shop_url)
        seen_urls = set()
        unique_products = []
        for p in detected_products:
            if p['shop_url'] not in seen_urls:
                seen_urls.add(p['shop_url'])
                unique_products.append(p)
        
        return {
            'title': title,
            'url': url,
            'image_url': image_url,
            'products': unique_products
        }
    except Exception as e:
        print(f"❌ Error scraping blog post: {e}")
        return None


def build_facebook_caption(blog_data, product):
    """Build a Facebook caption for the product spotlight"""
    emoji = product['emoji']
    name = product['name']
    shop_url = product['shop_url']
    blog_title = blog_data['title']
    blog_url = blog_data['url']
    
    caption = f"""{emoji} Inspired by our latest blog post!

We just published "{blog_title}" and wanted to spotlight the products that make it all possible.

✨ Featured: {name}

Whether you're just discovering us or already a fan, our {name} collection is exactly what your routine needs.

📖 Read the full article: {blog_url}

🛍️ Shop now: {shop_url}

Questions? Drop them in the comments below! We love hearing from you. 💬

#WaxAndWane #ShopSmall #SmallBusiness {product['hashtags']}"""
    
    return caption


def build_instagram_caption(blog_data, product):
    """Build an Instagram caption for the product spotlight"""
    emoji = product['emoji']
    name = product['name']
    
    caption = f"""{emoji} We just dropped a new blog post and had to spotlight this!

{name} - because your routine deserves the best.

👆 Link in bio to shop + read the full article!

{product['hashtags']} #ShopSmall #SmallBusiness #WaxAndWane"""
    
    return caption


def post_to_facebook(image_url, caption):
    """Post to Facebook Page"""
    if not ENABLE_FACEBOOK:
        print("⏭️  Facebook posting disabled")
        return None
    
    try:
        print("📘 Creating Facebook sister post...")
        url = f"https://graph.facebook.com/v25.0/{FACEBOOK_PAGE_ID}/photos"
        
        payload = {
            'url': image_url,
            'caption': caption,
            'access_token': FACEBOOK_PAGE_TOKEN
        }
        
        response = requests.post(url, data=payload)
        response.raise_for_status()
        
        post_id = response.json().get('id')
        post_url = f"https://www.facebook.com/{post_id}"
        print(f"✅ Facebook sister post created: {post_url}")
        return post_url
    except Exception as e:
        print(f"❌ Facebook posting failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text}")
        return None


def post_to_instagram(image_url, caption):
    """Post to Instagram (2-step process)"""
    if not ENABLE_INSTAGRAM:
        print("⏭️  Instagram posting disabled")
        return None
    
    try:
        print("📷 Creating Instagram sister post (step 1/2)...")
        
        # Step 1: Create container
        container_url = f"https://graph.facebook.com/v25.0/{INSTAGRAM_USER_ID}/media"
        container_payload = {
            'image_url': image_url,
            'caption': caption,
            'access_token': INSTAGRAM_ACCESS_TOKEN
        }
        
        container_response = requests.post(container_url, data=container_payload)
        container_response.raise_for_status()
        container_id = container_response.json().get('id')
        
        print(f"📷 Container created: {container_id}")
        time.sleep(5)
        
        # Step 2: Publish container
        print("📷 Publishing Instagram sister post (step 2/2)...")
        publish_url = f"https://graph.facebook.com/v25.0/{INSTAGRAM_USER_ID}/media_publish"
        publish_payload = {
            'creation_id': container_id,
            'access_token': INSTAGRAM_ACCESS_TOKEN
        }
        
        publish_response = requests.post(publish_url, data=publish_payload)
        publish_response.raise_for_status()
        media_id = publish_response.json().get('id')
        
        post_url = f"https://www.instagram.com/p/{media_id}"
        print(f"✅ Instagram sister post published: {post_url}")
        return post_url
    except Exception as e:
        print(f"❌ Instagram posting failed: {e}")
        return None


def main():
    """Main execution function"""
    print("=" * 60)
    print("🌸 Sister Posts Automation - Smart Product Spotlight")
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Get the most recent blog post
    recent_blog_url = get_most_recent_blog_post()
    if not recent_blog_url:
        return
    
    # Check if we already made a sister post for this blog
    sister_posted = load_sister_posted_links()
    if recent_blog_url in sister_posted:
        print(f"ℹ️  Sister post already created for: {recent_blog_url}")
        print("ℹ️  No new sister post needed today")
        return
    
    print(f"\n📰 Creating sister post for: {recent_blog_url}")
    
    # Scrape the blog post
    blog_data = scrape_blog_post(recent_blog_url)
    if not blog_data:
        print("❌ Could not scrape blog post")
        return
    
    print(f"📝 Blog title: {blog_data['title']}")
    print(f"🖼️  Featured image: {blog_data['image_url']}")
    print(f"🏷️  Products detected: {len(blog_data['products'])}")
    
    if not blog_data['products']:
        print("⚠️  No specific products detected - using general store spotlight")
        # Default to general store post
        blog_data['products'] = [{
            'name': 'Wax + Wane Collection',
            'shop_url': STORE_URL,
            'hashtags': '#WaxAndWane #ShopSmall #Wellness #KBeauty #Crystals #EMFProtection',
            'emoji': '✨🌙'
        }]
    
    if not blog_data['image_url']:
        print("❌ No featured image found - cannot post to Instagram")
        return
    
    # Use the first detected product for the spotlight
    product = blog_data['products'][0]
    print(f"\n🎯 Spotlighting: {product['name']}")
    
    # Build captions
    fb_caption = build_facebook_caption(blog_data, product)
    ig_caption = build_instagram_caption(blog_data, product)
    
    print(f"\n📝 Facebook caption preview:\n{fb_caption[:200]}...")
    
    # Post to platforms
    fb_url = post_to_facebook(blog_data['image_url'], fb_caption)
    time.sleep(2)
    ig_url = post_to_instagram(blog_data['image_url'], ig_caption)
    
    # Mark as sister-posted
    if fb_url or ig_url:
        save_sister_posted_link(recent_blog_url)
        print(f"\n✅ Sister post complete!")
        print(f"   Blog: {recent_blog_url}")
        print(f"   Facebook: {fb_url or 'Failed'}")
        print(f"   Instagram: {ig_url or 'Failed'}")
    
    print("\n" + "=" * 60)
    print("🌸 Sister post automation complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
