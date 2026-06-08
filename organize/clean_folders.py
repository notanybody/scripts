#!/usr/bin/env python3
import os
import sys
import re
from tqdm import tqdm

def clean_name(name):
    # Strip "- TG" and similar suffixes before the @ handle
    name = re.sub(r'\s*-\s*TG\b.*$', '', name, flags=re.IGNORECASE)
    # Strip @handle suffixes (Telegram, etc.)
    name = re.sub(r'\s*@\S+.*$', '', name)
    # Replace & with and
    name = name.replace('&', 'and')
    # Lowercase
    name = name.lower()
    # Remove special characters except spaces
    name = re.sub(r'[^\w\s]', '', name)
    # Replace spaces with underscores
    name = re.sub(r'\s+', '_', name)
    # Collapse multiple underscores
    name = re.sub(r'_+', '_', name)
    # Strip leading/trailing underscores
    name = name.strip('_')
    return name

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 clean_folders.py <path> [--apply]")
        print("  Default is dry-run. Pass --apply to actually rename.")
        sys.exit(1)

    base = sys.argv[1].rstrip('/')
    apply = '--apply' in sys.argv

    if apply:
        print("APPLY MODE — folders will be renamed\n")
    else:
        print("DRY RUN — no changes will be made (pass --apply to rename)\n")

    renamed = skipped = conflicts = 0
    entries = sorted([e for e in os.scandir(base) if e.is_dir()], key=lambda e: e.name)
    renames = []
    conflict_list = []

    for entry in tqdm(entries, desc="Cleaning folder names", unit=" folders"):
        original = entry.name
        cleaned = clean_name(original)

        if original == cleaned:
            skipped += 1
            continue

        new_path = os.path.join(base, cleaned)
        if os.path.exists(new_path):
            tqdm.write(f"CONFLICT: '{original}' -> '{cleaned}' (already exists)")
            conflict_list.append((original, cleaned))
            conflicts += 1
            continue

        tqdm.write(f"{'RENAME' if apply else 'WOULD RENAME'}: '{original}' -> '{cleaned}'")
        renames.append((original, cleaned))

        if apply:
            os.rename(entry.path, new_path)
        renamed += 1

    print(f"\n{'Renamed' if apply else 'Would rename'}: {renamed} | Already clean: {skipped} | Conflicts: {conflicts}")

    if not apply:
        report_path = os.path.join(os.path.expanduser('~'), 'scripts', 'folder_rename_preview.md')
        with open(report_path, 'w') as f:
            f.write("# Folder Rename Preview\n\n")
            f.write(f"## Would Rename ({len(renames)})\n\n")
            f.write("| Original | Cleaned |\n|---|---|\n")
            for orig, clean in renames:
                f.write(f"| {orig} | {clean} |\n")
            f.write(f"\n## Conflicts ({len(conflict_list)})\n\n")
            f.write("| Original | Conflicts With |\n|---|---|\n")
            for orig, clean in conflict_list:
                f.write(f"| {orig} | {clean} |\n")
        print(f"\nPreview saved to {report_path}")

if __name__ == '__main__':
    main()
