#!/usr/bin/env python3
"""Remove confirmed-dead bookmark URLs (from dead_link_report.md) from the live Bookmarks file."""
import json
import re
import time

BOOKMARKS_PATH = "/Users/jackwillis/Library/Application Support/Google/Chrome/Default/Bookmarks"
REPORT_PATH = "/Users/jackwillis/scripts/organize/dead_link_report.md"

with open(REPORT_PATH) as f:
    report = f.read()

dead_section = report.split('## Dead (confirmed)')[1].split('## Blocked')[0]
dead_urls = set(re.findall(r'^\s+(https?://\S+)$', dead_section, re.MULTILINE))
print(f"Dead URLs parsed from report: {len(dead_urls)}")

with open(BOOKMARKS_PATH) as f:
    data = json.load(f)

removed = 0

def now_ts():
    epoch_offset = 11644473600
    return str(int((time.time() + epoch_offset) * 1_000_000))

def prune(node):
    global removed
    if node.get('type') != 'folder':
        return
    kept = []
    for c in node.get('children', []):
        if c.get('type') == 'folder':
            prune(c)
            kept.append(c)
        else:
            if c.get('url', '') in dead_urls:
                removed += 1
            else:
                kept.append(c)
    node['children'] = kept
    node['date_modified'] = now_ts()

for root_name in ['bookmark_bar', 'other']:
    prune(data['roots'][root_name])

with open(BOOKMARKS_PATH, 'w') as f:
    json.dump(data, f)

print(f"Removed {removed} dead bookmarks")
