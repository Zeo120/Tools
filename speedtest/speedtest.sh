#!/usr/bin/env bash
# Internet Speed Test Launcher (CLI Braille Speedometer, Ping, Jitter, DL & UL)
# Usage:
#   ./speedtest.sh              # Interactive live 60 FPS Braille speedometer
#   ./speedtest.sh -s           # Simple plain-text output
#   ./speedtest.sh -j           # JSON output
#   ./speedtest.sh --bytes      # Display speeds in MB/s instead of Mbps
#   ./speedtest.sh -d 10        # 10s test duration
#   ./speedtest.sh --list-servers

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$(which python3 2>/dev/null || which python 2>/dev/null || echo "/data/data/com.termux/files/usr/bin/python3")"

if [ ! -x "$PYTHON_BIN" ]; then
    echo "Error: Python 3 not found. Please install python (pkg install python or apt install python3)."
    exit 1
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/speedtest.py" "$@"
