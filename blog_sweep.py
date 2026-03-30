#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  WAX | WANE — Blog Sweep Automation Script                          ║
║  Double-click to run from your Mac desktop                          ║
║                                                                      ║
║  What this does:                                                     ║
║  1. Reads ALL active ingredient_profile, mineral, and emf_guide     ║
║     metaobject entries from your Shopify store                      ║
║  2. Checks if a blog post already exists for each one               ║
║  3. For any entry WITHOUT a blog post → generates a full SEO-rich   ║
║     draft using Google Gemini AI                                    ║
║  4. Creates the draft blog post in Shopify (status: hidden/draft)   ║
║  5. Links the blog post back to the metaobject entry                ║
║                                                                      ║
║  Run quarterly for evergreen refresh, or any time you add new       ║
║  entries to any of the three metaobject types.                      ║
║                                                                      ║
║  SETUP (one time only):                                             ║
║  1. pip3 install requests google-genai python-dotenv                ║
║  2. Edit the .env file in the same folder as this script            ║
║     (see .env.example for the format)                               ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import requests
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# ── LOAD .env FILE (if present) ───────────────────────────────────────
# This lets you store credentials in a .env file next to this script
# instead of hardcoding them here. NEVER commit .env to GitHub.
try:
    from dotenv import load_dotenv
    # Look for .env in the same directory as this script
    env_path = Path(__file__).parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass  # dotenv not installed — fall back to system env vars only

# ── CONFIG ────────────────────────────────────────────────────────────
# Credentials come from environment variables (set in .env file or
# system environment). Never hardcode tokens in this file.
SHOP          = os.environ.get('SHOPIFY_STORE', '6f97d0.myshopify.com')
SHOPIFY_TOKEN = os.environ.get('SHOPIFY_TOKEN', '')
GEMINI_KEY    = os.environ.get('GEMINI_API_KEY', '')

# ── VALIDATE CREDENTIALS ──────────────────────────────────────────────
if not SHOPIFY_TOKEN:
    print("❌  SHOPIFY_TOKEN is not set.")
    print("    Edit the .env file next to this script and add:")
    print("    SHOPIFY_TOKEN=shpat_your_token_here")
    print("    Then save and run again.")
    sys.exit(1)

if not GEMINI_KEY:
    print("❌  GEMINI_API_KEY is not set.")
    print("    Edit the .env file next to this script and add:")
    print("    GEMINI_API_KEY=AIzaSy_your_key_here")
    print("    Then save and run again.")
    sys.exit(1)

# Blog IDs — the Shopify blog each post type should go into
# These are fetched automatically below; set manually if needed
BLOG_MAP = {
    'ingredient_profile': 'HARAMOON - THE K-BEAUTY BLOG',
    'mineral':            'Crystals - Minerals - Materials Blog',
    'emf_guide':          'EMF and EMI',
}

# ── HEADERS ───────────────────────────────────────────────────────────
HEADERS = {
    'X-Shopify-Access-Token': SHOPIFY_TOKEN,
    'Content-Type': 'application/json'
}

# ─────────────────────────────────────────────────────────────────────
# STEP 0: Validate Gemini key
# ─────────────────────────────────────────────────────────────────────
try:
    from google import genai
    gemini_client = genai.Client(api_key=GEMINI_KEY)
    print("✅  Gemini AI connected")
except ImportError:
    print("⚠️  google-genai not installed. Run: pip3 install google-genai")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────
# STEP 1: Get all Shopify blog IDs
# ─────────────────────────────────────────────────────────────────────
def get_blog_ids():
    r = requests.get(f'https://{SHOP}/admin/api/2024-10/blogs.json', headers=HEADERS)
    blogs = r.json().get('blogs', [])
    return {b['title']: b['id'] for b in blogs}

