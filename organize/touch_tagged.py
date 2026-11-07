#!/usr/bin/env python3
"""Bump the mtime of every Finder-tagged file in a library to right now, so an
external "keep most recently modified" dedup tool (e.g. the UGREEN NAS Files
app's dedup feature) will always prefer a tagged copy over an untagged
duplicate.

NOTE: if a duplicate group has 2+ tagged copies, this does NOT disambiguate
between them — they all get touched to ~now, so which one the external tool
keeps is effectively arbitrary (whichever touch() call landed last). This is
exactly the case safe_dedup.py flags for manual review instead of resolving.

Default is DRY RUN — only reports what it would touch. Pass --apply to
actually update timestamps.

Usage:
  python3 touch_tagged.py <path>            # dry run, report only
  python3 touch_tagged.py <path> --apply     # actually touch tagged files
"""
import os
import sys
import subprocess
import plistlib
from pacman_bar import PacmanBar as tqdm

def has_tags(filepath):
    result = subprocess.run(
        ['xattr', '-px', 'com.apple.metadata:_kMDItemUserTags', filepath],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        return False
    try:
        hex_data = result.stdout.strip().replace(' ', '').replace('\n', '')
        data = plistlib.loads(bytes.fromhex(hex_data))
        return len(data) > 0
    except Exception:
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 touch_tagged.py <path> [--apply]")
        print("  Default is dry-run. Pass --apply to actually touch files.")
        sys.exit(1)

    base = sys.argv[1].rstrip('/')
    apply = '--apply' in sys.argv

    print("APPLY MODE — tagged files will have their mtime bumped to now\n" if apply
          else "DRY RUN — no changes will be made (pass --apply to touch)\n")

    all_files = []
    for root, dirs, files in os.walk(base):
        for fname in files:
            if fname.startswith('.') or fname == 'info.txt':
                continue
            all_files.append(os.path.join(root, fname))

    print(f"Scanning {len(all_files)} files for tags...\n")

    touched = failed = 0
    for path in tqdm(all_files, desc="Checking tags", unit=" files"):
        if has_tags(path):
            if apply:
                try:
                    os.utime(path, None)
                except OSError as e:
                    tqdm.write(f"FAILED: {path} ({e})")
                    failed += 1
                    continue
            touched += 1

    print(f"\n{'Touched' if apply else 'Would touch'}: {touched} tagged files"
          + (f" | Failed: {failed}" if failed else ""))
    if not apply:
        print("Pass --apply to actually update timestamps.")

if __name__ == '__main__':
    main()
