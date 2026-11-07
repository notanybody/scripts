#!/usr/bin/env python3
"""
ONE-OFF script for the 2026-10-24 /Volumes/stash/studio loose-file sort.
This embeds a hand-reviewed classification of the specific 130 unmatched
filenames from that run (not a general-purpose parser — it won't do anything
useful against a different pile of files). Creates one new 'model index/'
folder per recurring (2+ file) performer and moves their files in. Everything
else (singletons, multi-performer scenes, unnamed files) is left untouched.

Default is DRY RUN — only reports what it would do. Pass --apply to actually
create folders and move files.

Usage:
  python3 sort_studio_loose_apply.py <studio_path>            # dry run
  python3 sort_studio_loose_apply.py <studio_path> --apply     # actually move
"""
import os
import sys
import shutil

RECURRING = {
    "Lily Starfire": [
        "DadCrush - 2023 05 30 Lily Starfire The Support You Need_@JackCity on Telegram.mp4",
        "FamilyXXX - 2023 03 31 Lily Starfire_@JackCity on Telegram.mp4",
        "FilthyMassage - 2022 07 30 Lily Starfire Lubing Up Luscious Lily_@JackCity on Telegram.mp4",
        "GloryHole-Initiations - 2023 06 08 Lily Starfire_@JackCity on Telegram.mp4",
        "HijabHookup - 2022 11 14 Lily Starfire You Silly American_@JackCity on Telegram.mp4",
        "HotwifeXXX - 2022 12 14 Lily Starfire_@JackCity on Telegram.mp4",
        "HussiePass - 2022 05 13 Lily Starfire The First Thing Guys Notice_@JackCity on Telegram.mp4",
        "HussiePass - 2022 12 23 Lily Starfire She Loves Big Dicks_@JackCity on Telegram.mp4",
        "Inserted - 2023 07 20 Lily Starfire_@JackCity on Telegram.mp4",
        "MyDirtyMaid - 2022 11 17 Lily Starfire_@JackCity on Telegram.mp4",
        "MyPervyFamily - 2022 07 21 Lily Starfire I Help You And You Help Me_@JackCity on Telegram.mp4",
        "MySistersHotFriend - 2022 09 15 Lily Starfire_@JackCity on Telegram.mp4",
        "OnlyTeenBlowJobs - 2023 08 03 Lily Starfire_@JackCity on Telegram.mp4",
        "PerfectGirlfriend - 2022 12 27 Lily Starfire First Day Of Summer_@JackCity on Telegram.mp4",
        "RKPrime - 2022 08 04 Lily Starfire She Needs Throating Practice_@JackCity on Telegram.mp4",
        "RawWhiteMeat - E68 Lily Starfire_@JackCity on Telegram.mp4",
        "SexyModernBull - 2023 05 05 Lily Starfire_@JackCity on Telegram.mp4",
        "Tushy - 2023 19 Lily Starfire Blown Opportunities_@JackCity on Telegram.mp4",
        "TushyRaw - 2022 12 28 Lily Starfire_@JackCity on Telegram.mp4",
        "VirtualPorn - 2022 07 07 Lily Starfire Starfire Getting Ready to Fuck XXX VR180_@JackCity on Telegram.mp4",
    ],
    "Numi Zarah": [
        "DirtyAuditions - 2021 12 01 Numi Zarah_@JackCity on Telegram.mp4",
        "Facials4K - 2022 05 17 Numi Zarah Photoshoot Orgy_@JackCity on Telegram.mp4",
        "GangbangCreampie - 2022 04 01 G331 Numi Zarah_@JackCity on Telegram.mp4",
        "GangbangCreampie - 2022 04 04 G331 Numi Zarah BTS_@JackCity on Telegram.mp4",
        "HussiePass - 2022 05 27 Numi Zarah Our First Bangladeshi Girl_@JackCity on Telegram.mp4",
        "Inserted - 2022 06 09 Numi Zarah_@JackCity on Telegram.mp4",
        "JOIBabes - 2022 11 28 Numi Zarah_@JackCity on Telegram.mp4",
        "KarupsHA - 2022 06 09 Numi Zarah Numis Nude Show_@JackCity on Telegram.mp4",
        "KarupsHA - 2022 06 20 Numi Zarah Bad Robot_@JackCity on Telegram.mp4",
        "KinkyFamily - 2022 01 28 Numi Zarah Fucking My Busty Stepsister_@JackCity on Telegram.mp4",
        "MyDirtyMaid - 2022 09 22 Numi Zarah_@JackCity on Telegram.mp4",
        "OurLittleSecret - 2023 07 17 Numi Zarah Big Dick Beats Boyfriend_@JackCity on Telegram.mp4",
        "POVMasters - 2022 01 24 Numi Zarah_@JackCity on Telegram.mp4",
        "PrivateCasting-X - 2021 12 18 Numi Zarah Busty Brown Gal Loves Big Cock_@JackCity on Telegram.mp4",
        "SexyModernBull - 2022 11 03 Numi Zarah_@JackCity on Telegram.mp4",
        "SpankMonster - 2022 01 05 Numi Zarah Is A Sex Freak_@JackCity on Telegram.mp4",
        "TittyAttack - 2022 02 11 Numi Zarah The Irresistible Numi_@JackCity on Telegram.mp4",
    ],
    "Roxie Sinner": [
        "DirtyAuditions - 2021 12 01 Roxie Sinner_@L3AKZONE TELEGRAM.mp4",
        "FamilyTherapy - 202021 Roxie Sinner Fast Friends_@L3AKZONE TELEGRAM.mp4",
        "GoStuckYourself - 2022 05 18 Roxie Sinner One For The Team XX_@L3AKZONE TELEGRAM.mp4",
        "HussiePass - 2021 12 03 Roxie Sinner Roxie Gets Sloppy_@L3AKZONE TELEGRAM.mp4",
        "IMadePorn - 2021 12 14 Roxie Sinner A Busty Visitor_@L3AKZONE TELEGRAM.mp4",
        "MyGirlfriendsBustyFriend - 2022 02 28 Roxie Sinner_@L3AKZONE TELEGRAM.mp4",
        "MyPervyFamily - 2022 03 26 Roxie Sinner I Think Your Mom Knows About Us_@L3AKZONE TELEGRAM.mp4",
        "MyPervyFamily - 2022 12 31 Roxie Sinner Hand Comes In Handy Again_@L3AKZONE TELEGRAM.mp4",
        "Nympho - 2022 01 14 Roxie Sinner_@L3AKZONE TELEGRAM.mp4",
        "SexSelector - 2022 04 15 Roxie Sinner Getting Schoold _@L3AKZONE TELEGRAM.mp4",
        "Swallowed - 2022 03 28 Roxie Sinner_@L3AKZONE TELEGRAM.mp4",
        "Swallowed - 2022 06 09 Roxie Sinner_@L3AKZONE TELEGRAM.mp4",
        "TeenPies - 2022 11 27 Roxie Sinner Roxies Fantasy Cum True_@L3AKZONE TELEGRAM.mp4",
    ],
    "Abella Danger": [
        "dirty masseur - abella danger.mp4",
        "doctor adventures - abella danger 1.mp4",
        "doctor adventures - abella danger 2.mp4",
        "evil angel - abella danger.mp4",
        "fitting room - abella danger.mp4",
        "hands on hardcore - abella danger.mp4",
        "pornstars like it big - abella danger.mp4",
        "stranded teens - abella danger.mp4",
    ],
    "Megan Vaughn": [
        "Megan Vaughn 1.flv",
        "Megan Vaughn 2.mp4",
        "Megan Vaughn 3.flv",
        "Megan Vaughn 4.flv",
    ],
    "Teanna Trump": [
        "teanna-trump-201.mp4",
        "teanna-trump-203.mp4",
        "teanna-trump-204.mp4",
        "teanna-trump-205.mp4",
    ],
    "Willow Ryder": [
        "willow-ryder-13.mp4",
        "willow-ryder-15.mp4",
        "willow-ryder-the-good-girl-480p.mp4",
    ],
    "Cherry Hilson": [
        "!cherry-hilson-150.MP4",
        "Sista Slam - Cherry Hilson.mp4",
    ],
    "Anya Ivy": [
        "Casting Couch X - Anya Ivy.mp4",
        "in the crack - anya ivy.mp4",
    ],
    "Abby Lee Brazil": [
        "Reality Junkies - Abby Lee Brazil.mp4",
        "Woodman Casting X - Abby Lee Brazil.mp4",
    ],
}

def folder_name_for(performer):
    return performer.lower()

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 sort_studio_loose_apply.py <studio_path> [--apply]")
        print("  Default is dry-run. Pass --apply to actually create folders and move files.")
        sys.exit(1)

    base = sys.argv[1].rstrip('/')
    apply = '--apply' in sys.argv
    model_dir = os.path.join(base, 'model index')

    print("APPLY MODE — folders will be created and files moved\n" if apply
          else "DRY RUN — no changes will be made (pass --apply to move)\n")

    total_moved = total_missing = total_skipped_existing = 0

    for performer, files in RECURRING.items():
        folder_name = folder_name_for(performer)
        dest_dir = os.path.join(model_dir, folder_name)
        dest_exists = os.path.isdir(dest_dir)

        print(f"{performer} -> model index/{folder_name}/  ({len(files)} files)"
              + ("  [folder already exists!]" if dest_exists else ""))

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
