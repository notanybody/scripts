#!/usr/bin/env python3
"""Build an index of favorite-tagged files (Purple or Orange) for the random-launcher.
Optimization: tag_audit.md already lists untagged files per model, so tagged files =
(all files in model) - (untagged files) — avoids re-scanning all 233K files' xattrs,
only checks colors on the ~4,600 that are actually tagged.
"""
import os
import re
import subprocess
import plistlib

BASE = "/Volumes/personal_folder/division/onlyfans"
TAG_AUDIT = "/Users/jackwillis/scripts/tag_audit.md"
OUT_PATH = "/Users/jackwillis/scripts/organize/favorites_index.txt"

VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

RED, BLUE, ORANGE, PURPLE, YELLOW = 5, 4, 7, 3, 6
FAVORITE_COLORS = {PURPLE, ORANGE}
COLOR_NAMES = {1: 'Gray', 2: 'Green', 3: 'Purple', 4: 'Blue', 5: 'Red', 6: 'Yellow', 7: 'Orange'}

# --- parse tag_audit.md: model -> set of untagged filenames ---
untagged_by_model = {}
current_model = None
with open(TAG_AUDIT) as f:
    for line in f:
        m = re.match(r'^## (.+) \(\d+ untagged\)', line)
        if m:
            current_model = m.group(1)
            untagged_by_model[current_model] = set()
            continue
        m2 = re.match(r'^- (.+)$', line)
        if m2 and current_model:
            untagged_by_model[current_model].add(m2.group(1).strip())

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

favorites = []
checked = 0
model_dirs = sorted(
    [d for d in os.scandir(BASE) if d.is_dir() and not d.name.startswith('.')],
    key=lambda d: d.name
)

for model in model_dirs:
    untagged_set = untagged_by_model.get(model.name, set())
    try:
        all_files = [
            e.name for e in os.scandir(model.path)
            if e.is_file() and not e.name.startswith('.') and e.name != 'info.txt'
            and os.path.splitext(e.name)[1].lower() in (VIDEO_EXTS | IMAGE_EXTS)
        ]
    except OSError:
        continue
    tagged_candidates = [f for f in all_files if f not in untagged_set]
    for fname in tagged_candidates:
        fpath = os.path.join(model.path, fname)
        colors = get_tag_colors(fpath)
        checked += 1
        if colors & FAVORITE_COLORS:
            label = '+'.join(COLOR_NAMES.get(c, '?') for c in sorted(colors))
            favorites.append((fpath, label))

with open(OUT_PATH, 'w') as f:
    for fpath, label in favorites:
        f.write(f"{fpath}\t{label}\n")

print(f"Checked {checked} already-tagged files")
print(f"Favorites found (Purple/Orange): {len(favorites)}")
print(f"Index written to {OUT_PATH}")
