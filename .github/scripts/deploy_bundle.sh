#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <bundle-name> <dest-prefix> \"dir1 dir2 ...\"" >&2
  exit 1
}

[ $# -ge 3 ] || usage

BUNDLE_NAME="$1"
DEST_PREFIX="$2"
DIRS="$3"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

shopt -s nullglob

mkdir -p "$WORKDIR"

for dir in $DIRS; do
  if ls "$dir"/*.py >/dev/null 2>&1; then
    cp "$dir"/*.py "$WORKDIR"/
  fi
done

MANIFEST="$WORKDIR/manifest.txt"
echo "" >> "$MANIFEST"

for file in "$WORKDIR"/*.py; do
  [ -f "$file" ] || continue
  filename="$(basename "$file")"
  hash="$(sha256sum "$file" | cut -d' ' -f1)"
  echo "$filename $hash" >> "$MANIFEST"
done

aws s3 sync "$WORKDIR"/ "s3://ae-pico/$DEST_PREFIX" --delete

