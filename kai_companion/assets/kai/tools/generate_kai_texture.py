#!/usr/bin/env python3
"""
Generate a proper albedo texture for Kai's 3D model.

Since all existing texture files are noise/static, this script creates
a new albedo texture by mapping Shiba Inu colors onto the UV layout.

Usage:
    python generate_kai_texture.py [--source kai_photo_clean.png] [--output kai_albedo_new.png]

The script:
1. Loads the source photo (plush Shiba reference)
2. Extracts the dominant color regions (black, tan/rust, cream/white)
3. Generates a 2048x2048 albedo texture with proper Shiba coloring
4. Saves to the output path

After generating, re-export from Blender:
    blender -b --python tools/export_kai_runtime_glb.py
"""

import argparse
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    print("Pillow required: pip install Pillow")
    sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description="Generate Kai albedo texture")
    parser.add_argument("--source", default="kai_photo_clean.png",
                        help="Source photo for color extraction")
    parser.add_argument("--output", default="kai_albedo_new.png",
                        help="Output texture path")
    parser.add_argument("--size", type=int, default=2048,
                        help="Texture resolution")
    return parser.parse_args()


# Shiba Inu black & tan color palette
COLORS = {
    "black": (35, 28, 22),           # Dark coat (back, head top, ears outer)
    "tan_dark": (145, 90, 45),       # Dark tan (deep markings)
    "tan_mid": (196, 120, 58),       # Mid tan (cheeks, eyebrows, legs)
    "tan_light": (215, 160, 100),    # Light tan (transition zones)
    "cream": (245, 230, 208),        # Cream (chest, muzzle, paws)
    "white": (255, 248, 240),        # White (chest center, paw tips)
    "nose": (30, 25, 22),            # Nose leather
}


