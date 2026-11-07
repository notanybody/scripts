#!/usr/bin/env python3
"""Pick a random favorite (Purple/Orange tagged) file and open it. Instant — reads the
pre-built index, no scanning. Re-run build_favorites_index.py periodically to refresh it
as you tag more files.
Usage: python3 random_fav.py [color filter, e.g. Purple, Orange, Red+Purple]
"""
import random
import subprocess
import sys

INDEX_PATH = "/Users/jackwillis/scripts/organize/favorites_index.txt"

with open(INDEX_PATH) as f:
    lines = [l.rstrip('\n').split('\t') for l in f if l.strip()]

if len(sys.argv) > 1:
    filt = sys.argv[1].lower()
    lines = [l for l in lines if filt in l[1].lower()]

if not lines:
    print("No matching favorites in the index.")
    sys.exit(1)

path, label = random.choice(lines)
print(f"[{label}] {path}")
subprocess.run(['open', path])
