#!/usr/bin/env python3
"""
Groups the non-timestamped content in /division/random into a single downloaded/ folder:
  downloaded/images|videos/   - creator clips, compilations, scans, etc.
Files named like "2021-01-23 03.03.21.jpeg" are left in place.
Existing curated subfolders (e.g. "compilations", "vintage playboys") are moved under downloaded/
and their names cleaned to lowercase_with_underscores.
"""
import os
import sys
import re
import shutil
from tqdm import tqdm

TIMESTAMP_RE = re.compile(r'^(\d{4})-(\d{2})-(\d{2}) \d{2}\.\d{2}\.\d{2}')

def clean_name(name):
    return name.lower().replace(' ', '_')

def plan(base, subdir):
    src_dir = os.path.join(base, subdir)
    moves = []
    for entry in os.scandir(src_dir):
        if entry.name.startswith('.'):
            continue
        if entry.is_dir():
            dest = os.path.join(base, 'downloaded', subdir, clean_name(entry.name))
            moves.append((entry.path, dest, True))
        elif not TIMESTAMP_RE.match(entry.name):
            dest_dir = os.path.join(base, 'downloaded', subdir)
            moves.append((entry.path, os.path.join(dest_dir, entry.name), False))
    return moves

def unique_dest(dest):
    if not os.path.exists(dest):
        return dest, False
    d, name = os.path.split(dest)
    base_name, ext = os.path.splitext(name)
    n = 2
    while True:
        candidate = os.path.join(d, f"{base_name}_{n}{ext}")
        if not os.path.exists(candidate):
            return candidate, True
        n += 1

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 reorganize_random.py <random_path> [--apply]")
        print("  Default is dry-run. Pass --apply to actually move files.")
        sys.exit(1)

    base = os.path.expanduser(sys.argv[1].rstrip('/'))
    apply = '--apply' in sys.argv

    print("APPLY MODE — files will be moved\n" if apply else "DRY RUN — no changes will be made (pass --apply to move)\n")

    all_moves = []
    for subdir in ('images', 'videos'):
        all_moves.extend(plan(base, subdir))

    moved = renamed = failed = 0
    for src, dest, is_dir in tqdm(all_moves, desc="Reorganizing", unit=" items"):
        final_dest, was_renamed = (dest, False) if is_dir else unique_dest(dest)
        if was_renamed:
            renamed += 1

        rel_src = os.path.relpath(src, base)
        rel_dest = os.path.relpath(final_dest, base)

        if apply:
            try:
                os.makedirs(os.path.dirname(final_dest), exist_ok=True)
                shutil.move(src, final_dest)
                moved += 1
            except Exception as e:
                tqdm.write(f"FAILED: {rel_src} ({e})")
                failed += 1
        else:
            tqdm.write(f"  {rel_src} -> {rel_dest}")
            moved += 1

    # Clean up now-empty top-level images/videos dirs
    if apply:
        for subdir in ('images', 'videos'):
            src_dir = os.path.join(base, subdir)
            try:
                if not os.listdir(src_dir):
                    os.rmdir(src_dir)
            except OSError:
                pass

    print(f"\nDone — {'Moved' if apply else 'Would move'}: {moved} | Renamed (conflicts): {renamed} | Failed: {failed}")

if __name__ == '__main__':
    main()
