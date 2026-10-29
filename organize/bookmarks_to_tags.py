#!/usr/bin/env python3
"""Turn Chrome bookmark folders into Linkding tags.

Reads a Chrome bookmarks export, adds TAGS="..." to each link based on the
folders it sits in, and writes a new file Linkding can import.

Usage: bookmarks_to_tags.py INPUT OUTPUT [--sample]
  --sample  keep only the first 2 links from each folder (for a test import)
"""
import html
import re
import sys
from collections import Counter

SKIP = {"bookmarks-bar", "other-bookmarks"}
FOLDER = re.compile(r"<H3[^>]*>(.*?)</H3>")
# Tab-suspender links: chrome-extension://<id>/lazyloading.html#<real url>
WRAPPED = re.compile(r'HREF="chrome-extension://[^"#]*#([^"]*)"')


def to_tag(name):
    # "mega to do list" -> "mega-to-do-list", "Misc" -> "misc"
    return re.sub(r"\s+", "-", html.unescape(name).strip().lower())


def main():
    sample = "--sample" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--sample"]
    if len(args) != 2:
        sys.exit(__doc__)
    src, dest = args

    stack = []       # one entry per open <DL>: folder tag, or None
    pending = None   # folder just seen, waiting for its <DL>
    per_folder = Counter()
    per_tag = Counter()
    written = 0
    unwrapped = 0
    out = []

    with open(src, encoding="utf-8") as f:
        for line in f:
            folder = FOLDER.search(line)
            if folder:
                name = to_tag(folder.group(1))
                pending = None if name in SKIP else name
            elif "</DL>" in line:
                stack.pop()
            elif "<DL>" in line:
                stack.append(pending)
                pending = None
            elif "<A HREF" in line:
                line, n = WRAPPED.subn(r'HREF="\1"', line)
                unwrapped += n
                tags = [t for t in stack if t]
                per_folder[tuple(tags)] += 1
                if sample and per_folder[tuple(tags)] > 2:
                    continue
                if tags:
                    line = line.replace("<A ", f'<A TAGS="{",".join(tags)}" ', 1)
                per_tag.update(tags or ["(untagged)"])
                written += 1
            out.append(line)

    with open(dest, "w", encoding="utf-8") as f:
        f.writelines(out)

    print(f"wrote {written} links to {dest}")
    print(f"unwrapped {unwrapped} suspended-tab links")
    for tag, n in per_tag.most_common():
        print(f"  {n:5}  {tag}")


if __name__ == "__main__":
    main()
