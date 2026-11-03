# Internet Speed Test CLI (Braille Speedometer, Ping, Jitter, DL & UL)

High-performance, zero-dependency Internet Speed Test utility for the terminal. Features a 60 FPS sub-pixel Braille dot-matrix speedometer dial, physics-damped needle kinematics, real-time download and upload telemetry, and structured outputs for scripting and benchmarking.

```
  ╔════════════════════════════════════════════════════════════════╗
  ║                INTERNET SPEED TEST TERMINAL                   ║
  ╚════════════════════════════════════════════════════════════════╝

  Client: Jio (152.57.237.104)
  Server: ACT FIBERNET - Vijayawada [India]
  ────────────────────────────────────────────────────────────────
                    ⢀⣠⣤⣶⣶⣶⣶⣤⣄⡀
                ⢀⣴⡿⠋⠁          ⠈⠙⢿⣦⡀
              ⢠⣾⠏      ⢠⣾⣷⡄      ⠹⣷⡄
             ⣴⡿⠁       ⠈⣿⣿⠁        ⠈⢿⣦
            ⣼⡿⠁         ⠘⢿⠃          ⠈⣿⣇
            ⣿⡇                           ⢸⣿
            ⣿⡇              ⢠             ⢸⣿
            ⠹⣷⣄          ⣠⡿⠁          ⣠⣾⠏
  Speed:   116.9 Mbps   (Scale: 0-250 Mbps)
  Status: ▼ [DOWNLOAD] Testing Download Speed...

  ████████████████████████████████████████████▍░░░░░░░░  82%
  ▃▅▆▇▇▆▅▆▇██▇▆▅▄▃▂▂▃▄▅▆▇████▇▆▅▄▃▂▃▄▅▆▇██ Live
  ────────────────────────────────────────────────────────────────
  Ping: 180.7 ms  Jitter: 55.1 ms  DL: 116.9 Mbps (28.4 MB)
  UL: 0.7 Mbps (0.4 MB)
  ╚════════════════════════════════════════════════════════════════╝
```

---

## Key Features

- **Braille Dot-Matrix Speedometer Dial**: 72x32 sub-pixel canvas rendering a 250° circular arc gauge with radial ticks and a rotating needle.
- **Physics-Damped Spring Needle**: Critically damped second-order spring dynamics simulate real physical meter inertia without visual stutter or abrupt jumps.
- **Dynamic Auto-Scaling**: The dial scale dynamically expands (25 → 50 → 100 → 250 → 500 → 1000 Mbps) based on connection throughput.
- **Multi-Stream Parallel Engine**: Multi-threaded parallel HTTP GET (download) and chunked HTTP POST (upload) streams saturate available bandwidth.
- **Low-Latency Latency & Jitter**: Computes minimum, average, maximum RTT, and RFC 3550 / Ookla jitter across multiple ping samples.
- **Sub-Block Fractional Gauge**: 46-column progress bar with 1/8th-step Unicode fractional precision (`▏▎▍▌▋▊▉█`).
- **Real-Time Scrolling Sparkline**: Scrolling waveform graph visualizes speed stability and bufferbloat in real time.
- **Zero External Dependencies**: Pure Python 3 standard library (`urllib`, `socket`, `threading`, `json`, `math`). Runs anywhere with Python 3 installed.
- **Universal Cross-Platform**: Optimized for Android Termux, Linux, macOS, and Windows terminals.
- **Scripting & CI/CD Ready**: Supports `--json` for machine parsing and `--simple` for lightweight non-interactive logging.

---

## Usage

### 1. Interactive Animated Mode (Default)
Run with the live 60 FPS Braille speedometer dial:

**On Windows (PowerShell or CMD):**
```powershell
cd speedtest

# Using PowerShell launcher
.\speedtest.ps1

# Or using Windows Batch / Command Prompt
.\speedtest.cmd
```

**On Linux, macOS, or Android (Termux):**
```bash
cd speedtest

# Using POSIX launcher
./speedtest.sh

# Or directly with Python 3
python3 speedtest.py
```

### 2. Custom Duration and Parallel Threads
```bash
# Run 10-second download and upload with 6 worker threads
./speedtest.sh -d 10 -t 6
```

### 3. Display in MegaBytes per Second (MB/s)
```bash
./speedtest.sh --bytes
```

### 4. Simple Plain-Text Mode
Clean, unformatted text output ideal for headless servers, ssh sessions, or cron logs:
```bash
./speedtest.sh -s
```
Output:
```text
Initializing Speed Test...
Client: Gtpl Kcbpl Broadband Pvt (103.171.247.142)
Server: ACT FIBERNET (Vijayawada)
Measuring ping and jitter...
Latency: 180.72 ms (Jitter: 55.09 ms)
Testing download speed...
Download: 116.93 Mbps
Testing upload speed...
Upload: 0.69 Mbps
Grade: [D] Low Bandwidth / High Latency (Experiencing bottlenecks)
```

### 5. Structured JSON Output
Full structured benchmark results for automated pipelines and monitoring:
```bash
./speedtest.sh -j
```
Sample JSON:
```json
{
  "timestamp": "2026-11-03T03:33:58.502022+00:00",
  "client": {
    "ip": "103.171.247.142",
    "isp": "Gtpl Kcbpl Broadband Pvt",
    "city": "",
    "country": "IN",
    "lat": 22.518,
    "lon": 88.3832
  },
  "server": {
    "id": "25285",
    "sponsor": "DVPL",
    "name": "Guntur",
    "country": "India",
    "distance_km": 14,
    "host": "speedgnt.dvpl.in.prod.hosts.ooklaserver.net:8080"
  },
  "ping": {
    "avg_ms": 174.15,
    "min_ms": 104.5,
    "max_ms": 290.12,
    "jitter_ms": 40.77,
    "samples": [290.12, 250.95, 136.77, 104.5, 140.56, 128.07, 162.94, 179.29]
  },
  "download": {
    "mbps": 90.41,
    "mb_per_sec": 11.3,
    "bytes": 22972979
  },
  "upload": {
    "mbps": 1.23,
    "mb_per_sec": 0.15,
    "bytes": 393270
  },
  "quality": {
    "grade": "D",
    "description": "Low Bandwidth / High Latency (Experiencing bottlenecks)"
  }
}
```

### 6. List Closest Servers & Select Specific Server
```bash
# List nearest servers
./speedtest.sh --list-servers

# Test against a specific server ID
./speedtest.sh --server 25285
```

### 7. Download-Only or Upload-Only Test
```bash
# Skip upload test
./speedtest.sh --no-upload

# Skip download test
./speedtest.sh --no-download
```

---

## Command-Line Arguments Reference

| Option | Shorthand | Default | Description |
|---|---|---|---|
| `--simple` | `-s` | `false` | Plain text output without ANSI animations |
| `--json` | `-j` | `false` | JSON formatted telemetry |
| `--bytes` | | `false` | Display speeds in MB/s instead of Mbps |
| `--duration` | `-d` | `8` | Duration in seconds per test phase |
| `--threads` | `-t` | `4` | Number of parallel worker threads |
| `--server <id>` | | `None` | Force test to a specific server ID |
| `--list-servers` | | `false` | List 15 closest servers and exit |
| `--no-download` | | `false` | Skip download speed phase |
| `--no-upload` | | `false` | Skip upload speed phase |
| `--fps <n>` | `-f` | `60` | Target frame rate for the interactive display |
| `--no-color` | | `false` | Disable 24-bit ANSI color rendering |

---

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.