# ─────────────────────────────────────────────────────────────────────
# STEP 2: Get all metaobjects of a given type
# ─────────────────────────────────────────────────────────────────────
def get_all_metaobjects(obj_type):
    entries = []
    cursor  = None
    while True:
        after = f', after: "{cursor}"' if cursor else ''
        query = f'''
        {{
          metaobjects(type: "{obj_type}", first: 50{after}) {{
            pageInfo {{ hasNextPage endCursor }}
            nodes {{
              id
              handle
              fields {{ key value }}
            }}
          }}
        }}
        '''
        r    = requests.post(f'https://{SHOP}/admin/api/2024-10/graphql.json',
                             headers=HEADERS, json={'query': query})
        data = r.json().get('data', {}).get('metaobjects', {})
        entries.extend(data.get('nodes', []))
        pi = data.get('pageInfo', {})
        if pi.get('hasNextPage'):
            cursor = pi['endCursor']
        else:
            break
    return entries

# ─────────────────────────────────────────────────────────────────────
# STEP 3: Check if a blog post already exists for a metaobject
# ─────────────────────────────────────────────────────────────────────
def get_field(entry, key):
    for f in entry['fields']:
        if f['key'] == key:
            return f['value'] or ''
    return ''

def already_has_blog(entry, obj_type):
    """Returns True if the metaobject has a blog_post field already set."""
    val = get_field(entry, 'blog_post')
    return bool(val and val != 'null')

# ─────────────────────────────────────────────────────────────────────
# STEP 4: Generate blog post content with Gemini
# ─────────────────────────────────────────────────────────────────────
def build_prompt_ingredient(entry):
    name        = get_field(entry, 'name')
    origin      = get_field(entry, 'ingredient_origin')
    function_   = get_field(entry, 'main_function')
    description = get_field(entry, 'description')
    benefits    = get_field(entry, 'skin_benefits')
    l1          = get_field(entry, 'l1')
    l2          = get_field(entry, 'l2')
    cautions    = get_field(entry, 'cautions_side_effects')
    sub_cat     = get_field(entry, 'sub_category')

    return f"""You are a Korean skincare expert and science writer for Wax | Wane, a niche wellness store in Lincoln, Nebraska.
Write a comprehensive, SEO-rich blog post about the skincare ingredient: {name}

Use this data as your source of truth:
- Origin: {origin}
- Main Function: {function_}
- Description: {description}
- Key Benefits: {benefits}
- Science Note 1: {l1}
- Science Note 2: {l2}
- Cautions: {cautions}
- Usage Notes: {sub_cat}

Blog post requirements:
- Title: Use Title Case. Make it search-intent focused (e.g. "Niacinamide in Korean Skincare: What It Does and Why It Works")
- Length: 600-900 words
- Structure: Intro -> What It Is -> How It Works -> Key Benefits -> Who It's For -> How to Use -> Cautions -> Conclusion
- Tone: Educational, warm, trustworthy -- like a knowledgeable friend, not a salesperson
- SEO: Naturally include the ingredient name 5-8 times. Include related terms.
- Include a "Found in HARAMOON Products" paragraph if the ingredient is commonly found in Korean skincare routines
- End with a CTA linking to the Wax | Wane ingredient glossary: https://waxandwane.store/pages/ultimate-korean-skincare-ingredient-glossary
- DO NOT use markdown headers with # -- use plain text section labels in bold instead
- Return ONLY the blog post HTML (use <h2>, <p>, <strong>, <ul>, <li> tags). No preamble, no explanation."""


