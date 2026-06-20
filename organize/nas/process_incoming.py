#!/usr/bin/env python3
"""
One-shot pipeline for new downloads dropped into an incoming/ folder:
  clean folder name -> flatten subfolders -> delete images -> renumber videos
  -> move into the main library (merging + renumbering if the model already exists)
Run on the NAS. Processes one model folder at a time, so it's safe to re-run
if interrupted (already-processed folders will simply be gone from incoming/).
"""
import os
import sys
import re
import shutil
import plistlib
from tqdm import tqdm

VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

# Lower number = higher priority in sort (matches rename_videos_nas.py)
TAG_PRIORITY = {
    4: 0,  # Blue
    5: 1,  # Red
    7: 2,  # Orange
    3: 3,  # Purple
    6: 4,  # Yellow
}

def clean_name(name):
    name = re.sub(r'\s*-\s*TG\b.*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*@\S+.*$', '', name)
    name = name.replace('&', 'and')
    name = name.lower()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'_+', '_', name)
    return name.strip('_')

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
        if entry.is_file() and os.path.splitext(entry.name)[1].lower() in IMAGE_EXTS:
            os.remove(entry.path)
            count += 1
    return count

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
    if len(sys.argv) != 3:
        print("Usage: python3 process_incoming.py <incoming_path> <library_path>")
        sys.exit(1)

    incoming = sys.argv[1].rstrip('/')
    library = sys.argv[2].rstrip('/')

    model_dirs = [
        e for e in os.scandir(incoming)
        if e.is_dir() and not e.name.startswith('.')
    ]
    print(f"Found {len(model_dirs)} folders in incoming\n")

    new_count = merge_count = 0

    for entry in tqdm(model_dirs, desc="Processing incoming", unit=" models"):
        name = clean_name(entry.name)
        src_path = entry.path
        if name != entry.name:
            new_path = os.path.join(incoming, name)
            os.rename(src_path, new_path)
            src_path = new_path

        flatten(src_path)
        n_images = delete_images(src_path)

        library_model_path = os.path.join(library, name)
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

    print(f"\nDone — New: {new_count} | Merged: {merge_count}")

if __name__ == '__main__':
    main()
