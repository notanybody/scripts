#!/usr/bin/env python3
"""
Sort loose files in hentai/images/ by filename-origin pattern (not content
tagging — see conversation 2026-10-24 for why bulk Danbooru tagging isn't
practical here). Artist-tagged filenames (Sankaku format, embeds character/
artist in the name) move into the existing 'by creator/<artist>/' structure.
Everything else groups by platform-of-origin pattern into consolidated
subfolders under images/. Files matching no known pattern are left loose.

Default is DRY RUN. Pass --apply to actually create folders and move files.

Usage:
  python3 sort_hentai_images.py <hentai_path> [--apply]
"""
import os
import re
import sys
import shutil

def classify(fname):
    if '_drawn_by_' in fname:
        m = re.search(r'_drawn_by_([a-zA-Z0-9_]+?)(__|_sample-|\.\w+$)', fname)
        artist = m.group(1).replace('_', ' ').lower() if m else 'unknown artist'
        return ('artist', artist)
    if re.match(r'^IMG_\d+( \d)?\.(JPG|JPEG|PNG|HEIC)$', fname, re.IGNORECASE):
        return ('bucket', 'screenshots photos')
    if re.match(r'^\d{8}_\d{6}\.\w+$', fname) or re.match(r'^Screenshot_\d+_\d+\.\w+$', fname):
        return ('bucket', 'screenshots photos')
    if re.match(r'^photo_\d{4}-\d{2}-\d{2}[ _]\d{2}\.\d{2}\.\d{2}.*\.\w+$', fname):
        return ('bucket', 'screenshots photos')
    if re.match(r'^\d{13}\.\w+$', fname):
        return ('bucket', 'telegram')
    if re.match(r'^(sample[-_])[a-f0-9]{32,40}\.\w+$', fname, re.IGNORECASE):
        return ('bucket', 'booru downloads')
    if re.match(r'^[a-f0-9]{32}\.\w+$', fname):
        return ('bucket', 'booru downloads')
    if re.match(r'^\d+_p\d+(_master\d+)?.*\.\w+$', fname):
        return ('bucket', 'pixiv')
    if re.match(r'^[A-Z][A-Za-z0-9_-]{9,17}( \(\d+\))?\.(jpg|jpeg|png)$', fname):
        return ('bucket', 'social media')
    if re.match(r'^\d{9,}_\d+_\d+_\d+_n\.\w+$', fname):
        return ('bucket', 'social media')
    if re.match(r'^RDT_.*\.\w+$', fname):
        return ('bucket', 'social media')
    if re.match(r'^unknown[ _]?\(?\d+\)?( \d)?\.\w+$', fname, re.IGNORECASE):
        return ('bucket', 'unknown')
    return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 sort_hentai_images.py <hentai_path> [--apply]")
        sys.exit(1)

    base = sys.argv[1].rstrip('/')
    images_dir = os.path.join(base, 'images')
    creator_dir = os.path.join(base, 'by creator')
    apply = '--apply' in sys.argv

    print("APPLY MODE — folders will be created and files moved\n" if apply
          else "DRY RUN — no changes will be made (pass --apply to move)\n")

    files = sorted(
        e.name for e in os.scandir(images_dir)
        if e.is_file() and not e.name.startswith('.')
    )

    counts = {}
    unmatched = 0

    for fname in files:
        result = classify(fname)
        if not result:
            unmatched += 1
            continue
        kind, target = result
        dest_dir = os.path.join(creator_dir, target) if kind == 'artist' else os.path.join(images_dir, target)
        src = os.path.join(images_dir, fname)
        dest = os.path.join(dest_dir, fname)

        counts[target] = counts.get(target, 0) + 1

        if apply:
            os.makedirs(dest_dir, exist_ok=True)
            if os.path.exists(dest):
                print(f"  SKIP (exists at destination): {fname}")
                continue
            shutil.move(src, dest)
        else:
            label = f"by creator/{target}" if kind == 'artist' else f"images/{target}"
            print(f"  WOULD MOVE: {fname} -> {label}/")

    print(f"\n{'Moved' if apply else 'Would move'} by destination:")
    for target, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {target}: {n}")
    print(f"\nUnmatched (left loose): {unmatched}")

if __name__ == '__main__':
    main()
