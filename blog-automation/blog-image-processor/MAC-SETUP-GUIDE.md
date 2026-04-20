# Mac Setup Guide — Blog Image Processor
### Do This Once. Then Forget About It Forever.

---

## What You're Setting Up

A folder on your Desktop that works like a little factory:
- Drop an image in → it gets rotated and cropped to blog size
- The result logs itself to your Google Drive spreadsheet
- It pushes itself to GitHub automatically
- **You never need to open Manus, GitHub, or Google Drive to make this happen**

---

## Step 1 — Download the Folder to Your Desktop

Open Terminal (press `Cmd + Space`, type "Terminal", press Enter) and paste this exactly:

```bash
cd ~/Desktop && git clone https://github.com/samanthanorman/shopifycraft.git && cp -r shopifycraft/blog-automation/blog-image-processor ~/Desktop/ && echo "Done! Folder is on your Desktop."
```

You should now see a folder called **blog-image-processor** on your Desktop.

---

## Step 2 — Install the Required Tools (One Time Only)

Paste this into Terminal:

```bash
pip3 install Pillow gspread google-auth
```

If you see "pip3: command not found", paste this first:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" && brew install python3
```
Then re-run the pip3 line above.

---

## Step 3 — Set Up Google Sheets Logging (One Time Only)

This lets the script write a log row to your spreadsheet automatically.

1. Go to: https://console.cloud.google.com
2. Create a new project (name it anything, like "Blog Automation")
3. Enable the **Google Sheets API** and **Google Drive API**
4. Go to **IAM & Admin → Service Accounts → Create Service Account**
5. Name it "blog-automation", click Create
6. Click the service account → Keys tab → Add Key → JSON
7. Download the JSON file
8. Rename it to `google-credentials.json`
9. Move it into: `~/Desktop/blog-image-processor/`
10. Open your Master Log spreadsheet and share it with the service account email
    (it looks like: blog-automation@your-project.iam.gserviceaccount.com)
    Give it **Editor** access

**If this feels like too much:** Skip it for now. The script still works — it just won't log to Sheets. You can always add it later.

---

## Step 4 — Set Up GitHub Push (One Time Only)

Install GitHub Desktop: https://desktop.github.com

1. Open GitHub Desktop → File → Clone Repository
2. Search for `shopifycraft` → Clone to `~/shopifycraft`
3. That's it. The script will push to this folder automatically.

---

## How to Use It Every Time

1. Drop your image into: `~/Desktop/blog-image-processor/input/`
2. Open Terminal and paste:

```bash
cd ~/Desktop/blog-image-processor && python3 run_on_mac.py
```

3. Your processed images appear in the `output/` folder
4. The log row is added to Google Sheets
5. GitHub is updated automatically

**Optional — add the blog title for better logging:**
```bash
python3 run_on_mac.py --title "1,2-Hexanediol — Preservative & Skin-Conditioning Agent" --blog "HARAMOON"
```

---

## If Something Breaks

The most common issues and their fixes:

| Error Message | Fix |
|---------------|-----|
| `ModuleNotFoundError: PIL` | Run: `pip3 install Pillow` |
| `ModuleNotFoundError: gspread` | Run: `pip3 install gspread google-auth` |
| `No images found in input/` | Make sure your image is in the `input/` folder, not the main folder |
| `GitHub push failed` | Open GitHub Desktop, sign in, and make sure `shopifycraft` is cloned to `~/shopifycraft` |
| `google-credentials.json not found` | Move your credentials file to `~/Desktop/blog-image-processor/` |

---

## Your Key Links (Bookmark These)

| What | Link |
|------|------|
| Master Log Spreadsheet | https://docs.google.com/spreadsheets/d/1NWx-XcBkO7ps1kVClr0w5crnG3uQAtwZayialUbHqJ8/edit |
| Google Drive Content Hub | https://drive.google.com/drive/folders/1fc0xWCe62N5tj1tNRy3QUZJiGnafhLKA |
| GitHub Repo | https://github.com/samanthanorman/shopifycraft/tree/samanthanorman-patch-1/blog-automation/blog-image-processor |

---

## Content Hub Folder Map (Google Drive)

```
🗂️ CONTENT HUB — Wax|Wane & HARAMOON Automation
├── 📝 Blog Automation — HARAMOON & Wax|Wane
├── 📱 Social Posting — Pinterest, Instagram, Facebook, LinkedIn
├── 🛒 Ad Campaigns — Amazon, Walmart, Meta
├── 🖼️ Images — Originals & Processed
├── 📊 Logs & Spreadsheets          ← Master Log lives here
├── 🔑 API Keys & Config            ← Store credentials docs here (never share)
├── 📦 Product Data — Shopify, Amazon, Walmart
└── 📧 Email Campaigns & Templates
```

---

*Last updated: April 2026 | Maintained by Manus for Samantha Norman*
*Questions? Start a new Manus chat and say "blog image processor setup issue"*
