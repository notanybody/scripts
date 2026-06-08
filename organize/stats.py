#!/usr/bin/env python3
import os
import sys
import subprocess
import plistlib
from tqdm import tqdm

COLOR_NAMES = {
    1: 'Gray',
    2: 'Green',
    3: 'Purple',
    4: 'Blue',
    5: 'Red',
    6: 'Yellow',
    7: 'Orange',
}

TAG_ORDER = ['Blue', 'Red', 'Orange', 'Purple', 'Yellow', 'Gray', 'Green', 'Untagged']

def get_tag_color_name(filepath):
    result = subprocess.run(
        ['xattr', '-px', 'com.apple.metadata:_kMDItemUserTags', filepath],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        return 'Untagged'
    try:
        hex_data = result.stdout.strip().replace(' ', '').replace('\n', '')
        data = plistlib.loads(bytes.fromhex(hex_data))
        for tag in data:
            parts = tag.split('\n')
            if len(parts) > 1:
                return COLOR_NAMES.get(int(parts[1]), 'Other')
        return 'Other'
    except Exception:
        return 'Untagged'

def format_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 stats.py <library_path>")
        sys.exit(1)

    base = sys.argv[1].rstrip('/')
    model_dirs = sorted(
        [d for d in os.scandir(base) if d.is_dir() and not d.name.startswith('.')],
        key=lambda d: d.name
    )

    total_files = 0
    total_size = 0
    tag_totals = {}
    model_stats = []

    for model in tqdm(model_dirs, desc="Collecting stats", unit=" models"):
        count = 0
        size = 0
        for entry in os.scandir(model.path):
            if not entry.is_file() or entry.name.startswith('.') or entry.name == 'info.txt':
                continue
            count += 1
            size += entry.stat().st_size
            color = get_tag_color_name(entry.path)
            tag_totals[color] = tag_totals.get(color, 0) + 1
        total_files += count
        total_size += size
        model_stats.append((model.name, count, size))
        tqdm.write(f"Done: {model.name} — {count} files, {format_size(size)}")

    top_by_size = sorted(model_stats, key=lambda x: x[2], reverse=True)[:10]
    top_by_count = sorted(model_stats, key=lambda x: x[1], reverse=True)[:10]

    report_path = os.path.join(os.path.expanduser('~'), 'scripts', 'stats.md')
    with open(report_path, 'w') as f:
        f.write("# Library Stats\n\n")
        f.write(f"**Total models:** {len(model_dirs)}  \n")
        f.write(f"**Total files:** {total_files}  \n")
        f.write(f"**Total size:** {format_size(total_size)}\n\n")

        f.write("## Tag Distribution\n\n")
        f.write("| Tag | Count |\n|---|---|\n")
        for tag in TAG_ORDER:
            if tag in tag_totals:
                f.write(f"| {tag} | {tag_totals[tag]} |\n")
        for tag, count in tag_totals.items():
            if tag not in TAG_ORDER:
                f.write(f"| {tag} | {count} |\n")
        f.write("\n")

        f.write("## Top 10 by Size\n\n")
        f.write("| Model | Files | Size |\n|---|---|---|\n")
        for name, count, size in top_by_size:
            f.write(f"| {name} | {count} | {format_size(size)} |\n")
        f.write("\n")

        f.write("## Top 10 by File Count\n\n")
        f.write("| Model | Files | Size |\n|---|---|---|\n")
        for name, count, size in top_by_count:
            f.write(f"| {name} | {count} | {format_size(size)} |\n")

    print(f"\nTotal models: {len(model_dirs)} | Files: {total_files} | Size: {format_size(total_size)}")
    print(f"Report saved to {report_path}")

if __name__ == '__main__':
    main()
