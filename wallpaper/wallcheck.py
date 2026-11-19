#!/usr/bin/env python3
"""wallcheck — build a crop-comparison page from your Aether (Wallhaven) favorites.

Reads ~/.config/aether/favorites.json, downloads any full-size originals it
doesn't have yet, makes small previews, and writes index.html showing each
wallpaper with phone (9:19.5), laptop (3:2) and monitor (16:9) crops drawn on.
Drag the phone box on a card to get a matching `magick -crop` command.

Output folder (default ~/Pictures/wallpaper-check):
  originals/   full-size downloads, named <id>.<ext>
  img/         ~1100px previews used by the page
  phone/       where the crop commands write phone versions
  notes.json   your per-wallpaper notes, tags and "is it Marine" flag (edit freely)
  index.html   the page

Usage:
  wallcheck.py              build/refresh the page
  wallcheck.py --open       ...and open it in the browser
  wallcheck.py --out DIR    use a different output folder

Needs: python3 (stdlib only), ImageMagick (`magick`).
"""

import argparse
import json
import shutil
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

FAVORITES = Path.home() / ".config/aether/favorites.json"
DEFAULT_OUT = Path.home() / "Pictures/wallpaper-check"
PREVIEW_MAX = 1100
USER_AGENT = "wallcheck/1.0"


def tilde(p: Path) -> str:
    """Show paths as ~/... in the crop commands so they stay short."""
    s = str(p)
    home = str(Path.home())
    return "~" + s[len(home):] if s.startswith(home) else s


def download(fav: dict, originals: Path) -> tuple[str, str | None]:
    url = fav["path"]
    dest = originals / f"{fav['id']}{Path(url).suffix}"
    if dest.exists():
        return fav["id"], None
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        tmp.rename(dest)
        return fav["id"], "downloaded"
    except Exception as e:  # keep going; one bad link shouldn't stop the page
        tmp.unlink(missing_ok=True)
        return fav["id"], f"FAILED: {e}"


