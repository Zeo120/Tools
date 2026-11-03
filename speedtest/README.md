# Proprietary Speed Test Interface & Server

A high-performance, zero-dependency network speed testing interface built to deliver consistent, reproducible, wire-speed network benchmarks **without relying on third-party speedtest APIs** (such as Ookla, Fast.com, or third-party scraping).

```
  ╔════════════════════════════════════════════════════════════════╗
  ║                PROPRIETARY SPEED TEST ENGINE                   ║
  ╚════════════════════════════════════════════════════════════════╝

  Client:   Reliance Jio Infocomm Limited (2409:40f0:7449:...) [Guntur]
  Server:   [DIRECT BACKBONE] Nagpur Anycast Node (NAG)
  ────────────────────────────────────────────────────────────────
                    ⢀⣠⣤⣶⣶⣶⣶⣤⣄⡀
                ⢀⣴⡿⠋⠁          ⠈⠙⢿⣦⡀
              ⢠⣾⠏      ⢠⣾⣷⡄      ⠹⣷⡄
             ⣴⡿⠁       ⠈⣿⣿⠁        ⠈⢿⣦
            ⣼⡿⠁         ⠘⢿⠃          ⠈⣿⣇
            ⣿⡇                           ⢸⣿
            ⣿⡇              ⢠             ⢸⣿
            ⠹⣷⣄          ⣠⡿⠁          ⣠⣾⠏
  Speed:    86.4 Mbps   (Scale: 0-100 Mbps)
  Status: ▼ [DOWNLOAD] Testing Download Speed (Multi-Stream)...

  ████████████████████████████████████████████▍░░░░░░░░  86%
  ▃▅▆▇▇▆▅▆▇██▇▆▅▄▃▂▂▃▄▅▆▇████▇▆▅▄▃▂▃▄▅▆▇██ Live
  ────────────────────────────────────────────────────────────────
  Ping: 34.2 ms   Jitter: 4.8 ms   DL: 86.4 Mbps (31.2 MB)
  UL: 2.8 Mbps (1.1 MB)
  ╚════════════════════════════════════════════════════════════════╝
```

---

## Why Proprietary Testing?

Third-party speedtest APIs (such as Speedtest.net / Ookla scraping) suffer from major inconsistencies:
- **Volunteer Host Congestion**: Many 3rd-party servers are run by volunteer ISPs on non-standard ports (like `:8080`) that throttle, drop packets, or run behind self-signed SSL certificates.
- **Erratic Selection**: Flawed candidate pinging frequently routes tests through distant or overloaded servers, yielding wildly fluctuating numbers (e.g. 116 Mbps on one run, 29 Mbps on the next).
- **Aggressive Throttling & 403 Blocks**: Third-party APIs aggressively block automated requests, causing tests to fail with HTTP 403 Forbidden errors.

**The Solution:**
This proprietary interface provides two zero-dependency, wire-speed testing modes:
1. **Direct-Pipe Internet Mode (Default)**: Uses direct, neutral high-capacity backbone pipes without calling any third-party speedtest APIs. Delivers reproducible, low-jitter, enterprise-grade benchmarks.
2. **Dedicated Proprietary Server Mode (`--server` / `--serve`)**: Run a local or remote speed test daemon capable of testing full line rate (1 Gbps - 10 Gbps+) across local Wi-Fi, Ethernet LAN, 5G hotspots, VPNs, or private cloud links. Includes a built-in modern HTML5 Web GUI.

---

## Key Features

