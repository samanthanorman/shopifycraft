"""
Blog Image Processor — rotate_blog_image.py
============================================
Rotates and crops any image to standard Shopify blog featured image dimensions.

Usage (local or via GitHub Actions):
    python rotate_blog_image.py --input path/to/image.png --direction right
    python rotate_blog_image.py --input path/to/image.png --direction both

Arguments:
    --input      Path to the source image file
    --direction  Rotation direction: "right" (90 CW), "left" (90 CCW), or "both"
    --output     Output directory (default: ./output)
    --width      Target width in pixels (default: 1200)
    --height     Target height in pixels (default: 628)

Blog: HARAMOON K-Beauty | Wax|Wane
Maintained in: samanthanorman/shopifycraft/blog-automation/blog-image-processor
"""

import argparse
import os
from pathlib import Path
from PIL import Image


TARGET_W_DEFAULT = 1200
TARGET_H_DEFAULT = 628


def fit_and_crop(img, target_w, target_h):
    """Scale image to fill target dimensions, then center-crop."""
    orig_w, orig_h = img.size
    scale = max(target_w / orig_w, target_h / orig_h)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def process_image(input_path, direction, output_dir, target_w, target_h):
    """Process the image and return list of saved output file paths."""
    img = Image.open(input_path)
    stem = Path(input_path).stem
    os.makedirs(output_dir, exist_ok=True)
    saved = []

    rotations = []
    if direction in ("right", "both"):
        rotations.append(("right", img.rotate(-90, expand=True)))
    if direction in ("left", "both"):
        rotations.append(("left", img.rotate(90, expand=True)))

    for label, rotated in rotations:
        cropped = fit_and_crop(rotated, target_w, target_h)
        out_path = os.path.join(output_dir, f"{stem}_blog_{label}.png")
        cropped.save(out_path)
        print(f"Saved ({label}): {out_path}  [{cropped.size[0]}x{cropped.size[1]}]")
        saved.append(out_path)

    return saved


def main():
    parser = argparse.ArgumentParser(
        description="Rotate and crop images for Shopify blog featured image."
    )
    parser.add_argument("--input",     required=True,  help="Path to source image")
    parser.add_argument("--direction", default="both", choices=["right", "left", "both"],
                        help="Rotation direction (default: both)")
    parser.add_argument("--output",    default="output", help="Output directory (default: ./output)")
    parser.add_argument("--width",     type=int, default=TARGET_W_DEFAULT, help="Target width px")
    parser.add_argument("--height",    type=int, default=TARGET_H_DEFAULT, help="Target height px")
    args = parser.parse_args()

    print(f"Processing: {args.input}")
    print(f"Direction:  {args.direction}")
    print(f"Target:     {args.width}x{args.height}px")
    print(f"Output dir: {args.output}")
    print("-" * 50)

    saved = process_image(args.input, args.direction, args.output, args.width, args.height)
    print("-" * 50)
    print(f"Done! {len(saved)} file(s) saved.")


if __name__ == "__main__":
    main()
