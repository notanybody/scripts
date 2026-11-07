#!/usr/bin/env python3
"""Generate rounded-square gradient app icons with a centered emoji glyph, then package as .icns."""
import subprocess
import shutil
import os
from PIL import Image, ImageDraw, ImageFont

SIZE = 1024
FONT_PATH = "/System/Library/Fonts/Apple Color Emoji.ttc"

ICONS = {
    "Start Session": {"emoji": "⚡", "colors": ((255, 94, 58), (255, 149, 0))},      # bolt, orange-red
    "Stash": {"emoji": "\U0001f3ac", "colors": ((88, 43, 168), (30, 20, 70))},           # clapper, purple-dark
    "Random Favorite": {"emoji": "\U0001f3b2", "colors": ((255, 45, 149), (168, 43, 158))}, # dice, pink-magenta
    "Random Hentai": {"emoji": "\U0001f338", "colors": ((255, 179, 217), (200, 120, 220))}, # cherry blossom, soft pink-purple
}

def rounded_square_gradient(size, c1, c2):
    base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    grad = Image.new("RGBA", (size, size))
    for y in range(size):
        t = y / size
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        for x in range(size):
            grad.putpixel((x, y), (r, g, b, 255))
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    radius = int(size * 0.22)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    base.paste(grad, (0, 0), mask)
    return base

def add_emoji(img, emoji, size):
    # Apple Color Emoji is a fixed-strike bitmap font; only its native size renders correctly.
    native = 160
    font = ImageFont.truetype(FONT_PATH, size=native)
    small = Image.new("RGBA", (native * 2, native * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(small)
    bbox = d.textbbox((0, 0), emoji, font=font, embedded_color=True)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pos = (native - w / 2 - bbox[0], native - h / 2 - bbox[1])
    d.text(pos, emoji, font=font, embedded_color=True)
    small = small.crop((0, 0, native * 2, native * 2))
    target = int(size * 0.6)
    small = small.resize((target, target), Image.LANCZOS)
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    layer.paste(small, ((size - target) // 2, (size - target) // 2), small)
    return Image.alpha_composite(img, layer)

def make_icns(app_name, emoji, colors, apps_dir):
    img = rounded_square_gradient(SIZE, *colors)
    img = add_emoji(img, emoji, SIZE)

    iconset_dir = f"/tmp/{app_name.replace(' ', '_')}.iconset"
    os.makedirs(iconset_dir, exist_ok=True)
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    for s in sizes:
        img.resize((s, s), Image.LANCZOS).save(f"{iconset_dir}/icon_{s}x{s}.png")
        if s <= 512:
            img.resize((s * 2, s * 2), Image.LANCZOS).save(f"{iconset_dir}/icon_{s}x{s}@2x.png")

    icns_path = f"/tmp/{app_name.replace(' ', '_')}.icns"
    subprocess.run(["iconutil", "-c", "icns", iconset_dir, "-o", icns_path], check=True)
    shutil.rmtree(iconset_dir)

    app_path = os.path.join(apps_dir, f"{app_name}.app")
    resources_dir = os.path.join(app_path, "Contents", "Resources")
    os.makedirs(resources_dir, exist_ok=True)
    shutil.copy(icns_path, os.path.join(resources_dir, "icon.icns"))
    print(f"Icon set for {app_name}")

apps_dir = os.path.expanduser("~/Applications")
for name, spec in ICONS.items():
    make_icns(name, spec["emoji"], spec["colors"], apps_dir)
