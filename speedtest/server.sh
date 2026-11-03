#!/usr/bin/env bash
# Proprietary Speed Test Server Launcher
# Usage:
#   ./server.sh                 # Starts server on port 8080
#   ./server.sh --port 9000     # Custom port

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$(which python3 2>/dev/null || which python 2>/dev/null || echo "/data/data/com.termux/files/usr/bin/python3")"

if [ ! -x "$PYTHON_BIN" ]; then
    echo "Error: Python 3 not found. Please install python."
    exit 1
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/server.py" "$@"
