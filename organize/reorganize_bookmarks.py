#!/usr/bin/env python3
"""Flatten the dated bookmark structure into category folders, deduping exact URL dupes."""
import json
import time
import uuid

BOOKMARKS_PATH = "/Users/jackwillis/Library/Application Support/Google/Chrome/Default/Bookmarks"

CATEGORY_MAP = {
    'black': 'black', 'white': 'white', 'asian': 'asian', 'azn': 'asian',
    'hentai': 'hentai', 'latina': 'latina', 'comp': 'comp', 'comps': 'comp',
    'bi': 'bi', 'cock': 'cock', 'ebony': 'ebony', 'cum': 'cum', 'joi': 'joi',
    'mega to do list': 'mega to do list',
}
CATEGORY_ORDER = ['black', 'white', 'asian', 'hentai', 'latina', 'comp',
                   'bi', 'cock', 'ebony', 'cum', 'joi', 'mega to do list', 'Misc']

with open(BOOKMARKS_PATH) as f:
    data = json.load(f)

next_id = [max(int(n) for n in __import__('re').findall(r'"id":\s*"(\d+)"', json.dumps(data))) + 1]

def new_id():
    i = next_id[0]
    next_id[0] += 1
    return str(i)

def now_ts():
    # chrome timestamp: microseconds since 1601-01-01
    epoch_offset = 11644473600
    return str(int((time.time() + epoch_offset) * 1_000_000))

def make_folder(name, children):
    return {
        "children": children,
        "date_added": now_ts(),
        "date_modified": now_ts(),
        "guid": str(uuid.uuid4()),
        "id": new_id(),
        "name": name,
        "type": "folder",
    }

# --- collect leaf bookmarks from "other" tree, classified by category ---
other_root = data['roots']['other']
buckets = {c: [] for c in CATEGORY_ORDER}
seen_urls = set()
total_before = 0
dupes_dropped = 0

def classify(path):
    # The leaf folder's own name is what matters; some are literally named
    # "hentai/joi" or "bi/comp" (a slash IN the name), not real nested folders.
    last = path[-1].strip().lower() if path else ''
    if '/' in last:
        top_part, sub_part = last.split('/', 1)
        top_part = top_part.strip()
        sub_part = sub_part.strip()
        if top_part in CATEGORY_MAP:
            sub_part = CATEGORY_MAP.get(sub_part, sub_part)
            return (CATEGORY_MAP[top_part], sub_part)
    if last in CATEGORY_MAP:
        return (CATEGORY_MAP[last], None)
    return ('Misc', None)

def walk(node, path):
    global total_before, dupes_dropped
    if node.get('type') != 'folder':
        return
    children = node.get('children', [])
    for c in children:
        if c.get('type') == 'folder':
            walk(c, path + [c['name']])
        else:
            total_before += 1
            url = c.get('url', '')
            if url in seen_urls:
                dupes_dropped += 1
                continue
            seen_urls.add(url)
            top, sub = classify(path)
            buckets.setdefault(top, [])
            if sub:
                # find or create sub-bucket list under a special key
                buckets[top].append(('__SUB__', sub, c))
            else:
                buckets[top].append(c)

walk(other_root, [])

new_other_children = []
for cat in CATEGORY_ORDER:
    items = buckets.get(cat, [])
    if not items:
        continue
    direct = [i for i in items if not (isinstance(i, tuple))]
    subgrouped = {}
    for i in items:
        if isinstance(i, tuple):
            _, sub, node = i
            subgrouped.setdefault(sub, []).append(node)
    folder_children = list(direct)
    for sub_name, sub_items in subgrouped.items():
        folder_children.append(make_folder(sub_name, sub_items))
    new_other_children.append(make_folder(cat, folder_children))

other_root['children'] = new_other_children
other_root['date_modified'] = now_ts()

# --- dedupe bookmark_bar (flat, preserve order) ---
bar = data['roots']['bookmark_bar']
bar_seen = set()
new_bar_children = []
bar_dupes = 0
for c in bar.get('children', []):
    if c.get('type') == 'folder':
        new_bar_children.append(c)
        continue
    url = c.get('url', '')
    if url in bar_seen:
        bar_dupes += 1
        continue
    bar_seen.add(url)
    new_bar_children.append(c)
bar['children'] = new_bar_children
bar['date_modified'] = now_ts()

with open(BOOKMARKS_PATH, 'w') as f:
    json.dump(data, f)

print(f"Total bookmarks scanned (other tree): {total_before}")
print(f"Duplicates dropped (other tree): {dupes_dropped}")
print(f"Bookmark bar duplicates dropped: {bar_dupes}")
print(f"Categories written: {[c['name'] for c in new_other_children]}")
for c in new_other_children:
    print(f"  {c['name']}: {len(c['children'])} items")
