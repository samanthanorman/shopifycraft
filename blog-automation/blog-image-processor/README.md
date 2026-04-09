# Blog Image Processor

Automatically rotates and crops any portrait-orientation image into a **Shopify blog featured image** (1200 × 628 px) using Python + Pillow.

---

## How It Works

| Step | What happens |
|------|-------------|
| 1 | You drop a new image into the `input/` folder and push to GitHub |
| 2 | GitHub Actions detects the new file and runs the workflow automatically |
| 3 | The script rotates the image 90° (right, left, or both) and center-crops to 1200×628 |
| 4 | The processed image is committed back to `output/` and also available as a downloadable artifact in the Actions tab |

---

## Folder Structure

```
blog-image-processor/
├── input/                  ← Drop your raw images here before pushing
├── output/                 ← Processed blog-ready images land here (auto-committed)
├── rotate_blog_image.py    ← The processing script (also runs locally)
├── README.md               ← This file
└── .github/
    └── workflows/
        └── process-blog-image.yml  ← GitHub Actions automation
```

---

## Running Locally (on your Mac)

You need Python 3 and Pillow installed once:

```bash
pip3 install Pillow
```

Then run:

```bash
python3 rotate_blog_image.py --input input/my-image.png --direction both
```

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--input` | *(required)* | Path to source image |
| `--direction` | `both` | `right` (90° CW), `left` (90° CCW), or `both` |
| `--output` | `./output` | Where to save processed files |
| `--width` | `1200` | Target width in pixels |
| `--height` | `628` | Target height in pixels |

---

## Triggering the Workflow Manually

1. Go to **GitHub.com → samanthanorman/shopifycraft**
2. Click the **Actions** tab
3. Select **Process Blog Featured Image**
4. Click **Run workflow**
5. Enter the image filename (e.g. `my-ingredient.png`) and direction
6. Click the green **Run workflow** button

The processed images will appear in `output/` and as a downloadable artifact.

---

## Blog Context

- **Blog:** HARAMOON K-Beauty & Wax|Wane
- **Posting schedule:** Tuesday · Thursday · Sunday
- **Featured image target size:** 1200 × 628 px (standard Shopify / Open Graph)
- **Maintained in:** `samanthanorman/shopifycraft`

---

*Last updated: April 2026*
