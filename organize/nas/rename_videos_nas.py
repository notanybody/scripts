#!/usr/bin/env python3
import os
import sys
import plistlib
from tqdm import tqdm

VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}

# Tags can stack (e.g. Red+Purple for a nude favorite). Lower number = higher
# priority in sort. Order: Red+Purple, Blue+Purple, Purple alone, Orange,
# Blue, Red, Yellow, untagged.
RED, BLUE, ORANGE, PURPLE, YELLOW = 5, 4, 7, 3, 6

def find_tag_attr(filepath):
    """Find the correct xattr name for Apple tags on this filesystem."""
    try:
        attrs = os.listxattr(filepath)
        for attr in attrs:
            if 'kMDItemUserTags' in attr:
                return attr
    except OSError:
        pass
    return None

def get_tag_colors(filepath):
    attr_name = find_tag_attr(filepath)
    if not attr_name:
        return set()
    try:
        data = os.getxattr(filepath, attr_name)
        tags = plistlib.loads(data)
        colors = set()
        for tag in tags:
            parts = tag.split('\n')
            if len(parts) > 1:
                colors.add(int(parts[1]))
        return colors
    except (OSError, Exception):
        return set()

def get_tag_priority(filepath):
    colors = get_tag_colors(filepath)
    if RED in colors and PURPLE in colors:
        return 0
    if BLUE in colors and PURPLE in colors:
        return 1
    if PURPLE in colors:
        return 2
    if ORANGE in colors:
        return 3
    if BLUE in colors:
        return 4
    if RED in colors:
        return 5
    if YELLOW in colors:
        return 6
    return 7  # untagged

def get_creation_time(filepath):
    return os.path.getmtime(filepath)

def rename_model(model_path, model_name, apply):
    videos = [
        e.path for e in os.scandir(model_path)
        if e.is_file() and os.path.splitext(e.name)[1].lower() in VIDEO_EXTS
    ]

    if not videos:
        return 0, 0

    videos.sort(key=lambda p: (get_tag_priority(p), get_creation_time(p)))

    pad = len(str(len(videos)))
    renamed = failed = 0

    if apply:
        # Two-pass rename to avoid collisions
        temp_paths = []
        for src in videos:
            tmp = src + '.__tmp__'
            try:
                os.rename(src, tmp)
                temp_paths.append((tmp, os.path.splitext(src)[1].lower()))
            except Exception as e:
                tqdm.write(f"FAILED (temp): {os.path.basename(src)} ({e})")
                temp_paths.append((src, os.path.splitext(src)[1].lower()))
                failed += 1

        for i, (tmp, ext) in enumerate(temp_paths, 1):
            new_name = f"{model_name.lower().replace(' ', '_')}_{str(i).zfill(pad)}{ext}"
            new_path = os.path.join(model_path, new_name)
            try:
                os.rename(tmp, new_path)
                renamed += 1
            except Exception as e:
                tqdm.write(f"FAILED: {os.path.basename(tmp)} ({e})")
                failed += 1
    else:
        for i, src in enumerate(videos, 1):
            ext = os.path.splitext(src)[1].lower()
            new_name = f"{model_name.lower().replace(' ', '_')}_{str(i).zfill(pad)}{ext}"
            tqdm.write(f"  WOULD RENAME: {os.path.basename(src)} -> {new_name}")
            renamed += 1

    return renamed, failed

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 rename_videos_nas.py <library_path> [--apply]")
        print("  Default is dry-run. Pass --apply to actually rename.")
        sys.exit(1)

    base = os.path.expanduser(sys.argv[1].rstrip('/'))
    apply = '--apply' in sys.argv

    if apply:
        print("APPLY MODE — files will be renamed\n")
    else:
        print("DRY RUN — no changes will be made (pass --apply to rename)\n")

    model_dirs = sorted(
        [d for d in os.scandir(base) if d.is_dir() and not d.name.startswith('.')],
        key=lambda d: d.name
    )

    total_renamed = total_failed = 0

    for model in tqdm(model_dirs, desc="Renaming videos", unit=" models"):
        renamed, failed = rename_model(model.path, model.name, apply)
        total_renamed += renamed
        total_failed += failed
        tqdm.write(f"Done: {model.name} — {'Renamed' if apply else 'Would rename'}: {renamed} | Failed: {failed}")

    print(f"\nDone — {'Renamed' if apply else 'Would rename'}: {total_renamed} | Failed: {total_failed}")

if __name__ == '__main__':
    main()