def extract_colors_from_photo(source_path: str) -> dict:
    """Sample dominant colors from the source photo."""
    try:
        img = Image.open(source_path).convert("RGB")
        # Sample regions: top (black), sides (tan), center-bottom (cream)
        w, h = img.size
        samples = {
            "black": img.crop((w//4, 0, 3*w//4, h//4)),
            "tan": img.crop((0, h//4, w//3, 3*h//4)),
            "cream": img.crop((w//3, 2*h//4, 2*w//3, h)),
        }
        extracted = {}
        for name, region in samples.items():
            pixels = list(region.getdata())
            if pixels:
                avg = tuple(int(sum(c[i] for c in pixels) / len(pixels)) for i in range(3))
                extracted[name] = avg
        return extracted
    except Exception as e:
        print(f"Warning: Could not extract colors from photo: {e}")
        return {}


def generate_shiba_texture(size: int = 2048) -> Image.Image:
    """
    Generate a Shiba Inu albedo texture.

    This creates a procedural texture that approximates a black & tan Shiba
    Inu coat pattern. The UV mapping follows a typical animal UV layout where:
    - Center of the texture = body/torso
    - Top = head/ears
    - Bottom = legs/paws
    - Left/Right = sides
    """
    img = Image.new("RGB", (size, size), COLORS["black"])
    draw = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2

    # === Body (tan sides, black back) ===
    # Main body - tan on sides
    body_margin = size // 6
    draw.ellipse(
        [body_margin, body_margin, size - body_margin, size - body_margin],
        fill=COLORS["tan_mid"]
    )

    # Back stripe (black)
    back_width = size // 3
    draw.ellipse(
        [cx - back_width//2, 0, cx + back_width//2, size * 2//3],
        fill=COLORS["black"]
    )

    # === Chest (cream/white) ===
    chest_w = size // 4
    chest_h = size // 3
    draw.ellipse(
        [cx - chest_w//2, size//2 - chest_h//4, cx + chest_w//2, size//2 + chest_h//2],
        fill=COLORS["cream"]
    )

    # Chest center highlight
    draw.ellipse(
        [cx - chest_w//4, size//2, cx + chest_w//4, size//2 + chest_h//3],
        fill=COLORS["white"]
    )

    # === Head area (top of texture) ===
    head_cy = size // 5
    head_r = size // 4

    # Head base (black with tan cheeks)
    draw.ellipse(
        [cx - head_r, head_cy - head_r, cx + head_r, head_cy + head_r],
        fill=COLORS["black"]
    )

    # Tan cheeks
    cheek_r = head_r * 2 // 3
    draw.ellipse(
        [cx - head_r - cheek_r//2, head_cy - cheek_r//2,
         cx - head_r + cheek_r + cheek_r//2, head_cy + cheek_r + cheek_r//2],
        fill=COLORS["tan_mid"]
    )
    draw.ellipse(
        [cx + head_r - cheek_r - cheek_r//2, head_cy - cheek_r//2,
         cx + head_r + cheek_r//2, head_cy + cheek_r + cheek_r//2],
        fill=COLORS["tan_mid"]
    )

    # Cream muzzle
    muzzle_r = head_r // 2
    draw.ellipse(
        [cx - muzzle_r, head_cy + head_r//3, cx + muzzle_r, head_cy + head_r + muzzle_r//2],
        fill=COLORS["cream"]
    )

    # === Legs / paws (cream at bottom) ===
    paw_y = size * 5 // 6
    paw_r = size // 10
    for paw_x in [size//4, 3*size//4]:
        draw.ellipse(
            [paw_x - paw_r, paw_y - paw_r, paw_x + paw_r, paw_y + paw_r],
            fill=COLORS["cream"]
        )
        # Tan above paws
        draw.ellipse(
            [paw_x - paw_r, paw_y - paw_r * 2, paw_x + paw_r, paw_y],
            fill=COLORS["tan_mid"]
        )

    # === Inner ears (tan, top corners) ===
    ear_r = size // 8
    draw.ellipse([0, 0, ear_r * 2, ear_r * 2], fill=COLORS["tan_mid"])
    draw.ellipse([size - ear_r * 2, 0, size, ear_r * 2], fill=COLORS["tan_mid"])

    # === Apply soft blur for smooth color transitions ===
    img = img.filter(ImageFilter.GaussianBlur(radius=size // 64))

    # Add slight grain for realism
    import random
    random.seed(42)
    pixels = img.load()
    for y in range(0, size, 2):
        for x in range(0, size, 2):
            r, g, b = pixels[x, y]
            noise = random.randint(-8, 8)
            pixels[x, y] = (
                max(0, min(255, r + noise)),
                max(0, min(255, g + noise)),
                max(0, min(255, b + noise)),
            )

    return img


def main():
    args = parse_args()
    base_dir = os.path.dirname(os.path.abspath(__file__))

    source_path = os.path.join(base_dir, "..", args.source)
    output_path = os.path.join(base_dir, "..", args.output)

    print(f"[KAI_TEXTURE] Generating {args.size}x{args.size} albedo texture...")

    # Try to extract colors from source photo
    if os.path.exists(source_path):
        extracted = extract_colors_from_photo(source_path)
        if extracted:
            print(f"[KAI_TEXTURE] Extracted colors from photo: {extracted}")
            # Only override if extracted colors look reasonable
            for name, color in extracted.items():
                if all(0 <= c <= 255 for c in color):
                    brightness = sum(color) / 3
                    if name == "black" and brightness < 80:  # Must be dark
                        COLORS["black"] = color
                    elif name == "tan" and 80 < brightness < 200:  # Mid range
                        COLORS["tan_mid"] = color
                    elif name == "cream" and brightness > 180:  # Must be light
                        COLORS["cream"] = color
            print(f"[KAI_TEXTURE] Adjusted palette from photo")
    else:
        print(f"[KAI_TEXTURE] No source photo found at {source_path}, using default palette")

    print(f"[KAI_TEXTURE] Using palette: {COLORS}")

    img = generate_shiba_texture(args.size)
    img.save(output_path, "PNG")

    print(f"[KAI_TEXTURE] Saved to {output_path}")
    print(f"[KAI_TEXTURE] Next step: load this in Blender and re-export kai_textured.glb")
    print(f"[KAI_TEXTURE] Or: blender -b --python tools/export_kai_runtime_glb.py")


if __name__ == "__main__":
    main()
