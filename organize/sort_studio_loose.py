#!/usr/bin/env python3
"""
Match loose top-level files in a studio library against existing 'model index/'
and 'studio index/' subfolders, and suggest where each should move.

Heuristics (best-effort, meant to be reviewed before trusting):
  1. Strip known junk suffixes (Telegram repost tags like "_@JackCity on Telegram").
  2. If the name splits on " - ", check the part BEFORE it against known studio
     folder names first (studio titles conventionally lead with the studio name).
  3. Otherwise/also, check the whole (junk-stripped) name against known model
     folder names (loose files are often just "performer-name-123.ext").
  4. No match on either -> flagged as UNMATCHED for manual sorting.

Matching is substring-based on a normalized (lowercased, non-alnum-stripped) form
of both the filename and each known folder name, preferring the LONGEST matching
folder name to avoid short-name false positives (e.g. a studio named "bang"
matching inside an unrelated word).

Dry run only — this never moves anything. It just writes a report.

Usage:
  python3 sort_studio_loose.py <studio_path>
"""
import os
import re
import sys

JUNK_SUFFIX_RE = re.compile(r'_@\S.*$')

def normalize(s):
    # collapse non-alnum to single spaces (NOT stripped) so word boundaries survive —
    # e.g. "bang" must not match inside "gangbang" or "Bangladeshi"
    s = s.lower()
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return ' '.join(s.split())

def strip_junk(name):
    return JUNK_SUFFIX_RE.sub('', name)

def best_match(haystack_norm, candidates):
    """candidates: list of (folder_name, normalized_name). Returns the longest
    matching candidate whose normalized name appears as a whole word-sequence
    in haystack_norm, or None."""
    matches = [
        c for c in candidates
        if c[1] and re.search(r'\b' + re.escape(c[1]) + r'\b', haystack_norm)
    ]
    if not matches:
        return None
    return max(matches, key=lambda c: len(c[1]))

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 sort_studio_loose.py <studio_path>")
        sys.exit(1)

    base = sys.argv[1].rstrip('/')
    model_dir = os.path.join(base, 'model index')
    studio_dir = os.path.join(base, 'studio index')

    model_candidates = [(d.name, normalize(d.name)) for d in os.scandir(model_dir) if d.is_dir()]
    studio_candidates = [(d.name, normalize(d.name)) for d in os.scandir(studio_dir) if d.is_dir()]

    loose_files = [
        e.name for e in os.scandir(base)
        if e.is_file() and not e.name.startswith('.')
    ]
    loose_files.sort()

    to_model = []
    to_studio = []
    unmatched = []

    for fname in loose_files:
        base_name, ext = os.path.splitext(fname)
        cleaned = strip_junk(base_name)
        norm_full = normalize(cleaned)

        studio_part = cleaned.split(' - ', 1)[0] if ' - ' in cleaned else None
        norm_studio_part = normalize(studio_part) if studio_part else None

        studio_hit = None
        if norm_studio_part:
            studio_hit = best_match(norm_studio_part, studio_candidates)
        if not studio_hit:
            studio_hit = best_match(norm_full, studio_candidates)

        model_hit = best_match(norm_full, model_candidates)

        if studio_hit and model_hit:
            # both matched — report both, prefer studio (titles usually lead with studio)
            to_studio.append((fname, studio_hit[0], f"also matched model '{model_hit[0]}'"))
        elif studio_hit:
            to_studio.append((fname, studio_hit[0], ""))
        elif model_hit:
            to_model.append((fname, model_hit[0], ""))
        else:
            unmatched.append(fname)

    report_path = os.path.join(os.path.expanduser('~'), 'scripts', 'organize', 'studio_sort_report.md')
    with open(report_path, 'w') as f:
        f.write(f"# Studio Loose-File Sort Report — {base}\n\n")
        f.write(f"Loose files found: {len(loose_files)}\n\n")
        f.write(f"- Matched to model index: {len(to_model)}\n")
        f.write(f"- Matched to studio index: {len(to_studio)}\n")
        f.write(f"- Unmatched: {len(unmatched)}\n\n")

        f.write("## -> model index/\n\n")
        for fname, match, note in to_model:
            f.write(f"- `{fname}` -> `model index/{match}/`" + (f"  _{note}_" if note else "") + "\n")

        f.write("\n## -> studio index/\n\n")
        for fname, match, note in to_studio:
            f.write(f"- `{fname}` -> `studio index/{match}/`" + (f"  _{note}_" if note else "") + "\n")

        f.write("\n## Unmatched (needs manual decision)\n\n")
        for fname in unmatched:
            f.write(f"- `{fname}`\n")

    print(f"Loose files: {len(loose_files)}")
    print(f"Matched to model index: {len(to_model)}")
    print(f"Matched to studio index: {len(to_studio)}")
    print(f"Unmatched: {len(unmatched)}")
    print(f"\nReport written to {report_path}")

if __name__ == '__main__':
    main()
