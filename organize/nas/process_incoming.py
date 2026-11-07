#!/usr/bin/env python3
"""
One-shot pipeline for new downloads dropped into an incoming/ folder:
  clean folder name -> flatten subfolders -> delete images/junk -> renumber videos
  -> move into the main library (merging + renumbering if the model already exists)
Run on the NAS. Processes one model folder at a time, so it's safe to re-run
if interrupted (already-processed folders will simply be gone from incoming/).
"""
import os
import sys
import re
import shutil
import subprocess
import plistlib
from pacman_bar import PacmanBar as tqdm

VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.ts'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
JUNK_EXTS = {'.txt', '.pdf'}
JUNK_NAMES = {'.ds_store'}

# Tags can stack (e.g. Red+Purple for a nude favorite). Lower number = higher
# priority in sort. Order: Red+Purple, Blue+Purple, Purple alone, Orange,
# Blue, Red, Yellow, untagged.
RED, BLUE, ORANGE, PURPLE, YELLOW = 5, 4, 7, 3, 6

def clean_name(name):
    name = re.sub(r'\s*\S*4lm\.\w+$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*-\s*TG\b.*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*@\S+.*$', '', name)
    # drop parenthetical role/kink tags entirely, e.g. "Archie Choi (Stepgf)" -> "Archie Choi"
    name = re.sub(r'\s*\([^)]*\)', '', name)
    # drop filler prefixes glued onto a capitalized name, e.g. "itsKenzieReeves", "TheJhonniBlaze"
    # (scoped (?i:) so the uppercase lookahead stays case-sensitive — otherwise IGNORECASE
    # would let it match a lowercase letter too, e.g. "Themba" -> "mba")
    name = re.sub(r'^(?i:its|the)(?=[A-Z])', '', name)
    name = name.replace('&', 'and')
    # split camelCase word boundaries before lowercasing (e.g. AlaineCheeks -> Alaine_Cheeks)
    name = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', name)
    name = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', '_', name)
    name = name.lower()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'_+', '_', name)
    return name.strip('_')

def collect_files(model_path):
    """Recursively list all files under model_path, for dry-run previews only."""
    return [os.path.join(root, f) for root, _, fnames in os.walk(model_path) for f in fnames]

def classify(files):
    video = junk = other = 0
    for p in files:
        fname = os.path.basename(p)
        ext = os.path.splitext(fname)[1].lower()
        if ext in VIDEO_EXTS:
            video += 1
        elif ext in IMAGE_EXTS or ext in JUNK_EXTS or fname.lower() in JUNK_NAMES:
            junk += 1
        else:
            other += 1
    return video, junk, other

def flatten(model_path):
    for subdir in [e for e in os.scandir(model_path) if e.is_dir()]:
        for entry in os.scandir(subdir.path):
            if not entry.is_file():
                continue
            dest = os.path.join(model_path, entry.name)
            if os.path.exists(dest):
                base, ext = os.path.splitext(entry.name)
                n = 2
                while os.path.exists(os.path.join(model_path, f"{base}_{n}{ext}")):
                    n += 1
                dest = os.path.join(model_path, f"{base}_{n}{ext}")
            shutil.move(entry.path, dest)
        try:
            os.rmdir(subdir.path)
        except OSError:
            pass

def delete_images(model_path):
    count = 0
    for entry in os.scandir(model_path):
        if not entry.is_file():
            continue
        ext = os.path.splitext(entry.name)[1].lower()
        if ext in IMAGE_EXTS or ext in JUNK_EXTS or entry.name.lower() in JUNK_NAMES:
            os.remove(entry.path)
            count += 1
    return count

