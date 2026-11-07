#!/usr/bin/env python3
"""Tag-aware duplicate finder. HARD RULE: a file with any Finder tag is never
eligible for deletion, full stop — no exceptions, no override flag.

Scoped per model folder — a byte-identical file in two different models'
folders is never treated as a duplicate (could be intentional: a collab,
a repost, etc). Only files within the same model folder are compared.

Catches two kinds of duplicates within a model folder:
  1. Exact byte-identical files (hash match), regardless of filename —
     confirmed duplicates, eligible for auto-delete (subject to the tag rule).
  2. "Copy pattern" siblings — e.g. "clip.mp4" next to "clip (1).mp4" — but
     ONLY when the unsuffixed original actually exists on disk, and even then
     these are never auto-deleted, only flagged for manual review, since a
     shared filename pattern is not proof of duplicate content. (Some source
     sites use "(N)" as their own sequential content ID for entirely different
     files with no unsuffixed original ever present — e.g. "Scene (2).mp4"
     through "Scene (12).mp4" — those are correctly never grouped at all.)

Files are only hashed if another file in the same model folder shares its
exact size — a cheap stat()-based pre-filter that avoids hashing every byte
of every video in a large library.

Default is DRY RUN — only reports what it would do. Pass --delete to actually
remove files, and even then, only ones that pass the tag check.

Usage:
  python3 safe_dedup.py <path>                 # dry run, report only
  python3 safe_dedup.py <path> --delete         # actually delete safe duplicates
"""
import os
import re
import sys
import hashlib
import subprocess
import plistlib
from collections import defaultdict
from pacman_bar import PacmanBar as tqdm

COPY_PATTERNS = [
    re.compile(r'^(?P<base>.+?) \(\d+\)(?P<ext>\.[^.]+)$'),      # name (1).ext
    re.compile(r'^(?P<base>.+?) copy(?: \d+)?(?P<ext>\.[^.]+)$', re.IGNORECASE),  # name copy.ext / name copy 2.ext
    re.compile(r'^(?P<base>.+?)_copy(?:_\d+)?(?P<ext>\.[^.]+)$', re.IGNORECASE),  # name_copy.ext
    re.compile(r'^(?P<base>.+?)-copy(?:-\d+)?(?P<ext>\.[^.]+)$', re.IGNORECASE),  # name-copy.ext
]

