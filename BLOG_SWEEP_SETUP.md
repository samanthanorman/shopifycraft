# Blog Sweep — Setup Guide

**Updated setup: credentials now live in a `.env` file (not hardcoded in the script).**

---

## Step 1 — Install Python dependencies

Press **Command + Space**, type `Terminal`, press Enter. Then paste this and press Enter:

```
pip3 install requests google-genai python-dotenv
```

Wait ~30 seconds. You will never need to do this again.

---

## Step 2 — Create your `.env` credentials file

1. In the same folder as `blog_sweep.py`, find the file called `.env.example`
2. **Duplicate** it and rename the copy to just `.env` (no "example")
3. Open `.env` in TextEdit or any text editor
4. Fill in your real credentials:

```
SHOPIFY_STORE=6f97d0.myshopify.com
SHOPIFY_TOKEN=shpat_your_actual_token_here
GEMINI_API_KEY=AIzaSy_your_actual_key_here
```

5. Save and close

> **IMPORTANT:** The `.env` file is secret. Never share it, never upload it to GitHub.
> It is already listed in `.gitignore` so it cannot be accidentally committed.

---

## Step 3 — Put the Scripts on Your Desktop

1. Find the files `blog_sweep.py`, `.env`, and `RUN_BLOG_SWEEP.command`
2. Put **all three files** in the **same folder** on your Desktop (e.g., a folder called `WaxWane Scripts`)
3. Right-click `RUN_BLOG_SWEEP.command` → **Open** (first time only — Mac will ask for permission)
4. Click **Open** on the security prompt

---

## Run It Anytime

From now on: **double-click `RUN_BLOG_SWEEP.command`**

A Terminal window opens, runs the sweep, and closes. Every ingredient, mineral, and EMF guide entry that does not have a blog post yet gets a draft blog post created in Shopify automatically. All posts are created as **drafts** — you review and publish them yourself.

---

## When to Run It

| Trigger | Action |
|---|---|
| You add a new ingredient, mineral, or EMF entry | Run it |
| Quarterly (Jan, Apr, Jul, Oct) | Run it — refreshes evergreen content |
| After a big metaobject data entry session | Run it |

---

## What It Creates

- One **draft blog post per new entry** in the correct Shopify blog
- Post title: `[Ingredient/Mineral Name] — Complete Guide`
- Content: AI-written, SEO-rich, based entirely on your metaobject data
- Status: **Draft** (hidden from public until you publish)
- You can edit, add images, and publish from Shopify Admin → Content → Blog Posts

---

## When You Rotate Your Shopify Token

1. Go to **Shopify Admin → Settings → Apps → Develop apps**
2. Click your app → **API credentials → Rotate API credentials**
3. Copy the new `shpat_...` token
4. Open your `.env` file
5. Replace the old token value on the `SHOPIFY_TOKEN=` line
6. Save — done. The script picks it up automatically next run.

---

## Troubleshooting

| Error | Fix |
|---|---|
| `SHOPIFY_TOKEN is not set` | Check your `.env` file exists and has the right token |
| `GEMINI_API_KEY is not set` | Check your `.env` file has your Gemini key |
| `command not found: pip3` | Run: `python3 -m ensurepip --upgrade` |
| `401 Unauthorized` | Your Shopify token expired — rotate it (see above) |
| Script runs but creates 0 posts | All entries already have blog posts — that is a good thing! |
