#!/usr/bin/env python3
"""Check bookmark URLs for dead links. Read-only — writes a report, touches nothing else."""
import json
import concurrent.futures
import urllib.request
import urllib.error
import socket
from urllib.parse import urlparse

BOOKMARKS_PATH = "/Users/jackwillis/Library/Application Support/Google/Chrome/Default/Bookmarks"
REPORT_PATH = "/Users/jackwillis/scripts/organize/dead_link_report.md"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

DEAD_TEXT_MARKERS = [
    "video has been removed", "video not found", "video unavailable",
    "this video is no longer available", "page not found", "404 not found",
    "content unavailable", "this content is no longer available",
    "removed by the uploader", "video does not exist",
]

SPA_UNVERIFIABLE_DOMAINS = {"mega.nz"}

with open(BOOKMARKS_PATH) as f:
    data = json.load(f)

bookmarks = []  # (name, url, category_path)

def walk(node, path):
    if node.get('type') == 'folder':
        for c in node.get('children', []):
            walk(c, path + [node.get('name', '')])
    else:
        bookmarks.append((node.get('name', ''), node.get('url', ''), '/'.join(path)))

for root_name in ['bookmark_bar', 'other']:
    walk(data['roots'][root_name], [])

print(f"Total bookmarks to check: {len(bookmarks)}")

def check_one(item):
    name, url, path = item
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return (name, url, path, 'unverifiable', 'non-http scheme')
    if parsed.netloc in SPA_UNVERIFIABLE_DOMAINS:
        return (name, url, path, 'unverifiable', 'client-rendered SPA, status unreliable')

    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9',
    })
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            status = resp.status
            try:
                chunk = resp.read(65536).decode('utf-8', errors='ignore').lower()
            except Exception:
                chunk = ''
            if status in (404, 410):
                return (name, url, path, 'dead', f'http {status}')
            if any(m in chunk for m in DEAD_TEXT_MARKERS):
                return (name, url, path, 'dead', 'soft-404 text match')
            if status in (403, 429, 503):
                return (name, url, path, 'blocked', f'http {status}')
            if 200 <= status < 400:
                return (name, url, path, 'alive', f'http {status}')
            return (name, url, path, 'dead', f'http {status}')
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return (name, url, path, 'dead', f'http {e.code}')
        if e.code in (403, 429, 503):
            return (name, url, path, 'blocked', f'http {e.code}')
        return (name, url, path, 'dead', f'http {e.code}')
    except (urllib.error.URLError, socket.timeout, ConnectionError, TimeoutError) as e:
        return (name, url, path, 'dead', f'unreachable: {type(e).__name__}')
    except Exception as e:
        return (name, url, path, 'blocked', f'error: {type(e).__name__}')

results = {'alive': [], 'dead': [], 'blocked': [], 'unverifiable': []}

with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    futures = [ex.submit(check_one, b) for b in bookmarks]
    done = 0
    for fut in concurrent.futures.as_completed(futures):
        name, url, path, status, reason = fut.result()
        results[status].append((name, url, path, reason))
        done += 1
        if done % 200 == 0:
            print(f"...{done}/{len(bookmarks)} checked")

print(f"\nDone. alive={len(results['alive'])} dead={len(results['dead'])} "
      f"blocked={len(results['blocked'])} unverifiable={len(results['unverifiable'])}")

with open(REPORT_PATH, 'w') as f:
    f.write("# Dead Link Report\n\n")
    f.write(f"Total checked: {len(bookmarks)}\n\n")
    f.write(f"- Alive: {len(results['alive'])}\n")
    f.write(f"- **Dead (confirmed): {len(results['dead'])}**\n")
    f.write(f"- Blocked/inconclusive (site rejected the automated request — not necessarily dead): {len(results['blocked'])}\n")
    f.write(f"- Unverifiable (non-http links, JS-rendered sites): {len(results['unverifiable'])}\n\n")

    f.write("## Dead (confirmed)\n\n")
    for name, url, path, reason in sorted(results['dead'], key=lambda x: x[2]):
        f.write(f"- [{path}] {reason} — {name or url}\n  {url}\n")

    f.write("\n## Blocked / inconclusive\n\n")
    for name, url, path, reason in sorted(results['blocked'], key=lambda x: x[2]):
        f.write(f"- [{path}] {reason} — {name or url}\n  {url}\n")

    f.write("\n## Unverifiable\n\n")
    for name, url, path, reason in sorted(results['unverifiable'], key=lambda x: x[2]):
        f.write(f"- [{path}] {reason} — {name or url}\n  {url}\n")

print(f"Report written to {REPORT_PATH}")
