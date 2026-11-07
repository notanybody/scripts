#!/usr/bin/env python3
"""
ONE-OFF script for the 2026-10-24 hentai/series/ sort. Groups loose episode
files into per-series folders, matching the existing 'World of Light/'
convention (Title Case folder name containing all episodes). Series with
only one file found stay loose — nothing to group.

This embeds a hand-reviewed grouping of the specific 29 loose files in that
folder as of this run (merges two different filename styles for the same
series where applicable, e.g. "Learning the Hard Way 1.mp4" +
"learning-the-hard-way-2-720p-v2u.mp4"). Not a general-purpose parser.

Default is DRY RUN. Pass --apply to actually create folders and move files.

Usage:
  python3 sort_hentai_series.py <series_path> [--apply]
"""
import os
import sys
import shutil

GROUPS = {
    "Eroge": [
        "Eroge I.mp4",
        "Eroge II.mp4",
    ],
    "Eroge De Subete Wa Kaiketsu Dekiru": [
        "eroge-de-subete-wa-kaiketsu-dekiru-1.mp4",
        "eroge-de-subete-wa-kaiketsu-dekiru-2.mp4",
    ],
    "Imaizumin Chi Wa Douyara Gal No Tamariba Ni Natteru Rashii": [
        "imaizumin-chi-wa-douyara-gal-no-tamariba-ni-natteru-rashii-1-720p-v1x.mp4",
        "imaizumin-chi-wa-douyara-gal-no-tamariba-ni-natteru-rashii-2-720p-v1x.mp4",
        "imaizumin-chi-wa-douyara-gal-no-tamariba-ni-natteru-rashii-3-720p-h1x.mp4",
        "imaizumin-chi-wa-douyara-gal-no-tamariba-ni-natteru-rashii-4-720p-h1x.mp4",
    ],
    "Imouto Bitch Ni Shiboraretai": [
        "imouto-bitch-ni-shiboraretai-1-720p-v1x.mp4",
        "imouto-bitch-ni-shiboraretai-2-720p-v1x.mp4",
    ],
    "Isekai Harem Monogatari": [
        "isekai-harem-monogatari-1-720p-v1x.mp4",
        "isekai-harem-monogatari-2-720p-v1x.mp4",
    ],
    "Joshi Luck": [
        "joshi-luck-1-720p-v1x.mp4",
        "joshi-luck-2-720p-v1x.mp4",
        "joshi-luck-3-720p-v2x.mp4",
        "joshi-luck-4-720p-v2x.mp4",
        "joshi-luck-5-720p-h1x.mp4",
        "joshi-luck-6-720p-h1x.mp4",
    ],
    "Learning the Hard Way": [
        "Learning the Hard Way 1.mp4",
        "learning-the-hard-way-2-720p-v2u.mp4",
    ],
    "Sensual Adventure": [
        "sensual adventure 3.mp4",
        "sensual adventure 4.mp4",
    ],
    "Uchi No Otouto Maji De Dekain Dakedo Mi Ni Konai": [
        "uchi-no-otouto-maji-de-dekain-dakedo-mi-ni-konai-1-720p-v1x.mp4",
        "uchi-no-otouto-maji-de-dekain-dakedo-mi-ni-konai-2-720p-v1x.mp4",
    ],
}

# left loose (only 1 file found, nothing to group):
#   class-de-otoko-wa-boku-hitori-1-720p-v1x.mp4
#   garden-takamine-ke-no-nirinka-1-720p-v1x.mp4
#   imouto-wa-gal-kawaii-1-720p-v1x.mp4
#   kono-koi-ni-kizuite-1-720p-h1x.mp4
#   Green Eyes Ane Kyun! Yori 1.mp4

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 sort_hentai_series.py <series_path> [--apply]")
        sys.exit(1)

    base = sys.argv[1].rstrip('/')
    apply = '--apply' in sys.argv

    print("APPLY MODE — folders will be created and files moved\n" if apply
          else "DRY RUN — no changes will be made (pass --apply to move)\n")

    total_moved = total_missing = total_skipped_existing = 0

    for series, files in GROUPS.items():
        dest_dir = os.path.join(base, series)
        dest_exists = os.path.isdir(dest_dir)
        print(f"{series}/  ({len(files)} files)" + ("  [folder already exists!]" if dest_exists else ""))

        if apply:
            os.makedirs(dest_dir, exist_ok=True)

        for fname in files:
            src = os.path.join(base, fname)
            dest = os.path.join(dest_dir, fname)
            if not os.path.exists(src):
                print(f"  MISSING (not found at top level): {fname}")
                total_missing += 1
                continue
            if os.path.exists(dest):
                print(f"  SKIP (already exists at destination): {fname}")
                total_skipped_existing += 1
                continue
            if apply:
                shutil.move(src, dest)
            else:
                print(f"  WOULD MOVE: {fname}")
            total_moved += 1

    print(f"\n{'Moved' if apply else 'Would move'}: {total_moved} | "
          f"Missing: {total_missing} | Already at destination: {total_skipped_existing}")

if __name__ == '__main__':
    main()