def get_tag_colors(filepath):
    # os.listxattr/os.getxattr are Linux-only in the stdlib — not available on macOS.
    # Shell out to the `xattr` CLI instead, same approach as safe_dedup.py.
    result = subprocess.run(
        ['xattr', '-px', 'com.apple.metadata:_kMDItemUserTags', filepath],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        return set()
    try:
        hex_data = result.stdout.strip().replace(' ', '').replace('\n', '')
        tags = plistlib.loads(bytes.fromhex(hex_data))
        colors = set()
        for tag in tags:
            parts = tag.split('\n')
            if len(parts) > 1:
                colors.add(int(parts[1]))
        return colors
    except Exception:
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

def renumber(model_path, model_name):
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

def merge_into_library(incoming_model_path, library_model_path, model_name):
    videos = [
        e for e in os.scandir(incoming_model_path)
        if e.is_file() and os.path.splitext(e.name)[1].lower() in VIDEO_EXTS
    ]
    for v in videos:
        dest = os.path.join(library_model_path, v.name)
        if os.path.exists(dest):
            base, ext = os.path.splitext(v.name)
            n = 2
            while os.path.exists(os.path.join(library_model_path, f"{base}_{n}{ext}")):
                n += 1
            dest = os.path.join(library_model_path, f"{base}_{n}{ext}")
        shutil.move(v.path, dest)
    return renumber(library_model_path, model_name)

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    apply = '--apply' in sys.argv

    if len(args) != 2:
        print("Usage: python3 process_incoming.py <incoming_path> <library_path> [--apply]")
        print("  Default is dry-run (reports only). Pass --apply to actually process.")
        sys.exit(1)

    incoming = args[0].rstrip('/')
    library = args[1].rstrip('/')

    print("APPLY MODE — files will be renamed/moved/deleted\n" if apply
          else "DRY RUN — no changes will be made (pass --apply to process)\n")

    model_dirs = [
        e for e in os.scandir(incoming)
        if e.is_dir() and not e.name.startswith('.')
    ]
    print(f"Found {len(model_dirs)} folders in incoming\n")

    new_count = merge_count = 0

    for entry in tqdm(model_dirs, desc="Processing incoming", unit=" models"):
        name = clean_name(entry.name)
        library_model_path = os.path.join(library, name)

        if not apply:
            files = collect_files(entry.path)
            video_count, junk_count, other_count = classify(files)
            top_level = sum(1 for e in os.scandir(entry.path) if e.is_file())
            nested = len(files) - top_level

            if os.path.exists(library_model_path):
                existing_videos = sum(
                    1 for e in os.scandir(library_model_path)
                    if e.is_file() and os.path.splitext(e.name)[1].lower() in VIDEO_EXTS
                )
                tqdm.write(f"WOULD MERGE: '{entry.name}' -> {name} "
                           f"({video_count} incoming + {existing_videos} existing = "
                           f"{video_count + existing_videos} videos total; "
                           f"delete {junk_count} images/junk; flatten {nested} nested files)")
                merge_count += 1
            else:
                tqdm.write(f"WOULD ADD NEW: '{entry.name}' -> {name} "
                           f"({video_count} videos; delete {junk_count} images/junk; "
                           f"flatten {nested} nested files)")
                new_count += 1

            if other_count:
                tqdm.write(f"  WARNING: {other_count} file(s) with unrecognized extension(s) "
                           f"would be flattened/moved as-is, not deleted — check these")
            continue

        src_path = entry.path
        if name != entry.name:
            new_path = os.path.join(incoming, name)
            os.rename(src_path, new_path)
            src_path = new_path

        flatten(src_path)
        n_images = delete_images(src_path)

        if os.path.exists(library_model_path):
            count = merge_into_library(src_path, library_model_path, name)
            try:
                os.rmdir(src_path)
            except OSError:
                tqdm.write(f"  {name}: leftover files in incoming (not removed)")
            merge_count += 1
            tqdm.write(f"MERGED: {name} -> {count} videos total (deleted {n_images} images)")
        else:
            renumber(src_path, name)
            shutil.move(src_path, library_model_path)
            new_count += 1
            tqdm.write(f"NEW: {name} (deleted {n_images} images)")

    print(f"\n{'Done' if apply else 'Dry run complete'} — New: {new_count} | Merged: {merge_count}")
    if not apply:
        print("Pass --apply to actually process these folders.")

if __name__ == '__main__':
    main()
