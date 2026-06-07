#!/bin/bash
# Usage: ./transfer_tags.sh /Volumes/ExternalDrive /Volumes/YourNAS

SOURCE="${1%/}"
DEST="${2%/}"

if [ -z "$SOURCE" ] || [ -z "$DEST" ]; then
  echo "Usage: $0 <source_mount> <dest_mount>"
  exit 1
fi

echo "Building filename index from destination..."
declare -A dest_map
declare -A dest_dupes

while IFS= read -r -d '' file; do
  name=$(basename "$file")
  if [ -n "${dest_map[$name]}" ]; then
    dest_dupes[$name]=1
  fi
  dest_map[$name]="$file"
done < <(find "$DEST" -not -name "._*" -type f -print0)

echo "Index built. Processing tagged files..."

TAGGED=0
MISSING=0
FAILED=0
DUPES=0

while IFS= read -r -d '' file; do
  tags=$(xattr -px com.apple.metadata:_kMDItemUserTags "$file" 2>/dev/null)
  [ -z "$tags" ] && continue

  name=$(basename "$file")

  if [ -n "${dest_dupes[$name]}" ]; then
    echo "AMBIGUOUS (same filename in multiple folders): $name"
    ((DUPES++))
    continue
  fi

  dest_file="${dest_map[$name]}"

  if [ -z "$dest_file" ]; then
    echo "MISSING: $name"
    ((MISSING++))
    continue
  fi

  if xattr -wx com.apple.metadata:_kMDItemUserTags "$tags" "$dest_file" 2>/dev/null; then
    echo "OK: $name"
    ((TAGGED++))
  else
    echo "FAILED (NAS may not support xattr): $name"
    ((FAILED++))
  fi
done < <(find "$SOURCE" -not -name "._*" -type f -print0)

echo ""
echo "Done — Tagged: $TAGGED | Missing: $MISSING | Ambiguous: $DUPES | Failed: $FAILED"
