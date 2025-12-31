#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <bundle-name> <dest-prefix> \"dir_or_file1 dir_or_file2 ...\"" >&2
  exit 1
}

[ $# -ge 3 ] || usage

BUNDLE_NAME="$1"
DEST_PREFIX="$2"
DIRS="$3"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

# Safety: never sync to bucket root with --delete
if [[ -z "${DEST_PREFIX}" || "${DEST_PREFIX}" == "/" ]]; then
  echo "Refusing to deploy '${BUNDLE_NAME}' to empty or root dest-prefix (would delete entire bucket)." >&2
  exit 2
fi

shopt -s nullglob

mkdir -p "$WORKDIR"

for dir in $DIRS; do
  if [ -d "$dir" ]; then
    if ls "$dir"/*.py >/dev/null 2>&1; then
      cp "$dir"/*.py "$WORKDIR"/
    fi
  elif [ -f "$dir" ]; then
    cp "$dir" "$WORKDIR"/
  fi
done

# Compile .py to .mpy for all bundles except 'entry'
if [[ "${BUNDLE_NAME}" != "entry" ]]; then
  echo "Compiling Python files to .mpy format..."
  for file in "$WORKDIR"/*.py; do
    [ -f "$file" ] || continue
    echo "  Compiling $(basename "$file")..."
    python -m mpy_cross -march=armv6m "$file"
    rm "$file"  # Remove the .py file after successful compilation
  done
fi

MANIFEST="$WORKDIR/manifest.txt"
echo "" >> "$MANIFEST"

# Generate manifest for .py files (entry bundle) or .mpy files (other bundles)
if [[ "${BUNDLE_NAME}" == "entry" ]]; then
  for file in "$WORKDIR"/*.py; do
    [ -f "$file" ] || continue
    filename="$(basename "$file")"
    hash="$(sha256sum "$file" | cut -d' ' -f1)"
    echo "$filename $hash" >> "$MANIFEST"
  done
else
  for file in "$WORKDIR"/*.mpy; do
    [ -f "$file" ] || continue
    filename="$(basename "$file")"
    hash="$(sha256sum "$file" | cut -d' ' -f1)"
    echo "$filename $hash" >> "$MANIFEST"
  done
fi

aws s3 sync "$WORKDIR"/ "s3://ae-pico/$DEST_PREFIX" --delete

