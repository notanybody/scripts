#!/usr/bin/env python3
import os
import sys
import plistlib
from tqdm import tqdm

VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

def find_tag_attr(filepath):
    try:
        attrs = os.listxattr(filepath)
        for attr in attrs:
            if 'kMDItemUserTags' in attr:
                return attr
    except OSError:
        pass
    return None

def has_tags(filepath):
    attr_name = find_tag_attr(filepath)
    if not attr_name:
        return False
    try:
        data = os.getxattr(filepath, attr_name)
        tags = plistlib.loads(data)
        return len(tags) > 0
    except (OSError, Exception):
        return False

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 tag_audit_nas.py <library_path>")
        sys.exit(1)

    base = os.path.expanduser(sys.argv[1].rstrip('/'))
    model_dirs = sorted(
        [d for d in os.scandir(base) if d.is_dir() and not d.name.startswith('.')],
        key=lambda d: d.name
    )

    untagged_by_model = {}
    total_files = 0
    total_untagged = 0

    for model in tqdm(model_dirs, desc="Auditing tags", unit=" models"):
        untagged = []
        for entry in os.scandir(model.path):
            ext = os.path.splitext(entry.name)[1].lower()
            if not entry.is_file() or entry.name.startswith('.') or entry.name == 'info.txt':
                continue
            if ext not in VIDEO_EXTS and ext not in IMAGE_EXTS:
                continue
            total_files += 1
            if not has_tags(entry.path):
                untagged.append(entry.name)
                total_untagged += 1
        if untagged:
            untagged_by_model[model.name] = untagged
        tqdm.write(f"Done: {model.name} — {len(untagged)} untagged")

    report_path = os.path.join(os.path.expanduser('~'), 'scripts', 'tag_audit.md')
    with open(report_path, 'w') as f:
        f.write("# Tag Audit Report\n\n")
        f.write(f"**Total files scanned:** {total_files}  \n")
        f.write(f"**Untagged files:** {total_untagged}  \n")
        f.write(f"**Models with untagged files:** {len(untagged_by_model)}\n\n")

        for model_name in sorted(untagged_by_model.keys()):
            files = untagged_by_model[model_name]
            f.write(f"## {model_name} ({len(files)} untagged)\n\n")
            for fname in sorted(files):
                f.write(f"- {fname}\n")
            f.write("\n")

    print(f"\nTotal files: {total_files} | Untagged: {total_untagged} | Models affected: {len(untagged_by_model)}")
    print(f"Report saved to {report_path}")

if __name__ == '__main__':
    main()
