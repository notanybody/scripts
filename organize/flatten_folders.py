#!/usr/bin/env python3
import os
import sys
import shutil
from tqdm import tqdm

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

def flatten_model(model_path, pbar):
    moved = renamed = failed = 0
    subdirs = [d for d in os.scandir(model_path) if d.is_dir()]

    for subdir in subdirs:
        for entry in os.scandir(subdir.path):
            if not entry.is_file():
                continue
            dest = safe_dest(model_path, entry.name)
            renamed_flag = dest != os.path.join(model_path, entry.name)
            try:
                shutil.move(entry.path, dest)
                if renamed_flag:
                    tqdm.write(f"  RENAMED: {entry.name} -> {os.path.basename(dest)}")
                    renamed += 1
                else:
                    moved += 1
            except Exception as e:
                tqdm.write(f"  FAILED: {entry.name} ({e})")
                failed += 1
            pbar.update(1)

        try:
            os.rmdir(subdir.path)
        except OSError:
            tqdm.write(f"  NOT EMPTY (skipped delete): {subdir.name}")

    return moved, renamed, failed

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 flatten_folders.py <library_path>")
        sys.exit(1)

    base = sys.argv[1].rstrip('/')
    total_moved = total_renamed = total_failed = 0

    model_dirs = [d for d in os.scandir(base) if d.is_dir()]
    print(f"Found {len(model_dirs)} model folders\n")

    with tqdm(desc="Flattening folders", unit=" files") as pbar:
        for model in tqdm(model_dirs, desc="Model folders", unit=" models", leave=False):
            moved, renamed, failed = flatten_model(model.path, pbar)
            total_moved += moved
            total_renamed += renamed
            total_failed += failed
            tqdm.write(f"Done: {model.name} — Moved: {moved} | Renamed: {renamed} | Failed: {failed}")

    print(f"\nAll done — Moved: {total_moved} | Renamed: {total_renamed} | Failed: {total_failed}")

if __name__ == '__main__':
    main()
