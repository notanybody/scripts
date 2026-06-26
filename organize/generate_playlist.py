#!/usr/bin/env python3
"""
Builds an .m3u playlist of tagged videos across all model folders, e.g.:
  python3 generate_playlist.py ~/library              -> favorites (Purple + Orange) (default)
  python3 generate_playlist.py ~/library red          -> any nude-tagged video
  python3 generate_playlist.py ~/library purple orange red blue yellow
Tags can stack (e.g. a video tagged Red+Purple is a nude favorite) — a video
matches if it carries ANY of the requested colors. Results are sorted by the
combined-tag priority order: Red+Purple, Blue+Purple, Purple alone, Orange,
Blue, Red, Yellow, untagged.
Open the resulting .m3u in VLC/IINA to play through your favorites in order.
"""
import os
import sys
import subprocess
import plistlib
from tqdm import tqdm

VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}

COLOR_NAMES = ['purple', 'blue', 'red', 'orange', 'yellow']
COLOR_CODES = {'purple': 3, 'blue': 4, 'red': 5, 'orange': 7, 'yellow': 6}
RED, BLUE, ORANGE, PURPLE, YELLOW = 5, 4, 7, 3, 6

def get_tag_colors(filepath):
    result = subprocess.run(
        ['xattr', '-px', 'com.apple.metadata:_kMDItemUserTags', filepath],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        return set()
    try:
        hex_data = result.stdout.strip().replace(' ', '').replace('\n', '')
        data = plistlib.loads(bytes.fromhex(hex_data))
        colors = set()
        for tag in data:
            parts = tag.split('\n')
            if len(parts) > 1:
                colors.add(int(parts[1]))
        return colors
    except Exception:
        return set()

def get_tag_priority(colors):
    if RED in colors and PURPLE in colors:
        return 0
    if BLUE in colors and PURPLE in colors:
        return 1
    if PURPLE in colors:
        return 2
    if ORANGE in colors:
        return 3
    if BLUE in colors:
        return 4
    if RED in colors:
        return 5
    if YELLOW in colors:
        return 6
    return 7  # untagged

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate_playlist.py <library_path> [color1 color2 ...]")
        print(f"  Colors (default: purple orange), any of: {', '.join(COLOR_NAMES)}")
        sys.exit(1)

    base = sys.argv[1].rstrip('/')
    requested = [c.lower() for c in sys.argv[2:]] or ['purple', 'orange']
    wanted_codes = {COLOR_CODES[c] for c in requested if c in COLOR_CODES}

    if not wanted_codes:
        print(f"No valid colors given. Choose from: {', '.join(COLOR_NAMES)}")
        sys.exit(1)

    print(f"Building playlist for: {', '.join(c.title() for c in requested if c in COLOR_CODES)}\n")

    model_dirs = sorted(
        [d for d in os.scandir(base) if d.is_dir() and not d.name.startswith('.')],
        key=lambda d: d.name
    )

    matches = []
    for model in tqdm(model_dirs, desc="Scanning models", unit=" models"):
        for entry in os.scandir(model.path):
            ext = os.path.splitext(entry.name)[1].lower()
            if not entry.is_file() or ext not in VIDEO_EXTS:
                continue
            colors = get_tag_colors(entry.path)
            if colors & wanted_codes:
                matches.append((get_tag_priority(colors), model.name, entry.path))

    matches.sort(key=lambda m: (m[0], m[1], m[2]))

    output = os.path.join(os.path.expanduser('~'), 'scripts', 'favorites.m3u')
    with open(output, 'w') as f:
        f.write("#EXTM3U\n")
        for _, _, path in matches:
            f.write(path + '\n')

    print(f"\nDone — {len(matches)} videos added to playlist")
    print(f"Saved to {output}")

if __name__ == '__main__':
    main()
