#!/bin/bash
set -uo pipefail

SRC="$HOME/Library/Messages/Attachments"
DEST="/Volumes/Base 1/messages-attachments-backup"
LOG="$HOME/scripts/backup_messages_attachments.log"

mkdir -p "$DEST/images" "$DEST/videos" "$DEST/audio" "$DEST/other"

count=0
total=$(find "$SRC" -type f | wc -l | tr -d ' ')
echo "Starting copy of $total files at $(date)" > "$LOG"

find "$SRC" -type f | while IFS= read -r f; do
    ext=$(echo "${f##*.}" | tr '[:upper:]' '[:lower:]')
    case "$ext" in
        jpg|jpeg|png|gif|heic|heics|webp|avif|bmp) sub="images" ;;
        mov|mp4|3gp|m4v) sub="videos" ;;
        caf|amr|m4a) sub="audio" ;;
        *) sub="other" ;;
    esac

    # Extract short id from the parent "at_N_GUID" folder to keep names unique
    parent=$(basename "$(dirname "$f")")
    shortid=$(echo "$parent" | grep -oE '[A-F0-9]{8}' | head -1)
    [ -z "$shortid" ] && shortid=$(echo "$parent" | tr -cd 'A-Za-z0-9' | head -c 8)

    base=$(basename "$f")
    dest="$DEST/$sub/${shortid}_${base}"

    if [ ! -e "$dest" ]; then
        cp -p "$f" "$dest" 2>>"$LOG"
    fi

    count=$((count + 1))
    if (( count % 500 == 0 )); then
        echo "$(date '+%H:%M:%S') - copied $count / $total files" >> "$LOG"
    fi
done

echo "$(date '+%H:%M:%S') - DONE. Copied $count / $total files" >> "$LOG"