def build_prompt_mineral(entry):
    name        = get_field(entry, 'display_name')
    one_liner   = get_field(entry, 'one_liner')
    description = get_field(entry, 'seo_description')
    energy      = get_field(entry, 'energy_properties')
    element     = get_field(entry, 'element')
    chakra      = get_field(entry, 'chakra')
    zodiac      = get_field(entry, 'zodiac')
    history     = get_field(entry, 'history')
    modern_use  = get_field(entry, 'modern_or_scientific_use')
    why_need    = get_field(entry, 'why_you_need_it')
    origin      = get_field(entry, 'origin')
    hardness    = get_field(entry, 'mohs_hardness')
    formula     = get_field(entry, 'chemical_formula')
    archetype   = get_field(entry, 'archetype')

    return f"""You are a crystal and mineral expert and writer for Wax | Wane, a niche wellness store in Lincoln, Nebraska.
Write a comprehensive, SEO-rich blog post about the crystal/mineral: {name}

Use this data as your source of truth:
- One-liner: {one_liner}
- Description: {description}
- Energy Properties: {energy}
- Element: {element}
- Chakra: {chakra}
- Zodiac: {zodiac}
- History: {history}
- Modern/Scientific Use: {modern_use}
- Why You Need It: {why_need}
- Origin: {origin}
- Mohs Hardness: {hardness}
- Chemical Formula: {formula}
- Archetype: {archetype}

Blog post requirements:
- Title: Use Title Case. Make it search-intent focused (e.g. "Amethyst Crystal Meaning, Properties & How to Use It")
- Length: 600-900 words
- Structure: Intro -> What It Is (geology/science) -> History & Lore -> Energy & Metaphysical Properties -> Who It's For -> How to Use & Care -> Conclusion
- Tone: Grounded, curious, respectful -- informative without being mystical or dismissive
- SEO: Naturally include the crystal name 5-8 times. Include related terms.
- End with a CTA linking to the Wax | Wane Crystal Compendium: https://waxandwane.store/pages/crystal-compendium
- DO NOT use markdown headers with # -- use plain text section labels in bold instead
- Return ONLY the blog post HTML (use <h2>, <p>, <strong>, <ul>, <li> tags). No preamble, no explanation."""


def build_prompt_emf(entry):
    name        = get_field(entry, 'name') or get_field(entry, 'title')
    description = get_field(entry, 'description') or get_field(entry, 'body')

    return f"""You are an EMF protection expert and science writer for Wax | Wane, a niche wellness store in Lincoln, Nebraska.
Write a comprehensive, SEO-rich blog post about the EMF topic: {name}

Background: {description}

Blog post requirements:
- Title: Use Title Case. Make it search-intent focused
- Length: 600-900 words
- Structure: Intro -> What It Is -> The Science -> Why It Matters -> How to Protect Yourself -> Product Solutions -> Conclusion
- Tone: Factual, calm, empowering -- not fear-mongering, not dismissive
- SEO: Naturally include the topic 5-8 times. Include related terms.
- End with a CTA linking to the Wax | Wane EMF guide: https://waxandwane.store/pages/emf
- DO NOT use markdown headers with # -- use plain text section labels in bold instead
- Return ONLY the blog post HTML (use <h2>, <p>, <strong>, <ul>, <li> tags). No preamble, no explanation."""


def generate_blog_content(prompt):
    response = gemini_client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    return response.text.strip()


# ─────────────────────────────────────────────────────────────────────
# STEP 5: Create draft blog post in Shopify
# ─────────────────────────────────────────────────────────────────────
def create_blog_post(blog_id, title, body_html, tags, handle):
    payload = {
        'article': {
            'title':      title,
            'body_html':  body_html,
            'tags':       tags,
            'published':  False,   # Draft -- you review and publish
            'handle':     handle,
        }
    }
    r = requests.post(
        f'https://{SHOP}/admin/api/2024-10/blogs/{blog_id}/articles.json',
        headers=HEADERS,
        json=payload
    )
    if r.status_code in (200, 201):
        return r.json()['article']
    else:
        print(f"    WARNING: Failed to create post: {r.status_code} -- {r.text[:200]}")
        return None


