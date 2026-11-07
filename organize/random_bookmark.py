#!/usr/bin/env python3
"""Pick a random bookmark from a given top-level category folder and open it in Chrome.
Usage: python3 random_bookmark.py <category>   (e.g. hentai, black, asian, latina, comp, bi)
Includes subfolders (e.g. hentai/joi is nested under hentai).
"""
import json
import random
import subprocess
import sys

BOOKMARKS_PATH = "/Users/jackwillis/Library/Application Support/Google/Chrome/Default/Bookmarks"

if len(sys.argv) != 2:
    print("Usage: python3 random_bookmark.py <category>")
    sys.exit(1)

category = sys.argv[1].strip().lower()

with open(BOOKMARKS_PATH) as f:
    data = json.load(f)

def collect_urls(node):
    urls = []
    if node.get('type') == 'folder':
        for c in node.get('children', []):
            urls.extend(collect_urls(c))
    else:
        urls.append((node.get('name', ''), node.get('url', '')))
    return urls

target = None
for c in data['roots']['other']['children']:
    if c.get('name', '').strip().lower() == category:
        target = c
        break

if target is None:
    available = [c['name'] for c in data['roots']['other']['children']]
    print(f"No category '{category}'. Available: {', '.join(available)}")
    sys.exit(1)

urls = collect_urls(target)
if not urls:
    print(f"'{category}' has no bookmarks.")
    sys.exit(1)

name, url = random.choice(urls)
print(f"{name}\n{url}")
subprocess.run(['open', '-a', 'Google Chrome', url])
