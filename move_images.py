#!/usr/bin/env python3
import os
import sys
import shutil
from tqdm import tqdm

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

def safe_dest(dest_dir, filename):
    dest = os.path.join(dest_dir, filename)
    if not os.path.exists(dest):
        return dest
    name, ext = os.path.splitext(filename)
    counter = 2
    while True:
        new_dest = os.path.join(dest_dir, f"{name}_{counter}{ext}")
        if not os.path.exists(new_dest):
            return new_dest
        counter += 1

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 move_images.py <library_path> <images_dest>")
        sys.exit(1)

    source = sys.argv[1].rstrip('/')
    dest = sys.argv[2].rstrip('/')

    os.makedirs(dest, exist_ok=True)

    image_files = []
    print("Scanning for images...")
    for root, dirs, files in os.walk(source, onerror=lambda e: None):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if os.path.splitext(f)[1].lower() in IMAGE_EXTS:
                image_files.append(os.path.join(root, f))

    print(f"Found {len(image_files)} images\n")

    moved = renamed = failed = 0

    for src_path in tqdm(image_files, desc="Moving images", unit=" files"):
        dest_path = safe_dest(dest, os.path.basename(src_path))
        renamed_flag = os.path.basename(dest_path) != os.path.basename(src_path)
        try:
            shutil.move(src_path, dest_path)
            if renamed_flag:
                tqdm.write(f"RENAMED: {os.path.basename(src_path)} -> {os.path.basename(dest_path)}")
                renamed += 1
            else:
                moved += 1
        except Exception as e:
            tqdm.write(f"FAILED: {os.path.basename(src_path)} ({e})")
            failed += 1

    print(f"\nDone — Moved: {moved} | Renamed: {renamed} | Failed: {failed}")

if __name__ == '__main__':
    main()
