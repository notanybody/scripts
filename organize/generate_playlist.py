#!/usr/bin/env python3
"""
Builds an .m3u playlist of tagged videos across all model folders, e.g.:
  python3 generate_playlist.py ~/library            -> Blue + Red (default)
  python3 generate_playlist.py ~/library blue       -> Blue only
  python3 generate_playlist.py ~/library blue red orange purple yellow
Open the resulting .m3u in VLC/IINA to play through your favorites in order.
"""
import os
import sys
import subprocess
import plistlib
from tqdm import tqdm

VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}

# Canonical priority order (matches rename_videos.py)
COLOR_ORDER = ['blue', 'red', 'orange', 'purple', 'yellow']
COLOR_CODES = {'blue': 4, 'red': 5, 'orange': 7, 'purple': 3, 'yellow': 6}

def get_tag_color(filepath):
    result = subprocess.run(
        ['xattr', '-px', 'com.apple.metadata:_kMDItemUserTags', filepath],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        hex_data = result.stdout.strip().replace(' ', '').replace('\n', '')
        data = plistlib.loads(bytes.fromhex(hex_data))
        for tag in data:
            parts = tag.split('\n')
            if len(parts) > 1:
                return int(parts[1])
        return None
    except Exception:
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate_playlist.py <library_path> [color1 color2 ...]")
        print(f"  Colors (default: blue red), in priority order: {', '.join(COLOR_ORDER)}")
        sys.exit(1)

    base = sys.argv[1].rstrip('/')
    requested = [c.lower() for c in sys.argv[2:]] or ['blue', 'red']
    wanted_codes = {COLOR_CODES[c]: COLOR_ORDER.index(c) for c in requested if c in COLOR_CODES}

    if not wanted_codes:
        print(f"No valid colors given. Choose from: {', '.join(COLOR_ORDER)}")
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
            color = get_tag_color(entry.path)
            if color in wanted_codes:
                matches.append((wanted_codes[color], model.name, entry.path))

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
