#!/usr/bin/env python3
"""
Proprietary Speed Test Server
=============================
Ultra-lightweight, zero-dependency high-throughput speed test server.
Supports:
- High-speed zero-copy synthetic download streaming (1Gbps+ capable)
- Wire-speed upload sink with real-time throughput tracking
- Microsecond latency (RTT) and jitter probing
- UDP local network broadcast discovery (LAN / Wi-Fi)
- Built-in responsive HTML5 web interface for browser testing
"""

import sys
import os
import time
import json
import socket
import threading
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

# Pre-allocated 1MB buffer of random-like synthetic data for zero-copy streaming
CHUNK_SIZE = 64 * 1024  # 64 KB chunks
STREAM_BUFFER = (b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!@#$%^&*()" * (CHUNK_SIZE // 74 + 1))[:CHUNK_SIZE]

# Embedded Web UI for browser-based testing
WEB_INTERFACE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Proprietary Speed Test</title>
<style>
  :root {
    --bg: #0f141c;
    --card: #182232;
    --border: #263852;
    --accent: #00e5ff;
    --green: #00e676;
    --purple: #d500f9;
    --text: #e0e6ed;
    --dim: #8b9bb4;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; }
  body { background: var(--bg); color: var(--text); min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 20px; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 32px; max-width: 680px; width: 100%; box-shadow: 0 12px 36px rgba(0,0,0,0.4); text-align: center; }
  h1 { font-size: 24px; color: var(--accent); margin-bottom: 8px; letter-spacing: 1px; }
  p.subtitle { color: var(--dim); font-size: 14px; margin-bottom: 24px; }
  .canvas-container { position: relative; width: 280px; height: 160px; margin: 0 auto 16px auto; }
  canvas { width: 100%; height: 100%; }
  .speed-readout { font-size: 44px; font-weight: 800; color: var(--accent); margin-bottom: 4px; font-variant-numeric: tabular-nums; }
  .unit { font-size: 18px; color: var(--dim); margin-left: 4px; }
  .status { font-size: 14px; color: var(--dim); margin-bottom: 24px; height: 20px; }
  .metrics-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 28px; }
  .metric-box { background: rgba(0,0,0,0.25); border: 1px solid var(--border); border-radius: 12px; padding: 14px; }
  .metric-label { font-size: 12px; color: var(--dim); margin-bottom: 4px; text-transform: uppercase; }
  .metric-val { font-size: 20px; font-weight: 700; color: var(--text); font-variant-numeric: tabular-nums; }
  .metric-box.dl .metric-val { color: var(--green); }
  .metric-box.ul .metric-val { color: var(--purple); }
  .btn-start { background: linear-gradient(135deg, #00b0ff, #00e5ff); color: #000; border: none; font-size: 16px; font-weight: 700; padding: 14px 42px; border-radius: 30px; cursor: pointer; transition: transform 0.15s, box-shadow 0.15s; }
  .btn-start:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0, 229, 255, 0.4); }
  .btn-start:disabled { background: #334; color: #667; cursor: not-allowed; transform: none; box-shadow: none; }
  footer { margin-top: 20px; font-size: 12px; color: var(--dim); }
</style>
</head>
<body>
<div class="card">
  <h1>PROPRIETARY SPEED TEST</h1>
  <p class="subtitle">Direct Wire-Speed Testing &bull; Zero External Dependencies</p>
  
  <div class="canvas-container">
    <canvas id="gauge" width="560" height="320"></canvas>
  </div>
  <div class="speed-readout"><span id="speedVal">0.0</span><span class="unit">Mbps</span></div>
  <div class="status" id="statusText">Ready</div>

  <div class="metrics-grid">
    <div class="metric-box">
      <div class="metric-label">Latency / Jitter</div>
      <div class="metric-val" id="pingVal">-- ms</div>
    </div>
    <div class="metric-box dl">
      <div class="metric-label">Download</div>
      <div class="metric-val" id="dlVal">-- Mbps</div>
    </div>
    <div class="metric-box ul">
      <div class="metric-label">Upload</div>
      <div class="metric-val" id="ulVal">-- Mbps</div>
    </div>
  </div>

  <button class="btn-start" id="startBtn" onclick="runTest()">START SPEED TEST</button>
</div>
<footer>Self-Hosted Proprietary Speed Engine &bull; Port <span id="portDisplay">8080</span></footer>

<script>
const gauge = document.getElementById('gauge');
const ctx = gauge.getContext('2d');
let currentGaugeVal = 0;
let targetGaugeVal = 0;
let maxScale = 100;

function drawGauge(val, max) {
  ctx.clearRect(0, 0, 560, 320);
  const cx = 280, cy = 270, r = 210;
  
  // Background track
  ctx.beginPath();
  ctx.arc(cx, cy, r, Math.PI * 0.85, Math.PI * 2.15, false);
  ctx.strokeStyle = '#263852';
  ctx.lineWidth = 26;
  ctx.lineCap = 'round';
  ctx.stroke();

  // Active arc
  const ratio = Math.min(1.0, Math.max(0, val / max));
  const activeEnd = Math.PI * 0.85 + (Math.PI * 1.3) * ratio;
  if (ratio > 0.005) {
    const grad = ctx.createLinearGradient(0, 320, 560, 0);
    grad.addColorStop(0, '#00b0ff');
    grad.addColorStop(0.5, '#00e676');
    grad.addColorStop(1, '#ffea00');
    ctx.beginPath();
    ctx.arc(cx, cy, r, Math.PI * 0.85, activeEnd, false);
    ctx.strokeStyle = grad;
    ctx.lineWidth = 26;
    ctx.lineCap = 'round';
    ctx.stroke();
  }

  // Radial ticks
  for (let i = 0; i <= 10; i++) {
    const a = Math.PI * 0.85 + (Math.PI * 1.3) * (i / 10);
    const x1 = cx + Math.cos(a) * (r - 20);
    const y1 = cy + Math.sin(a) * (r - 20);
    const x2 = cx + Math.cos(a) * (r - 32);
    const y2 = cy + Math.sin(a) * (r - 32);
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.strokeStyle = '#3a506e';
    ctx.lineWidth = 3;
    ctx.stroke();
  }
}

function animateGauge() {
  currentGaugeVal += (targetGaugeVal - currentGaugeVal) * 0.2;
  drawGauge(currentGaugeVal, maxScale);
  requestAnimationFrame(animateGauge);
}
animateGauge();

async function runTest() {
  const btn = document.getElementById('startBtn');
  const status = document.getElementById('statusText');
  const speedEl = document.getElementById('speedVal');
  const pingEl = document.getElementById('pingVal');
  const dlEl = document.getElementById('dlVal');
  const ulEl = document.getElementById('ulVal');

  btn.disabled = true;
  maxScale = 100;
  targetGaugeVal = 0;
  dlEl.innerText = '-- Mbps';
  ulEl.innerText = '-- Mbps';

  // 1. Latency & Jitter
  status.innerText = 'Measuring Latency & Jitter...';
  const pings = [];
  for (let i = 0; i < 8; i++) {
    const t0 = performance.now();
    await fetch('/api/ping');
    pings.push(performance.now() - t0);
    await new Promise(r => setTimeout(r, 60));
  }
  const avgPing = (pings.reduce((a,b)=>a+b,0) / pings.length).toFixed(1);
  let jitter = 0;
  for (let i = 1; i < pings.length; i++) jitter += Math.abs(pings[i] - pings[i-1]);
  jitter = (jitter / (pings.length - 1)).toFixed(1);
  pingEl.innerText = `${avgPing} ms (±${jitter})`;

  // 2. Download Test (Multi-stream 6s)
  status.innerText = 'Testing Download Speed...';
  let dlBytes = 0;
  const dlStart = performance.now();
  let dlRunning = true;

  const dlWorkers = Array.from({length: 4}, async () => {
    while (dlRunning) {
      try {
        const res = await fetch('/api/download?size=25000000');
        const reader = res.body.getReader();
        while (dlRunning) {
          const {done, value} = await reader.read();
          if (done) break;
          dlBytes += value.length;
        }
      } catch(e) { break; }
    }
  });

  const updateDlInterval = setInterval(() => {
    const dt = (performance.now() - dlStart) / 1000;
    const mbps = (dlBytes * 8) / (dt * 1e6);
    speedEl.innerText = mbps.toFixed(1);
    targetGaugeVal = mbps;
    if (mbps > maxScale * 0.85) maxScale = mbps > 500 ? 1000 : (mbps > 200 ? 500 : 250);
  }, 100);

  await new Promise(r => setTimeout(r, 6000));
  dlRunning = false;
  clearInterval(updateDlInterval);
  const dlDuration = (performance.now() - dlStart) / 1000;
  const finalDlMbps = (dlBytes * 8) / (dlDuration * 1e6);
  dlEl.innerText = `${finalDlMbps.toFixed(1)} Mbps`;
  targetGaugeVal = 0;
  speedEl.innerText = '0.0';

  // 3. Upload Test (Multi-stream 6s)
  status.innerText = 'Testing Upload Speed...';
  let ulBytes = 0;
  const ulStart = performance.now();
  let ulRunning = true;
  const dummyPayload = new Uint8Array(256 * 1024);

  const ulWorkers = Array.from({length: 3}, async () => {
    while (ulRunning) {
      try {
        await fetch('/api/upload', { method: 'POST', body: dummyPayload });
        ulBytes += dummyPayload.length;
      } catch(e) { break; }
    }
  });

  const updateUlInterval = setInterval(() => {
    const dt = (performance.now() - ulStart) / 1000;
    const mbps = (ulBytes * 8) / (dt * 1e6);
    speedEl.innerText = mbps.toFixed(1);
    targetGaugeVal = mbps;
    if (mbps > maxScale * 0.85) maxScale = mbps > 500 ? 1000 : (mbps > 200 ? 500 : 250);
  }, 100);

  await new Promise(r => setTimeout(r, 6000));
  ulRunning = false;
  clearInterval(updateUlInterval);
  const ulDuration = (performance.now() - ulStart) / 1000;
  const finalUlMbps = (ulBytes * 8) / (ulDuration * 1e6);
  ulEl.innerText = `${finalUlMbps.toFixed(1)} Mbps`;
  targetGaugeVal = 0;
  speedEl.innerText = '0.0';

  status.innerText = 'Speed Test Complete';
  btn.disabled = false;
}
document.getElementById('portDisplay').innerText = window.location.port || '80';
</script>
</body>
</html>
"""


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server handling simultaneous parallel test streams."""
    daemon_threads = True
    allow_reuse_address = True


class SpeedTestHandler(BaseHTTPRequestHandler):
    """High-throughput request handler for proprietary speed test endpoints."""

    def log_message(self, format, *args):
        # Silence default request logging to avoid slowing down I/O
        return

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]

        # 1. Microsecond Ping Endpoint
        if path in ("/api/ping", "/ping"):
            payload = json.dumps({
                "pong": True,
                "server_time_ns": time.time_ns(),
            }).encode("utf-8")
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        # 2. Server Metadata & Hello Endpoint
        if path in ("/api/hello", "/api/meta", "/info"):
            client_ip = self.client_address[0]
            payload = json.dumps({
                "status": "online",
                "service": "proprietary-speedtest",
                "version": "1.0",
                "client_ip": client_ip,
                "server_time": time.time(),
            }).encode("utf-8")
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        # 3. High-Throughput Zero-Copy Synthetic Download Stream
        if path in ("/api/download", "/download"):
            # Parse requested size or default to 25 MB
            size = 25 * 1024 * 1024
            if "?" in self.path:
                try:
                    query = self.path.split("?", 1)[1]
                    for part in query.split("&"):
                        if part.startswith("size="):
                            size = int(part.split("=")[1])
                except Exception:
                    pass

            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(size))
            self.end_headers()

            sent = 0
            buf = STREAM_BUFFER
            buf_len = len(buf)
            try:
                while sent < size:
                    to_send = min(buf_len, size - sent)
                    self.wfile.write(buf[:to_send])
                    sent += to_send
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        # 4. Embedded Web Interface
        if path in ("/", "/index.html"):
            payload = WEB_INTERFACE_HTML.encode("utf-8")
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        # 404 for unknown paths
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        path = self.path.split("?")[0]

        # 5. Wire-Speed Upload Sink
        if path in ("/api/upload", "/upload"):
            content_length = int(self.headers.get("Content-Length", 0))
            bytes_read = 0
            t0 = time.time()

            try:
                while bytes_read < content_length:
                    to_read = min(CHUNK_SIZE, content_length - bytes_read)
                    chunk = self.rfile.read(to_read)
                    if not chunk:
                        break
                    bytes_read += len(chunk)
            except Exception:
                pass

            dt = max(0.0001, time.time() - t0)
            mbps = (bytes_read * 8) / (dt * 1e6)

            payload = json.dumps({
                "received_bytes": bytes_read,
                "elapsed_seconds": round(dt, 4),
                "server_measured_mbps": round(mbps, 2)
            }).encode("utf-8")

            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        self.send_response(404)
        self.end_headers()


