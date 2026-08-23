#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="${MICROPYTHON_SRC_DIR:-$HOME/micropython}"
MICROPYTHON_REF="${MICROPYTHON_REF:-}"
BIN="$SRC_DIR/ports/unix/build-standard/micropython"

if [ -x "$BIN" ]; then
    echo "Already built: $BIN"
    exit 0
fi

if ! command -v gcc >/dev/null 2>&1 || ! command -v make >/dev/null 2>&1; then
    echo "Missing build tools. On Debian/Ubuntu:"
    echo "  sudo apt-get update && sudo apt-get install -y build-essential libffi-dev git pkg-config"
    exit 1
fi

if [ ! -d "$SRC_DIR" ]; then
    if [ -n "$MICROPYTHON_REF" ]; then
        git clone --depth 1 --branch "$MICROPYTHON_REF" https://github.com/micropython/micropython.git "$SRC_DIR"
    else
        git clone --depth 1 https://github.com/micropython/micropython.git "$SRC_DIR"
    fi
fi

make -C "$SRC_DIR/mpy-cross"
( cd "$SRC_DIR/ports/unix" && make submodules && make -j"$(nproc 2>/dev/null || echo 2)" )

echo "Built: $BIN"
