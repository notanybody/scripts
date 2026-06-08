#!/usr/bin/env python3
import os
import sys
import subprocess
from tqdm import tqdm

def get_tags(filepath):
    result = subprocess.run(
        ['xattr', '-px', 'com.apple.metadata:_kMDItemUserTags', filepath],
        capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else None

def set_tags(filepath, hex_data):
    result = subprocess.run(
        ['xattr', '-wx', 'com.apple.metadata:_kMDItemUserTags', hex_data, filepath],
        capture_output=True, text=True
    )
    return result.returncode == 0

def build_file_index(dest):
    index = {}
    dupes = {}
    with tqdm(desc="Indexing destination files", unit=" files") as pbar:
        for root, dirs, files in os.walk(dest, onerror=lambda e: None):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in files:
                if f.startswith('._') or f == '.DS_Store':
                    continue
                path = os.path.join(root, f)
                if f in index:
                    if f not in dupes:
                        dupes[f] = [index.pop(f)]
                    dupes[f].append(path)
                elif f in dupes:
                    dupes[f].append(path)
                else:
                    index[f] = path
                pbar.update(1)
    return index, dupes

def build_dir_index(dest):
    index = {}
    dupes = {}
    with tqdm(desc="Indexing destination folders", unit=" dirs") as pbar:
        for root, dirs, files in os.walk(dest, onerror=lambda e: None):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for d in dirs:
                path = os.path.join(root, d)
                if d in index:
                    if d not in dupes:
                        dupes[d] = [index.pop(d)]
                    dupes[d].append(path)
                elif d in dupes:
                    dupes[d].append(path)
                else:
                    index[d] = path
                pbar.update(1)
    return index, dupes

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 transfer_tags.py <source> <dest>")
        sys.exit(1)

    source = sys.argv[1].rstrip('/')
    dest = sys.argv[2].rstrip('/')

    # --- Files ---
    file_index, file_dupes = build_file_index(dest)
    print(f"Index built ({len(file_index)} unique, {len(file_dupes)} ambiguous)\n")

    tagged = missing = failed = size_matched = 0

    with tqdm(desc="Tagging files", unit=" files") as pbar:
        for root, dirs, files in os.walk(source, onerror=lambda e: None):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in files:
                if f.startswith('._') or f == '.DS_Store':
                    continue
                src_path = os.path.join(root, f)
                tags = get_tags(src_path)
                if not tags:
                    continue

                if f in file_index:
                    if set_tags(file_index[f], tags):
                        tagged += 1
                    else:
                        tqdm.write(f"FAILED: {f}")
                        failed += 1
                elif f in file_dupes:
                    for p in file_dupes[f]:
                        if set_tags(p, tags):
                            size_matched += 1
                        else:
                            tqdm.write(f"FAILED: {f}")
                            failed += 1
                else:
                    tqdm.write(f"MISSING: {f}")
                    missing += 1
                pbar.update(1)

    print(f"\n--- File Results ---")
    print(f"Tagged: {tagged} | All-copies: {size_matched} | Missing: {missing} | Failed: {failed}")

    # --- Folders ---
    dir_index, dir_dupes = build_dir_index(dest)
    print(f"Index built ({len(dir_index)} unique, {len(dir_dupes)} ambiguous)\n")

    dir_tagged = dir_missing = dir_failed = dir_still_ambiguous = 0

    with tqdm(desc="Tagging folders", unit=" dirs") as pbar:
        for root, dirs, files in os.walk(source, onerror=lambda e: None):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for d in dirs:
                src_path = os.path.join(root, d)
                tags = get_tags(src_path)
                if not tags:
                    continue

                if d in dir_index:
                    if set_tags(dir_index[d], tags):
                        dir_tagged += 1
                    else:
                        tqdm.write(f"FAILED (folder): {d}")
                        dir_failed += 1
                elif d in dir_dupes:
                    tqdm.write(f"AMBIGUOUS (folder): {d}")
                    dir_still_ambiguous += 1
                else:
                    tqdm.write(f"MISSING (folder): {d}")
                    dir_missing += 1
                pbar.update(1)

    print(f"\n--- Folder Results ---")
    print(f"Tagged: {dir_tagged} | Ambiguous: {dir_still_ambiguous} | Missing: {dir_missing} | Failed: {dir_failed}")

if __name__ == '__main__':
    main()
