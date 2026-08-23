#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

MICROPYTHON_BIN="${MICROPYTHON_BIN:-$HOME/micropython/ports/unix/build-standard/micropython}"

if [ ! -x "$MICROPYTHON_BIN" ]; then
    echo "MicroPython unix binary not found at $MICROPYTHON_BIN"
    echo "Run: bash $SCRIPT_DIR/setup.sh"
    echo "(or set MICROPYTHON_BIN to point at an existing build)"
    exit 1
fi

# MICROPYPATH, once set at all, REPLACES the interpreter's default sys.path
# rather than extending it -- which would cut off access to built-in/frozen
# modules like asyncio. Query the interpreter's own default first, then
# append our directories to it.
DEFAULT_PATH="$("$MICROPYTHON_BIN" -c 'import sys; print(":".join(sys.path))')"
export MICROPYPATH="$REPO_ROOT/libraries:$REPO_ROOT/infodisplay:$SCRIPT_DIR:$DEFAULT_PATH"

cd "$REPO_ROOT"

case "${1:-all}" in
    check) files=("$SCRIPT_DIR"/*_check.py) ;;
    bench) files=("$SCRIPT_DIR"/*_bench.py) ;;
    all)   files=("$SCRIPT_DIR"/*_check.py "$SCRIPT_DIR"/*_bench.py) ;;
    *)     files=("$@") ;;
esac

status=0
for f in "${files[@]}"; do
    [ -e "$f" ] || continue
    echo "=== $(basename "$f") ==="
    if ! "$MICROPYTHON_BIN" "$f"; then
        status=1
    fi
    echo
done

exit $status
