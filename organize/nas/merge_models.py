#!/usr/bin/env python3
"""
Merges cleaned model folders from an external source into the main library:
  - Models that don't exist yet in the library are copied over wholesale (via rsync).
  - Models that already exist have their videos copied in, then the whole
    folder is renumbered sequentially by tag color + creation time, matching
    the convention established by rename_videos_nas.py.
"""
import os
import sys
import shutil
import subprocess
import plistlib
from tqdm import tqdm

VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}

# Lower number = higher priority in sort (matches rename_videos_nas.py)
TAG_PRIORITY = {
    4: 0,  # Blue
    5: 1,  # Red
    7: 2,  # Orange
    3: 3,  # Purple
    6: 4,  # Yellow
}

def find_tag_attr(filepath):
    try:
        for attr in os.listxattr(filepath):
            if 'kMDItemUserTags' in attr:
                return attr
    except OSError:
        pass
    return None

def get_tag_priority(filepath):
    attr_name = find_tag_attr(filepath)
    if not attr_name:
        return 6  # untagged
    try:
        tags = plistlib.loads(os.getxattr(filepath, attr_name))
        for tag in tags:
            parts = tag.split('\n')
            if len(parts) > 1:
                return TAG_PRIORITY.get(int(parts[1]), 5)
        return 5
    except (OSError, Exception):
        return 6

def renumber_model(model_path, model_name):
    videos = [
        e.path for e in os.scandir(model_path)
        if e.is_file() and os.path.splitext(e.name)[1].lower() in VIDEO_EXTS
    ]
    if not videos:
        return 0

    videos.sort(key=lambda p: (get_tag_priority(p), os.path.getmtime(p)))
    pad = len(str(len(videos)))

    temp_paths = []
    for src in videos:
        tmp = src + '.__tmp__'
        os.rename(src, tmp)
        temp_paths.append((tmp, os.path.splitext(src)[1].lower()))

    for i, (tmp, ext) in enumerate(temp_paths, 1):
        new_name = f"{model_name}_{str(i).zfill(pad)}{ext}"
        os.rename(tmp, os.path.join(model_path, new_name))

    return len(videos)

def stage_incoming(dest_path):
    """Move .__incoming__ files to their final names, avoiding collisions."""
    for staged in list(os.scandir(dest_path)):
        if not staged.name.endswith('.__incoming__'):
            continue
        orig = staged.name[:-len('.__incoming__')]
        target = os.path.join(dest_path, orig)
        if os.path.exists(target):
            base, ext = os.path.splitext(orig)
            n = 2
            while os.path.exists(os.path.join(dest_path, f"{base}_{n}{ext}")):
                n += 1
            target = os.path.join(dest_path, f"{base}_{n}{ext}")
        os.rename(staged.path, target)

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 merge_models.py <source_base> <dest_base> [--apply]")
        print("  Default is dry-run. Pass --apply to actually copy/merge.")
        sys.exit(1)

    source = sys.argv[1].rstrip('/')
    dest = sys.argv[2].rstrip('/')
    apply = '--apply' in sys.argv

    print("APPLY MODE — files will be copied/merged\n" if apply else "DRY RUN — no changes will be made (pass --apply to merge)\n")

    source_dirs = sorted(
        [d for d in os.scandir(source) if d.is_dir() and not d.name.startswith('.')],
        key=lambda d: d.name
    )

    new_models = [e for e in source_dirs if not os.path.exists(os.path.join(dest, e.name))]
    merge_models = [e for e in source_dirs if os.path.exists(os.path.join(dest, e.name))]

    print(f"New models to copy:        {len(new_models)}")
    print(f"Existing models to merge:  {len(merge_models)}\n")

    failed = 0

    for entry in tqdm(new_models, desc="Copying new models", unit=" models"):
        dest_path = os.path.join(dest, entry.name)
        if apply:
            result = subprocess.run(
                ['rsync', '-a', entry.path + '/', dest_path + '/'],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                tqdm.write(f"FAILED: {entry.name} ({result.stderr.strip()[:200]})")
                failed += 1
        else:
            tqdm.write(f"  WOULD COPY: {entry.name}")

    for entry in tqdm(merge_models, desc="Merging into existing models", unit=" models"):
        dest_path = os.path.join(dest, entry.name)
        videos = [
            e for e in os.scandir(entry.path)
            if e.is_file() and os.path.splitext(e.name)[1].lower() in VIDEO_EXTS
        ]
        if not apply:
            tqdm.write(f"  WOULD MERGE: {entry.name} (+{len(videos)} videos)")
            continue

        for v in videos:
            tmp_dest = os.path.join(dest_path, v.name + '.__incoming__')
            try:
                shutil.copy2(v.path, tmp_dest)
            except Exception as e:
                tqdm.write(f"  FAILED: {v.name} ({e})")
                failed += 1

        stage_incoming(dest_path)
        count = renumber_model(dest_path, entry.name)
        tqdm.write(f"  {entry.name}: merged and renumbered {count} videos total")

    print(f"\nDone — {'Copied' if apply else 'Would copy'}: {len(new_models)} new | "
          f"{'Merged' if apply else 'Would merge'}: {len(merge_models)} existing | Failed: {failed}")

    if merge_models:
        print(f"\nMerged models: {', '.join(e.name for e in merge_models)}")

if __name__ == '__main__':
    main()