- **Zero 3rd-Party API Dependencies**: Completely autonomous network benchmarking with zero external API calls.
- **10Gbps+ Wire-Speed Capable**: Pre-allocated synthetic streaming buffers with zero disk I/O and zero-copy chunk delivery.
- **60 FPS Braille Speedometer Dial**: 72×32 sub-pixel canvas rendering a 250° circular arc with critically damped second-order spring physics.
- **Dynamic Auto-Scaling**: Speedometer smoothly upscales (25 → 50 → 100 → 250 → 500 → 1000 → 2500+ Mbps) to handle fast connections.
- **LAN Zero-Config Auto-Discovery (`--discover`)**: UDP broadcast discovery automatically detects proprietary servers running on the local network.
- **Built-in HTML5 Web Interface**: Serving `http://<ip>:8080/` gives any browser (phone, tablet, PC) a canvas-based speed test dashboard.
- **Low-Latency RTT & RFC 3550 Jitter**: Sub-millisecond round-trip time and jitter telemetry.
- **Universal Cross-Platform**: Pure Python 3 standard library (`urllib`, `socket`, `threading`, `http.server`). Runs on Android (Termux), Linux, macOS, and Windows.

---

## Usage Guide

### 1. Direct Internet Speed Test (Default)
Tests your connection against high-capacity direct backbone streams:

**On Windows (PowerShell or CMD):**
```powershell
cd speedtest

# Interactive 60 FPS Braille speedometer dial
.\speedtest.ps1

# Simple plain-text mode (for scripts or logs)
.\speedtest.ps1 -s

# Structured JSON telemetry
.\speedtest.ps1 -j

# Speeds in MegaBytes/sec (MB/s)
.\speedtest.ps1 --bytes
```

**On Linux, macOS, or Android (Termux):**
```bash
cd speedtest

# Interactive live test
./speedtest.sh

# Simple mode
./speedtest.sh -s

# JSON output
./speedtest.sh -j
```

---

### 2. Proprietary Server Mode (LAN, Wi-Fi & Private Cloud)

#### Step A: Start the Server
Launch the proprietary speed test daemon on any host (PC, Raspberry Pi, home server, Android phone in Termux, or cloud instance):

**On Windows:**
```powershell
.\server.ps1 --port 8080
# Or using CMD:
server.cmd --port 8080
```

**On Linux / macOS / Termux:**
```bash
./server.sh --port 8080
```

This starts:
- HTTP API on `http://0.0.0.0:8080/`
- Web GUI on `http://<your-ip>:8080/` (open in your phone or PC browser!)
- UDP LAN Discovery responder on port 8081

#### Step B: Run the Client Against Your Server
From any other machine or phone on the same network:

```bash
# Connect directly by IP and port:
./speedtest.sh --server 192.168.1.50:8080

# Or auto-discover servers on your Wi-Fi/LAN:
./speedtest.sh --discover
```

---

### 3. Browser-Based Web GUI
When the server is running, open `http://<server-ip>:8080/` in any browser:
- Canvas-rendered animated speedometer dial
- Live real-time latency and jitter measurement
- Multi-stream parallel download and upload tests
- Zero client installation needed on phones or guest devices

---

## CLI Options Reference

| Flag | Shorthand | Default | Description |
|---|---|---|---|
| `--server <ip:port>` | `-H` | `None` | Connect to proprietary server (e.g. `192.168.1.100:8080`) |
| `--discover` | | `false` | Auto-discover proprietary servers on the local LAN/Wi-Fi |
| `--serve` | `-S` | `false` | Start the proprietary server directly from the speedtest CLI |
| `--port <p>` | | `8080` | Port for the speed test server |
| `--simple` | `-s` | `false` | Plain-text output without ANSI animations |
| `--json` | `-j` | `false` | Machine-readable JSON telemetry |
| `--bytes` | | `false` | Display speeds in MB/s instead of Mbps |
| `--duration <sec>` | `-d` | `8` | Duration in seconds per test phase |
| `--threads <n>` | `-t` | `4` | Number of parallel worker streams |
| `--no-download` | | `false` | Skip download speed phase |
| `--no-upload` | | `false` | Skip upload speed phase |
| `--fps <n>` | `-f` | `60` | Target frame rate for the interactive display |
| `--no-color` | | `false` | Disable ANSI color rendering |

---

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.
