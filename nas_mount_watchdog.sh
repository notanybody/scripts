#!/bin/bash
# Checks the personal_folder SMB share and remounts it if it dropped.
# Run periodically by com.jackwillis.nasmountwatchdog LaunchAgent.
MOUNT_POINT="/Volumes/personal_folder"
SMB_URL="smb://DXP4800PLUS-RIN._smb._tcp.local/personal_folder"
LOG="$HOME/scripts/nas_mount_watchdog.log"

timestamp() { date "+%Y-%m-%d %H:%M:%S"; }

# Only act when the mount is genuinely gone. Do NOT force-unmount a mount
# just because a liveness check was briefly slow — under real I/O load (e.g.
# a long recursive scan) that's a false positive, and force-unmounting a
# mount that's actually busy breaks whatever is using it.
if mount | grep -q " on ${MOUNT_POINT} "; then
    exit 0
fi

echo "$(timestamp) Not mounted, attempting remount" >> "$LOG"
osascript -e "mount volume \"$SMB_URL\"" >> "$LOG" 2>&1
