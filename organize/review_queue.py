#!/usr/bin/env python3
"""Build a prioritized model review queue: newest-added first, and biggest-untouched first.
Reads from tag_audit.md (untagged counts), index.md (size/count), and each model's info.txt (date added).
"""
import os
import re
from datetime import datetime

BASE = "/Volumes/personal_folder/division/onlyfans"
TAG_AUDIT = "/Users/jackwillis/scripts/tag_audit.md"
INDEX_MD = os.path.join(BASE, "index.md")
OUT_PATH = "/Users/jackwillis/scripts/organize/review_queue.md"

# --- untagged counts per model ---
untagged = {}
with open(TAG_AUDIT) as f:
    for line in f:
        m = re.match(r'^## (.+) \((\d+) untagged\)', line)
        if m:
            untagged[m.group(1)] = int(m.group(2))

# --- size/count per model from index.md ---
size_info = {}  # name -> (files, size_str, size_bytes_approx)
UNIT_MULT = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4}
with open(INDEX_MD) as f:
    for line in f:
        m = re.match(r'^\|\s*([\w.]+)\s*\|\s*(\d+)\s*\|\s*([\d.]+)\s*(\w+)\s*\|', line)
        if m:
            name, files, num, unit = m.group(1), int(m.group(2)), float(m.group(3)), m.group(4)
            bytes_ = num * UNIT_MULT.get(unit, 1)
            size_info[name] = (files, f"{num} {unit}", bytes_)

# --- real "newest content" signal: most recent file mtime per model ---
# (info.txt's "Date Added" is bulk-generated from the reorg script, not real — don't use it)
from pacman_bar import PacmanBar as tqdm

date_added = {}
model_dirs = [e for e in os.scandir(BASE) if e.is_dir() and not e.name.startswith('.')]
for entry in tqdm(model_dirs, desc="Scanning mtimes", unit=" models"):
    latest = None
    try:
        for f in os.scandir(entry.path):
            if not f.is_file() or f.name.startswith('.') or f.name == 'info.txt':
                continue
            try:
                mt = f.stat().st_mtime
            except OSError:
                continue
            if latest is None or mt > latest:
                latest = mt
    except OSError:
        continue
    if latest:
        date_added[entry.name] = datetime.fromtimestamp(latest)

# --- build queues (only models with untagged > 0) ---
candidates = [name for name, cnt in untagged.items() if cnt > 0]

recent_queue = sorted(
    (n for n in candidates if n in date_added),
    key=lambda n: date_added[n], reverse=True
)
big_queue = sorted(
    (n for n in candidates if n in size_info),
    key=lambda n: size_info[n][2], reverse=True
)

N = 30
with open(OUT_PATH, 'w') as f:
    f.write("# Review Queue\n\n")
    f.write(f"Total models with untagged files: {len(candidates)}\n\n")

    f.write(f"## Newest-added, top {N}\n\n")
    f.write("| Model | Date Added | Untagged | Files | Size |\n|---|---|---|---|---|\n")
    for n in recent_queue[:N]:
        files, size_str, _ = size_info.get(n, (0, '?', 0))
        f.write(f"| {n} | {date_added[n].date()} | {untagged[n]} | {files} | {size_str} |\n")

    f.write(f"\n## Biggest libraries, top {N}\n\n")
    f.write("| Model | Size | Files | Untagged |\n|---|---|---|---|\n")
    for n in big_queue[:N]:
        files, size_str, _ = size_info.get(n, (0, '?', 0))
        f.write(f"| {n} | {size_str} | {files} | {untagged[n]} |\n")

print(f"Recent-queue candidates: {len(recent_queue)} | Big-queue candidates: {len(big_queue)}")
print(f"Written to {OUT_PATH}")
print()
print("Top 10 newest-added:")
for n in recent_queue[:10]:
    print(f"  {n} — added {date_added[n].date()}, {untagged[n]} untagged")
print()
print("Top 10 biggest:")
for n in big_queue[:10]:
    files, size_str, _ = size_info.get(n, (0, '?', 0))
    print(f"  {n} — {size_str}, {untagged[n]} untagged")