# ─────────────────────────────────────────────────────────────────────
# STEP 6: Link the blog post back to the metaobject
# ─────────────────────────────────────────────────────────────────────
def link_blog_to_metaobject(metaobject_id, article_id):
    article_gid = f'gid://shopify/Article/{article_id}'
    mutation = '''
    mutation UpdateMetaobject($id: ID!, $metaobject: MetaobjectUpdateInput!) {
      metaobjectUpdate(id: $id, metaobject: $metaobject) {
        metaobject { id handle }
        userErrors { field message }
      }
    }
    '''
    variables = {
        'id': metaobject_id,
        'metaobject': {
            'fields': [
                {'key': 'blog_post', 'value': article_gid}
            ]
        }
    }
    r = requests.post(
        f'https://{SHOP}/admin/api/2024-10/graphql.json',
        headers=HEADERS,
        json={'query': mutation, 'variables': variables}
    )
    data = r.json()
    errors = data.get('data', {}).get('metaobjectUpdate', {}).get('userErrors', [])
    if errors:
        print(f"    WARNING: Link error: {errors}")


# ─────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────
def main():
    print("\n" + "="*60)
    print("  WAX | WANE -- Blog Sweep")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*60)

    # Get blog IDs
    print("\n Loading Shopify blogs...")
    blog_ids = get_blog_ids()
    print(f"   Found blogs: {list(blog_ids.keys())}")

    total_created = 0
    total_skipped = 0

    # Process each metaobject type
    sweep_types = [
        ('ingredient_profile', build_prompt_ingredient, 'name',         'Korean Skincare, Ingredients, K-Beauty, HARAMOON'),
        ('mineral',            build_prompt_mineral,    'display_name',  'Crystals, Minerals, Healing Crystals, Crystal Compendium'),
        ('emf_guide',          build_prompt_emf,        'name',          'EMF Protection, EMF Shielding, 5G, RF Radiation'),
    ]

    for obj_type, prompt_fn, name_key, default_tags in sweep_types:
        blog_title  = BLOG_MAP.get(obj_type, '')
        blog_id     = blog_ids.get(blog_title)

        if not blog_id:
            print(f"\nWARNING: Blog '{blog_title}' not found -- skipping {obj_type}")
            continue

        print(f"\n{'─'*60}")
        print(f"  Processing: {obj_type}")
        print(f"  Blog: {blog_title} (ID: {blog_id})")
        print(f"{'─'*60}")

        entries = get_all_metaobjects(obj_type)
        print(f"  Found {len(entries)} entries")

        for entry in entries:
            name = get_field(entry, name_key) or entry['handle']

            if already_has_blog(entry, obj_type):
                print(f"  SKIP (has blog): {name}")
                total_skipped += 1
                continue

            print(f"  Generating blog for: {name}")

            try:
                prompt    = prompt_fn(entry)
                body_html = generate_blog_content(prompt)

                # Extract title from first <h2> or generate one
                import re
                h2_match = re.search(r'<h2[^>]*>(.*?)</h2>', body_html, re.IGNORECASE | re.DOTALL)
                if h2_match:
                    post_title = re.sub(r'<[^>]+>', '', h2_match.group(1)).strip()
                else:
                    post_title = f"{name}: Complete Guide"

                post_handle = entry['handle']
                tags        = f"{default_tags}, {name}"

                article = create_blog_post(blog_id, post_title, body_html, tags, post_handle)

                if article:
                    print(f"     Created draft: '{post_title}' (ID: {article['id']})")
                    # Link back to metaobject
                    link_blog_to_metaobject(entry['id'], article['id'])
                    total_created += 1
                    time.sleep(0.5)  # Rate limit courtesy pause

            except Exception as e:
                print(f"     ERROR for {name}: {e}")
                continue

    print(f"\n{'='*60}")
    print(f"  SWEEP COMPLETE")
    print(f"  New drafts created: {total_created}")
    print(f"  Already had blogs:  {total_skipped}")
    print(f"  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    print(f"\n  Review your drafts at:")
    print(f"     https://admin.shopify.com/store/6f97d0/blogs")
    print(f"\n  Run this script quarterly to refresh evergreen content.\n")


if __name__ == '__main__':
    main()
