#!/usr/bin/env bash
# Android 30W Power Meter Launcher (100ms hardware polling, 60 FPS display)
# Usage:
#   ./power_draw.sh             # Starts live power meter (60 FPS, 30W max)
#   ./power_draw.sh -f 60       # Run at 60 FPS
#   ./power_draw.sh -m 30       # Set maximum scale to 30W
#   ./power_draw.sh -s          # Single instantaneous snapshot
#   ./power_draw.sh -j          # JSON output

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$(which python3 2>/dev/null || which python 2>/dev/null || echo "/data/data/com.termux/files/usr/bin/python3")"

if [ ! -x "$PYTHON_BIN" ]; then
    echo "Error: Python 3 not found. Please install python (pkg install python)."
    exit 1
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/power_draw.py" "$@"