# ---------------------------------------------------------------------------
# UDP LAN Auto-Discovery Responder
# ---------------------------------------------------------------------------
def run_discovery_responder(http_port, stop_event):
    """Listen on UDP 8081 for LAN client discovery broadcasts."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(1.0)
    try:
        sock.bind(("", 8081))
    except Exception:
        return

    while not stop_event.is_set():
        try:
            data, addr = sock.recvfrom(1024)
            if data == b"PROPRIETARY_SPEEDTEST_DISCOVER":
                resp = f"PROPRIETARY_SPEEDTEST_OFFER:{http_port}".encode("utf-8")
                sock.sendto(resp, addr)
        except socket.timeout:
            continue
        except Exception:
            break
    sock.close()


def get_local_ip():
    """Get the primary local IP address of this machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


# ---------------------------------------------------------------------------
# Server Main Entry Point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Proprietary High-Performance Speed Test Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Port to listen on (default: 8080)")
    args = parser.parse_args()

    server_address = (args.host, args.port)
    httpd = ThreadedHTTPServer(server_address, SpeedTestHandler)

    local_ip = get_local_ip()

    stop_event = threading.Event()
    discovery_thread = threading.Thread(target=run_discovery_responder, args=(args.port, stop_event), daemon=True)
    discovery_thread.start()

    print("\n" + "=" * 66)
    print("        PROPRIETARY SPEED TEST SERVER INITIALIZED")
    print("=" * 66)
    print(f"  Local Address:     http://localhost:{args.port}/")
    print(f"  Network Address:   http://{local_ip}:{args.port}/")
    print(f"  UDP Discovery:     Active on port 8081")
    print(f"  Web GUI Interface: http://{local_ip}:{args.port}/")
    print("=" * 66)
    print("  Endpoints:")
    print(f"   - GET  /api/ping     (Microsecond latency & jitter)")
    print(f"   - GET  /api/download (Zero-copy synthetic data streaming)")
    print(f"   - POST /api/upload   (Wire-speed upload sink)")
    print(f"   - GET  /api/hello    (Metadata & server health check)")
    print("=" * 66)
    print("Press Ctrl+C to terminate server.\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        stop_event.set()
        httpd.server_close()
        print("Server stopped.")


if __name__ == "__main__":
    main()
