#!/usr/bin/env python3
import os
import sys
import plistlib
from datetime import datetime
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

def find_tag_attr(filepath):
    try:
        attrs = os.listxattr(filepath)
        for attr in attrs:
            if 'kMDItemUserTags' in attr:
                return attr
    except OSError:
        pass
    return None

def get_tag_color(filepath):
    attr_name = find_tag_attr(filepath)
    if not attr_name:
        return None
    try:
        data = os.getxattr(filepath, attr_name)
        tags = plistlib.loads(data)
        for tag in tags:
            parts = tag.split('\n')
            if len(parts) > 1:
                return int(parts[1])
        return 0
    except (OSError, Exception):
        return None

def format_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

def get_creation_date(path):
    return datetime.fromtimestamp(os.path.getctime(path)).strftime('%Y-%m-%d')

def get_existing_notes(info_path):
    if not os.path.exists(info_path):
        return ''
    with open(info_path, 'r') as f:
        content = f.read()
    marker = 'Notes:\n'
    idx = content.find(marker)
    if idx != -1:
        return content[idx + len(marker):].strip()
    return ''

def generate_info(model_path, model_name):
    file_count = 0
    total_size = 0
    tag_counts = {}

    for entry in os.scandir(model_path):
        if not entry.is_file() or entry.name.startswith('.') or entry.name == 'info.txt':
            continue
        file_count += 1
        total_size += entry.stat().st_size
        color = get_tag_color(entry.path)
        if color and color in COLOR_NAMES:
            label = COLOR_NAMES[color]
        elif color == 0:
            label = 'Tagged (no color)'
        else:
            label = 'Untagged'
        tag_counts[label] = tag_counts.get(label, 0) + 1

    date_added = get_creation_date(model_path)

    tag_order = ['Blue', 'Red', 'Orange', 'Purple', 'Yellow', 'Gray', 'Green', 'Tagged (no color)', 'Untagged']
    tag_summary = ', '.join(
        f"{label} ({tag_counts[label]})"
        for label in tag_order if label in tag_counts
    )
    if not tag_summary:
        tag_summary = 'None'

    info_path = os.path.join(model_path, 'info.txt')
    existing_notes = get_existing_notes(info_path)

    with open(info_path, 'w') as f:
        f.write(f"Name: {model_name}\n")
        f.write(f"Date Added: {date_added}\n")
        f.write(f"File Count: {file_count}\n")
        f.write(f"Total Size: {format_size(total_size)}\n")
        f.write(f"Tags: {tag_summary}\n")
        f.write(f"\nNotes:\n{existing_notes}\n")

    return {'count': file_count, 'size': format_size(total_size), 'tags': tag_summary}

def generate_index(base, model_dirs, stats):
    index_path = os.path.join(base, 'index.md')
    groups = {}
    for model in model_dirs:
        letter = model.name[0].upper()
        if not letter.isalpha():
            letter = '#'
        groups.setdefault(letter, []).append(model.name)

    with open(index_path, 'w') as f:
        f.write("# Model Index\n\n")
        for letter in sorted(groups.keys(), key=lambda l: (l == '#', l)):
            f.write(f"## {letter}\n\n")
            f.write("| Name | Files | Size | Tags |\n")
            f.write("|---|---|---|---|\n")
            for name in sorted(groups[letter]):
                s = stats.get(name, {})
                f.write(f"| {name} | {s.get('count', 0)} | {s.get('size', '—')} | {s.get('tags', '—')} |\n")
            f.write("\n")

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 generate_info_nas.py <library_path>")
        sys.exit(1)

    base = os.path.expanduser(sys.argv[1].rstrip('/'))
    model_dirs = sorted(
        [d for d in os.scandir(base) if d.is_dir() and not d.name.startswith('.')],
        key=lambda d: d.name
    )

    print(f"Found {len(model_dirs)} model folders\n")

    stats = {}
    for model in tqdm(model_dirs, desc="Generating info files", unit=" models"):
        s = generate_info(model.path, model.name)
        stats[model.name] = s
        tqdm.write(f"Done: {model.name} — {s['count']} files, {s['size']}, {s['tags']}")

    generate_index(base, model_dirs, stats)
    print(f"\nDone — info.txt created/updated in {len(model_dirs)} folders")
    print(f"Index saved to {os.path.join(base, 'index.md')}")

if __name__ == '__main__':
    main()