def get_tags(filepath):
    result = subprocess.run(
        ['xattr', '-px', 'com.apple.metadata:_kMDItemUserTags', filepath],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        hex_data = result.stdout.strip().replace(' ', '').replace('\n', '')
        data = plistlib.loads(bytes.fromhex(hex_data))
        return list(data)
    except Exception:
        return []

def hash_file(filepath, chunk_size=1024 * 1024):
    h = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None

def base_name_for_copy_pattern(filename):
    for pat in COPY_PATTERNS:
        m = pat.match(filename)
        if m:
            return m.group('base') + m.group('ext')
    return None

def format_size(n):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"

def find_duplicate_groups(all_files):
    """Find duplicate sets within one model folder. Returns (confirmed, suspected):

    confirmed — exact byte-for-byte hash matches (pre-filtered by file size to
      avoid hashing everything). Safe to act on automatically, subject to the tag rule.

    suspected — same base filename as an OS-style copy-rename ("file.ext" next
      to "file (1).ext"), but NOT byte-identical (e.g. a re-encode). Only
      counted when the unsuffixed original literally exists on disk — a source
      site's own sequential numbering with no unsuffixed original present
      (e.g. "Scene (2).mp4" ... "Scene (12).mp4", all different scenes) is
      correctly never grouped this way. Always routed to manual review, never
      auto-deleted — a shared name is not proof of duplicate content.
    """
    # size-based pre-filter: only hash files that share a size with another file
    size_groups = defaultdict(list)
    for path in all_files:
        try:
            size_groups[os.path.getsize(path)].append(path)
        except OSError:
            continue
    hash_candidates = [p for group in size_groups.values() if len(group) > 1 for p in group]

    hash_groups = defaultdict(list)
    for path in hash_candidates:
        h = hash_file(path)
        if h:
            hash_groups[h].append(path)

    confirmed = []
    seen_sets = set()
    for group in hash_groups.values():
        group = sorted(set(group))
        if len(group) < 2:
            continue
        key = tuple(group)
        if key in seen_sets:
            continue
        seen_sets.add(key)
        confirmed.append(group)

    # copy-pattern groups — only when the unsuffixed "original" literally exists
    pattern_groups = defaultdict(list)
    for path in all_files:
        d, fname = os.path.split(path)
        base = base_name_for_copy_pattern(fname)
        if base:
            original = os.path.join(d, base)
            if original != path and os.path.exists(original):
                pattern_groups[(d, base)].append(path)
                pattern_groups[(d, base)].append(original)

    suspected = []
    for group in pattern_groups.values():
        group = sorted(set(group))
        if len(group) < 2:
            continue
        key = tuple(group)
        if key in seen_sets:
            continue  # already confirmed via hash — no need to also flag as suspected
        seen_sets.add(key)
        suspected.append(group)

    return confirmed, suspected

def process_model(model_path):
    all_files = []
    for root, dirs, files in os.walk(model_path):
        for fname in files:
            if fname.startswith('.') or fname == 'info.txt':
                continue
            all_files.append(os.path.join(root, fname))

    confirmed, suspected = find_duplicate_groups(all_files)

    to_delete = []
    manual_review = []
    space_reclaimable = 0

    for group in confirmed:
        tagged = [(p, get_tags(p)) for p in group]
        tagged_files = [p for p, t in tagged if t]
        untagged_files = [p for p, t in tagged if not t]

        if len(tagged_files) >= 2:
            manual_review.append((group, tagged_files, "multiple tagged copies — pick one"))
            continue
        if len(tagged_files) == 1:
            for p in untagged_files:
                size = os.path.getsize(p) if os.path.exists(p) else 0
                to_delete.append((p, size, f"keeping tagged copy: {tagged_files[0]}"))
                space_reclaimable += size
            continue
        # none tagged — keep the "cleanest" name (no copy-pattern suffix), else first
        keep = None
        for p in group:
            if base_name_for_copy_pattern(os.path.basename(p)) is None:
                keep = p
                break
        if keep is None:
            keep = sorted(group)[0]
        for p in group:
            if p != keep:
                size = os.path.getsize(p) if os.path.exists(p) else 0
                to_delete.append((p, size, f"keeping: {keep}"))
                space_reclaimable += size

    for group in suspected:
        tagged_files = [p for p in group if get_tags(p)]
        manual_review.append((group, tagged_files,
                               "same base filename but NOT byte-identical — verify before touching"))

    return confirmed + suspected, to_delete, manual_review, space_reclaimable

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 safe_dedup.py <path> [--delete]")
        sys.exit(1)

    target = sys.argv[1].rstrip('/')
    do_delete = '--delete' in sys.argv

    if not os.path.isdir(target):
        print(f"Not a directory: {target}")
        sys.exit(1)

    model_dirs = sorted(
        [d for d in os.scandir(target) if d.is_dir() and not d.name.startswith('.')],
        key=lambda d: d.name
    )
    print(f"Found {len(model_dirs)} model folders. Scanning for duplicates within each...\n")

    total_groups = 0
    all_to_delete = []
    all_manual_review = []
    space_reclaimable = 0

    for model in tqdm(model_dirs, desc="Scanning models", unit=" models"):
        groups, to_delete, manual_review, space = process_model(model.path)
        if to_delete or manual_review:
            tqdm.write(f"{model.name}: {len(to_delete)} safe to delete, "
                       f"{len(manual_review)} group(s) need manual review")
        total_groups += len(groups)
        all_to_delete.extend(to_delete)
        all_manual_review.extend(manual_review)
        space_reclaimable += space

    print(f"\nDuplicate groups found: {total_groups}")
    print(f"Safe to delete: {len(all_to_delete)} files ({format_size(space_reclaimable)} reclaimable)")
    print(f"Flagged for manual review (not touched): {len(all_manual_review)} groups")

    report_path = os.path.join(os.path.expanduser('~'), 'scripts', 'organize', 'dedup_report.md')
    with open(report_path, 'w') as f:
        f.write(f"# Dedup Report — {target}\n\n")
        f.write(f"Duplicate groups: {total_groups}  \n")
        f.write(f"Safe to delete: {len(all_to_delete)} files ({format_size(space_reclaimable)})  \n")
        f.write(f"Manual review needed: {len(all_manual_review)} groups\n\n")

        f.write("## Safe to delete\n\n")
        for p, size, reason in all_to_delete:
            f.write(f"- `{p}` ({format_size(size)}) — {reason}\n")

        f.write("\n## Manual review (not touched)\n\n")
        for group, tagged_files, reason in all_manual_review:
            f.write(f"- Group ({reason}): {group}\n")
            if tagged_files:
                f.write(f"  Tagged copies: {tagged_files}\n")

    print(f"Report written to {report_path}")

    if do_delete:
        print(f"\nDeleting {len(all_to_delete)} files...")
        deleted = 0
        for p, size, reason in all_to_delete:
            try:
                os.remove(p)
                deleted += 1
            except OSError as e:
                print(f"FAILED to delete {p}: {e}")
        print(f"Deleted {deleted}/{len(all_to_delete)} files, reclaimed ~{format_size(space_reclaimable)}")
    else:
        print("\nDry run only — nothing deleted. Review the report, then re-run with --delete.")

if __name__ == '__main__':
    main()