def image_size(path: Path) -> tuple[int, int] | None:
    try:
        out = subprocess.run(
            ["magick", "identify", "-format", "%w %h\n", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout.split("\n")[0]
        w, h = out.split()
        return int(w), int(h)
    except Exception:
        return None


def make_preview(src: Path, dest: Path) -> None:
    if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
        return
    subprocess.run(
        ["magick", str(src) + "[0]", "-auto-orient",
         "-resize", f"{PREVIEW_MAX}x{PREVIEW_MAX}>", "-quality", "82", str(dest)],
        check=True,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a wallpaper crop-comparison page from Aether favorites.")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"output folder (default {tilde(DEFAULT_OUT)})")
    ap.add_argument("--open", action="store_true", help="open the page when done")
    args = ap.parse_args()

    if not shutil.which("magick"):
        print("ImageMagick not found. Install it with: omarchy pkg add imagemagick", file=sys.stderr)
        return 1
    if not FAVORITES.exists():
        print(f"No Aether favorites at {tilde(FAVORITES)}. Favorite something in Aether first.", file=sys.stderr)
        return 1

    favs = json.loads(FAVORITES.read_text())
    out = args.out.expanduser()
    originals, previews, phone = out / "originals", out / "img", out / "phone"
    for d in (originals, previews, phone):
        d.mkdir(parents=True, exist_ok=True)

    # 1. Download anything new (4 at a time)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for fid, status in pool.map(lambda f: download(f, originals), favs):
            if status:
                print(f"  {fid}: {status}")

    # 2. Notes: keep yours, add a blank entry for new favorites
    notes_path = out / "notes.json"
    notes = json.loads(notes_path.read_text()) if notes_path.exists() else {}
    new_ids = [f["id"] for f in favs if f["id"] not in notes]
    for fid in new_ids:
        notes[fid] = {"tag": "", "marine": None, "note": ""}
    notes_path.write_text(json.dumps(notes, indent=2, ensure_ascii=False) + "\n")

    # 3. Previews + real dimensions
    items = []
    for fav in favs:
        fid = fav["id"]
        src = next(originals.glob(f"{fid}.*"), None)
        if src is None or src.suffix == ".part":
            print(f"  {fid}: no original, skipped")
            continue
        try:
            make_preview(src, previews / f"{fid}.webp")
        except subprocess.CalledProcessError:
            print(f"  {fid}: preview failed, skipped")
            continue
        size = image_size(src)
        if size is None:
            w, h = map(int, fav.get("resolution", "0x0").split("x"))
        else:
            w, h = size
        n = notes.get(fid, {})
        items.append({
            "id": fid, "w": w, "h": h,
            "src": tilde(src),
            "dest": tilde(phone / f"{fid}-phone.png"),
            "tag": n.get("tag", ""), "marine": n.get("marine"), "note": n.get("note", ""),
            "url": f"https://wallhaven.cc/w/{fid}",
        })

    # Tagged first, then Marine, then unreviewed, then everything else; otherwise keep Aether's order
    rank = lambda i: (0 if i["tag"] else 1 if i["marine"] else 2 if i["marine"] is None else 3)
    items.sort(key=rank)

    html = TEMPLATE.replace("/*__DATA__*/[]", json.dumps(items, ensure_ascii=False).replace("</", "<\\/"))
    (out / "index.html").write_text(html)

    print(f"{len(items)} wallpapers → {tilde(out / 'index.html')}")
    if new_ids:
        print(f"New since last run: {', '.join(new_ids)} (add notes in {tilde(notes_path)})")
    if args.open:
        subprocess.Popen(["xdg-open", str(out / "index.html")],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Wallpaper Crop Check</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #12101a; --panel: #1c1926; --line: #2e2a3d; --fg: #ece8f2; --muted: #9a93ab;
  --red: #e2443d; --gold: #e6b84c; --cyan: #5fc8d8; --ok: #6fcf8a; --warn: #e6b84c;
  --display: "Space Grotesk", system-ui, sans-serif;
  --body: "Inter", system-ui, sans-serif;
  --mono: "JetBrains Mono", ui-monospace, monospace;
  color-scheme: dark;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); font: 14px/1.5 var(--body); }
.wrap { max-width: 1400px; margin: 0 auto; padding: 28px 16px 60px; }
h1 { font: 700 28px/1.1 var(--display); margin: 0 0 6px; }
.lede { color: var(--muted); margin: 0 0 20px; max-width: 70ch; }
.controls { display: flex; flex-wrap: wrap; gap: 10px 18px; align-items: center; padding: 12px 14px; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; margin-bottom: 22px; position: sticky; top: 0; z-index: 5; }
.controls label { display: inline-flex; gap: 7px; align-items: center; cursor: pointer; user-select: none; }
.sw { width: 12px; height: 12px; border-radius: 2px; border: 2px solid; }
.sw.phone { border-color: var(--red); } .sw.laptop { border-color: var(--gold); } .sw.mon { border-color: var(--cyan); }
.controls .sep { width: 1px; align-self: stretch; background: var(--line); }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 420px), 1fr)); gap: 22px; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; display: flex; flex-direction: column; }
.card.hidden { display: none; }
.stage { position: relative; background: #000; line-height: 0; touch-action: none; overflow: hidden; }
.stage img { width: 100%; height: auto; display: block; }
.frame { position: absolute; top: 0; height: 100%; pointer-events: none; }
.frame.laptop { border: 2px dashed var(--gold); }
.frame.mon { border: 2px dashed var(--cyan); }
.frame.phone { border: 2px solid var(--red); box-shadow: 0 0 0 9999px rgba(0,0,0,.55); pointer-events: auto; cursor: ew-resize; }
body.no-phone .frame.phone { display: none; } body.no-laptop .frame.laptop { display: none; } body.no-mon .frame.mon { display: none; }
body.no-shade .frame.phone { box-shadow: none; }
.meta { padding: 12px 14px 14px; display: flex; flex-direction: column; gap: 8px; }
.row { display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: baseline; }
.id { font: 700 17px var(--display); letter-spacing: .02em; color: var(--fg); text-decoration: none; }
.id:hover { color: var(--red); }
.res { font: 12px var(--mono); color: var(--muted); font-variant-numeric: tabular-nums; }
.pill { font-size: 11px; font-weight: 500; letter-spacing: .04em; text-transform: uppercase; padding: 2px 8px; border-radius: 99px; border: 1px solid var(--line); color: var(--muted); }
.pill.tag { border-color: var(--gold); color: var(--gold); }
.pill.ok { border-color: var(--ok); color: var(--ok); }
.pill.warn { border-color: var(--warn); color: var(--warn); }
.note { color: var(--muted); margin: 0; }
.cmd { display: flex; gap: 8px; align-items: stretch; }
.cmd code { flex: 1; min-width: 0; font: 11.5px/1.45 var(--mono); background: var(--bg); border: 1px solid var(--line); border-radius: 6px; padding: 7px 9px; overflow-x: auto; white-space: nowrap; }
button { font: 500 12px var(--body); background: transparent; color: var(--fg); border: 1px solid var(--line); border-radius: 6px; padding: 0 10px; cursor: pointer; }
button:hover { border-color: var(--red); }
button:focus-visible, input:focus-visible, .frame.phone:focus-visible { outline: 2px solid var(--gold); outline-offset: 2px; }
.hint { font-size: 12px; color: var(--muted); }
</style>
</head>
<body>
<div class="wrap">
  <h1>Wallpaper Crop Check</h1>
  <p class="lede">Your Aether favorites, with each screen's crop drawn over them. Drag the red phone box sideways to choose your phone framing; the crop command below each card updates to match. Laptop and monitor crops are centered, which is how Omarchy fills the screen.</p>
  <div class="controls">
    <label><input type="checkbox" id="t-phone" checked><span class="sw phone"></span>Phone 9:19.5</label>
    <label><input type="checkbox" id="t-laptop" checked><span class="sw laptop"></span>Laptop 3:2</label>
    <label><input type="checkbox" id="t-mon" checked><span class="sw mon"></span>Monitors 16:9</label>
    <span class="sep"></span>
    <label><input type="checkbox" id="t-shade" checked>Darken outside phone</label>
    <label><input type="checkbox" id="t-marine">Marine only</label>
  </div>
  <div class="grid" id="grid"></div>
</div>
<script>
const W = /*__DATA__*/[];
const PHONE_W = 1179, PHONE_RATIO = 9 / 19.5;
const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
function cover(w, h, r) {
  if (w / h > r) { const cw = h * r; return { x: (w - cw) / 2 / w, y: 0, fw: cw / w, fh: 1 }; }
  const ch = w / r; return { x: 0, y: (h - ch) / 2 / h, fw: 1, fh: ch / h };
}
const pct = v => (v * 100).toFixed(3) + "%";
const grid = document.getElementById("grid");
W.forEach(item => {
  const pw = Math.min(item.w, Math.round(item.h * PHONE_RATIO));
  const lap = cover(item.w, item.h, 3 / 2), mon = cover(item.w, item.h, 16 / 9);
  const who = item.marine === true ? "" : item.marine === false ? `<span class="pill">Not Marine</span>` : `<span class="pill warn">Unreviewed</span>`;
  const card = document.createElement("article");
  card.className = "card"; card.dataset.marine = String(item.marine);
  card.innerHTML = `
    <div class="stage">
      <img src="img/${esc(item.id)}.webp" alt="Wallpaper ${esc(item.id)}" loading="lazy" width="${item.w}" height="${item.h}">
      <div class="frame mon" style="left:${pct(mon.x)};top:${pct(mon.y)};width:${pct(mon.fw)};height:${pct(mon.fh)}"></div>
      <div class="frame laptop" style="left:${pct(lap.x)};top:${pct(lap.y)};width:${pct(lap.fw)};height:${pct(lap.fh)}"></div>
      <div class="frame phone" tabindex="0" aria-label="Phone crop, use arrow keys to move"></div>
    </div>
    <div class="meta">
      <div class="row">
        <a class="id" href="${esc(item.url)}" target="_blank" rel="noopener">${esc(item.id)}</a>
        <span class="res">${item.w}×${item.h} · ${(item.w / item.h).toFixed(2)}:1</span>
        ${item.tag ? `<span class="pill tag">${esc(item.tag)}</span>` : ""}
        ${who}
      </div>
      <div class="row">
        <span class="pill ${pw >= PHONE_W ? "ok" : "warn"}">Phone ${pw}px wide · ${pw >= PHONE_W ? "sharp" : "slightly soft"}</span>
        <span class="pill ${mon.fh < 0.85 ? "warn" : "ok"}">Monitors keep ${Math.round(mon.fw * mon.fh * 100)}%</span>
        <span class="pill ok">Laptop keeps ${Math.round(lap.fw * lap.fh * 100)}%</span>
      </div>
      ${item.note ? `<p class="note">${esc(item.note)}</p>` : ""}
      <div class="cmd"><code></code><button type="button">Copy</button></div>
      <span class="hint">Drag the red box or focus it and use ← →.</span>
    </div>`;
  grid.appendChild(card);
  const stage = card.querySelector(".stage"), phone = card.querySelector(".frame.phone");
  const code = card.querySelector("code"), btn = card.querySelector("button");
  const fw = pw / item.w;
  let x = (1 - fw) / 2;
  function render() {
    phone.style.left = pct(x); phone.style.width = pct(fw);
    code.textContent = `magick ${item.src} -crop ${pw}x${item.h}+${Math.round(x * item.w)}+0 +repage ${item.dest}`;
  }
  const clamp = v => Math.min(Math.max(v, 0), 1 - fw);
  let drag = null;
  phone.addEventListener("pointerdown", e => { drag = { sx: e.clientX, x0: x, rw: stage.getBoundingClientRect().width }; phone.setPointerCapture(e.pointerId); });
  phone.addEventListener("pointermove", e => { if (!drag) return; x = clamp(drag.x0 + (e.clientX - drag.sx) / drag.rw); render(); });
  phone.addEventListener("pointerup", () => drag = null);
  phone.addEventListener("keydown", e => {
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") { e.preventDefault(); x = clamp(x + (e.key === "ArrowLeft" ? -0.02 : 0.02)); render(); }
  });
  btn.addEventListener("click", () => {
    navigator.clipboard.writeText(code.textContent).then(() => { btn.textContent = "Copied"; setTimeout(() => btn.textContent = "Copy", 1200); })
      .catch(() => { const r = document.createRange(); r.selectNodeContents(code); const s = getSelection(); s.removeAllRanges(); s.addRange(r); });
  });
  render();
});
[["t-phone", "no-phone"], ["t-laptop", "no-laptop"], ["t-mon", "no-mon"], ["t-shade", "no-shade"]].forEach(([id, cls]) => {
  document.getElementById(id).addEventListener("change", e => document.body.classList.toggle(cls, !e.target.checked));
});
document.getElementById("t-marine").addEventListener("change", e => {
  document.querySelectorAll(".card").forEach(c => c.classList.toggle("hidden", e.target.checked && c.dataset.marine !== "true"));
});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    sys.exit(main())
