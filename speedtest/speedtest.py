#!/usr/bin/env python3
"""
Internet Speed Test CLI (Braille Speedometer, Ping, Jitter, Download & Upload)
=============================================================================
A high-performance, zero-dependency Internet Speed Test utility featuring:
- Sub-pixel Braille dot-matrix speedometer dial with physics-damped rotating needle
- Dynamic auto-scaling scale (25, 50, 100, 250, 500, 1000 Mbps)
- Multi-threaded parallel download and upload engines
- High-precision latency (RTT) and jitter calculation
- High-resolution Unicode sub-block gauges and scrolling speed history graph
- Full JSON and simple text output modes for scripting and automation
"""

import sys
import os
import time
import math
import json
import signal
import argparse
import threading
import socket
import ssl
import re
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# SSL Context Helper
# ---------------------------------------------------------------------------
def get_ssl_context():
    """Create a permissive SSL context for speed test servers with custom/self-signed certs."""
    try:
        ctx = ssl._create_unverified_context()
    except AttributeError:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx

SSL_CTX = get_ssl_context()

# ---------------------------------------------------------------------------
# ANSI Color & Formatting Constants
# ---------------------------------------------------------------------------
CLR_RESET    = "\033[0m"
CLR_BOLD     = "\033[1m"
CLR_DIM      = "\033[2m"
CLEAR_SCREEN = "\033[2J\033[H"
CURSOR_HOME  = "\033[H"
HIDE_CURSOR  = "\033[?25l"
SHOW_CURSOR  = "\033[?25h"

USE_COLORS = True
H_BLOCKS = [" ", "▏", "▎", "▍", "▌", "▋", "▊", "▉", "█"]
V_BLOCKS = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]


def rgb(r, g, b, text):
    if not USE_COLORS:
        return text
    return f"\033[38;2;{int(r)};{int(g)};{int(b)}m{text}{CLR_RESET}"


def rgb_bold(r, g, b, text):
    if not USE_COLORS:
        return text
    return f"\033[38;2;{int(r)};{int(g)};{int(b)}m\033[1m{text}{CLR_RESET}"


def strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)


def pad_visible(text, target_width):
    vis_len = len(strip_ansi(text))
    if vis_len < target_width:
        return text + (" " * (target_width - vis_len))
    elif vis_len > target_width:
        clean = strip_ansi(text)
        return clean[:target_width]
    return text


def get_speed_rgb(val, max_val=100.0):
    """Interpolate RGB color: Cyan-Blue (low) -> Green -> Amber -> Bright Red (high)."""
    ratio = min(1.0, max(0.0, val / max_val))
    if ratio < 0.25:
        sub = ratio / 0.25
        r = int(0 + sub * 30)
        g = int(210 + sub * 30)
        b = int(240 - sub * 20)
    elif ratio < 0.60:
        sub = (ratio - 0.25) / 0.35
        r = int(30 + sub * 190)
        g = int(240 - sub * 10)
        b = int(220 - sub * 190)
    elif ratio < 0.85:
        sub = (ratio - 0.60) / 0.25
        r = int(220 + sub * 35)
        g = int(230 - sub * 90)
        b = int(30 - sub * 10)
    else:
        sub = (ratio - 0.85) / 0.15
        r = int(255)
        g = int(140 - sub * 100)
        b = int(20 + sub * 70)
    return (r, g, b)


# ---------------------------------------------------------------------------
# Braille Canvas & Dial Rendering
# ---------------------------------------------------------------------------
class BrailleCanvas:
    """Dot-matrix 2x4 sub-pixel canvas for high-resolution terminal graphics."""

    def __init__(self, cols, rows):
        self.cols = cols
        self.rows = rows
        self.width = cols * 2
        self.height = rows * 4
        self.grid = [[0 for _ in range(self.width)] for _ in range(self.height)]

    def clear(self):
        for r in range(self.height):
            for c in range(self.width):
                self.grid[r][c] = 0

    def set(self, x, y):
        ix, iy = int(round(x)), int(round(y))
        if 0 <= ix < self.width and 0 <= iy < self.height:
            self.grid[iy][ix] = 1

    def line(self, x0, y0, x1, y1):
        steps = int(max(abs(x1 - x0), abs(y1 - y0)) * 2)
        if steps == 0:
            self.set(x0, y0)
            return
        for s in range(steps + 1):
            t = s / steps
            self.set(x0 + t * (x1 - x0), y0 + t * (y1 - y0))

    def render(self):
        lut = [
            (0, 0, 1), (1, 0, 2), (2, 0, 4),
            (0, 1, 8), (1, 1, 16), (2, 1, 32),
            (3, 0, 64), (3, 1, 128)
        ]
        out_lines = []
        for r in range(self.rows):
            line_chars = []
            for c in range(self.cols):
                code = 0
                for dr, dc, bit in lut:
                    py = r * 4 + dr
                    px = c * 2 + dc
                    if py < self.height and px < self.width:
                        if self.grid[py][px]:
                            code |= bit
                line_chars.append(chr(0x2800 + code) if code else " ")
            out_lines.append("".join(line_chars))
        return out_lines


def render_speedometer_dial(speed_mbps, max_scale=100.0):
    """
    Render 72x32 sub-pixel Braille dial with 250-degree sweep and rotating needle.
    """
    sc = BrailleCanvas(36, 8)
    x0, y0 = 36, 30
    rx, ry = 31, 23

    # Draw circular outer arc
    for deg in range(215, -36, -2):
        rad = math.radians(deg)
        sc.set(x0 + math.cos(rad) * rx, y0 - math.sin(rad) * ry)

    # Draw radial tick marks
    ticks = [215, 165, 115, 90, 65, 15, -35]
    for t in ticks:
        rad = math.radians(t)
        sc.line(
            x0 + math.cos(rad) * (rx - 4),
            y0 - math.sin(rad) * (ry - 3),
            x0 + math.cos(rad) * rx,
            y0 - math.sin(rad) * ry
        )

    # Calculate rotating needle position
    ratio = min(1.0, max(0.0, speed_mbps / max_scale))
    deg = 215.0 - ratio * 250.0
    rad = math.radians(deg)
    needle_len_x = 27
    needle_len_y = 20
    sc.line(x0, y0, x0 + math.cos(rad) * needle_len_x, y0 - math.sin(rad) * needle_len_y)

    raw_lines = sc.render()
    out_lines = []
    r, g, b = get_speed_rgb(speed_mbps, max_scale)
    for l in raw_lines:
        line_colored = rgb(r, g, b, l)
        centered = " " * 14 + line_colored + " " * 14
        out_lines.append(centered)
    return out_lines


def render_subblock_bar(val, max_val=100.0, width=46):
    """Render 8th-step sub-character progress bar."""
    ratio = min(1.0, max(0.0, val / max_val))
    total_eighths = int(round(ratio * (width * 8)))
    full_blocks = total_eighths // 8
    rem = total_eighths % 8
    sub_char = H_BLOCKS[rem] if rem > 0 else ""
    empty_blocks = max(0, width - full_blocks - (1 if rem > 0 else 0))

    r, g, b = get_speed_rgb(val, max_val)
    active_str = rgb_bold(r, g, b, ("█" * full_blocks) + sub_char)
    empty_str = rgb(60, 65, 75, "░" * empty_blocks)
    return active_str + empty_str


def render_oscilloscope_wave(history, max_val=100.0, width=46):
    """Render scrolling speed waveform with vertical blocks."""
    padded = history[-width:] if len(history) >= width else [0.0] * (width - len(history)) + history
    chars = []
    for val in padded:
        ratio = min(1.0, max(0.0, val / max_val))
        idx = int(round(ratio * 8))
        idx = max(0, min(8, idx))
        r, g, b = get_speed_rgb(val, max_val)
        chars.append(rgb_bold(r, g, b, V_BLOCKS[idx]))
    return "".join(chars)


# ---------------------------------------------------------------------------
# Scale Auto-Adjustment
# ---------------------------------------------------------------------------
SCALES = [25.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2500.0]


def get_appropriate_scale(current_val, current_scale):
    """Smoothly upscale when values exceed 85% of current max scale."""
    if current_val > current_scale * 0.85:
        for s in SCALES:
            if s > current_val * 1.15:
                return s
        return SCALES[-1]
    return current_scale


# ---------------------------------------------------------------------------
# Speed Test Engine
# ---------------------------------------------------------------------------
class SpeedTestEngine:
    def __init__(self, duration=8, threads=4, force_server_id=None, test_download=True, test_upload=True):
        self.duration = duration
        self.threads = threads
        self.force_server_id = force_server_id
        self.test_download = test_download
        self.test_upload = test_upload

        self.client_info = {
            "ip": "Unknown",
            "isp": "Unknown",
            "city": "",
            "country": "Unknown",
            "lat": 0.0,
            "lon": 0.0,
        }
        self.server_info = {}
        self.servers_list = []

        # Telemetry
        self.ping_ms = 0.0
        self.ping_min = 0.0
        self.ping_max = 0.0
        self.jitter_ms = 0.0
        self.all_pings = []

        self.current_speed_mbps = 0.0
        self.peak_speed_mbps = 0.0
        self.avg_download_mbps = 0.0
        self.avg_upload_mbps = 0.0

        self.download_bytes = 0
        self.upload_bytes = 0

        self.speed_history = []
        self.current_phase = "IDLE"  # DISCOVERY, PING, DOWNLOAD, UPLOAD, DONE
        self.phase_progress = 0.0    # 0.0 to 1.0

        self.lock = threading.Lock()
        self.stop_signal = False

    def fetch_client_and_servers(self):
        """Fetch client configuration and closest servers from Speedtest.net."""
        self.current_phase = "DISCOVERY"

        # 1. Client info from speedtest-config.php
        try:
            req = urllib.request.Request(
                "https://www.speedtest.net/speedtest-config.php",
                headers={"User-Agent": "curl/8.19.0", "Accept": "*/*"}
            )
            with urllib.request.urlopen(req, timeout=6) as res:
                root = ET.fromstring(res.read())
                client = root.find("client")
                if client is not None:
                    self.client_info["ip"] = client.attrib.get("ip", "Unknown")
                    self.client_info["isp"] = client.attrib.get("isp", "Unknown")
                    self.client_info["country"] = client.attrib.get("country", "")
                    self.client_info["lat"] = float(client.attrib.get("lat", 0.0))
                    self.client_info["lon"] = float(client.attrib.get("lon", 0.0))
        except Exception:
            pass

        # 2. Server list from api/js/servers
        try:
            req = urllib.request.Request(
                "https://www.speedtest.net/api/js/servers?engine=js",
                headers={"User-Agent": "curl/8.19.0", "Accept": "*/*"}
            )
            with urllib.request.urlopen(req, timeout=6) as res:
                self.servers_list = json.loads(res.read().decode())
        except Exception:
            self.servers_list = []

        # If servers_list is empty, fallback to reliable default servers
        if not self.servers_list:
            self.servers_list = [
                {
                    "id": "fallback-1",
                    "sponsor": "Global CDN Edge",
                    "name": "Global Anycast",
                    "country": "Global",
                    "host": "speedtest.tele2.net",
                    "url": "http://speedtest.tele2.net/upload.cgi",
                    "distance": 10,
                }
            ]

        # Select target server
        selected = None
        if self.force_server_id:
            for s in self.servers_list:
                if str(s.get("id")) == str(self.force_server_id):
                    selected = s
                    break

        if not selected and self.servers_list:
            candidates = self.servers_list[:5]
            best_rtt = float("inf")
            for cand in candidates:
                urls = self._get_server_test_urls(cand, "latency")
                for u in urls:
                    try:
                        t0 = time.time()
                        req = urllib.request.Request(u, headers={"User-Agent": "curl/8.19.0"})
                        with urllib.request.urlopen(req, timeout=2.5, context=SSL_CTX) as r:
                            r.read()
                        rtt = (time.time() - t0) * 1000.0
                        cand["ping_test"] = rtt
                        if rtt < best_rtt:
                            best_rtt = rtt
                            selected = cand
                        break
                    except Exception:
                        continue

        if not selected:
            selected = self.servers_list[0]

        self.server_info = selected
        return selected

    def _get_server_test_urls(self, server, action="latency"):
        """Generate HTTPS and HTTP candidate URLs for latency, download, or upload."""
        host = server.get("host")
        raw_url = server.get("url", "")
        base_dir = "/speedtest/"

        urls = []
        if host:
            if action == "latency":
                urls.append(f"https://{host}{base_dir}latency.txt")
                urls.append(f"http://{host}{base_dir}latency.txt")
            elif action == "upload":
                urls.append(f"https://{host}{base_dir}upload.php")
                urls.append(f"http://{host}{base_dir}upload.php")
            elif action == "download":
                for sz in ["random1500x1500.jpg", "random2500x2500.jpg", "random3500x3500.jpg"]:
                    urls.append(f"https://{host}{base_dir}{sz}")
                    urls.append(f"http://{host}{base_dir}{sz}")
        elif raw_url:
            base = raw_url.rsplit("/", 1)[0]
            if action == "latency":
                urls.append(f"{base}/latency.txt")
            elif action == "upload":
                urls.append(raw_url)
            elif action == "download":
                for sz in ["random1500x1500.jpg", "random2500x2500.jpg"]:
                    urls.append(f"{base}/{sz}")
        return urls

    def run_ping_test(self, num_pings=8):
        """Run latency (RTT) and jitter measurement."""
        self.current_phase = "PING"
        candidate_urls = self._get_server_test_urls(self.server_info, "latency")

        active_url = None
        for u in candidate_urls:
            try:
                req = urllib.request.Request(u, headers={"User-Agent": "curl/8.19.0"})
                with urllib.request.urlopen(req, timeout=2.5, context=SSL_CTX) as res:
                    res.read()
                active_url = u
                break
            except Exception:
                continue

        if not active_url and candidate_urls:
            active_url = candidate_urls[0]

        times = []
        for i in range(num_pings):
            if self.stop_signal:
                break
            try:
                t0 = time.time()
                req = urllib.request.Request(active_url, headers={"User-Agent": "curl/8.19.0"})
                with urllib.request.urlopen(req, timeout=3.0, context=SSL_CTX) as res:
                    res.read()
                rtt = (time.time() - t0) * 1000.0
                times.append(rtt)
            except Exception:
                pass
            with self.lock:
                self.phase_progress = (i + 1) / float(num_pings)
                if times:
                    self.ping_ms = times[-1]
            time.sleep(0.08)

        if not times:
            times = [99.0]

        self.all_pings = times
        self.ping_min = min(times)
        self.ping_max = max(times)
        self.ping_ms = sum(times) / len(times)

        # RFC 3550 / Ookla jitter calculation
        if len(times) > 1:
            diffs = [abs(times[i] - times[i - 1]) for i in range(1, len(times))]
            self.jitter_ms = sum(diffs) / len(diffs)
        else:
            self.jitter_ms = 0.0

    def run_download_test(self):
        """Multi-threaded parallel download test."""
        if not self.test_download:
            return

        self.current_phase = "DOWNLOAD"
        self.speed_history = []
        candidate_urls = self._get_server_test_urls(self.server_info, "download")

        # Pick working scheme
        working_urls = []
        for u in candidate_urls[:3]:
            try:
                req = urllib.request.Request(u)
                with urllib.request.urlopen(req, timeout=3.0, context=SSL_CTX) as res:
                    chunk = res.read(1024)
                    if chunk:
                        working_urls.append(u)
            except Exception:
                continue

        if not working_urls:
            working_urls = candidate_urls[:3]

        total_bytes_transferred = 0
        running_download = True
        bytes_lock = threading.Lock()

        def worker(thread_idx):
            nonlocal total_bytes_transferred
            url = working_urls[thread_idx % len(working_urls)]
            while running_download and not self.stop_signal:
                try:
                    req = urllib.request.Request(url)
                    with urllib.request.urlopen(req, timeout=4.0, context=SSL_CTX) as res:
                        while running_download and not self.stop_signal:
                            chunk = res.read(65536)
                            if not chunk:
                                break
                            with bytes_lock:
                                total_bytes_transferred += len(chunk)
                except Exception:
                    time.sleep(0.1)

        threads_list = []
        for i in range(self.threads):
            t = threading.Thread(target=worker, args=(i,), daemon=True)
            threads_list.append(t)
            t.start()

        start_time = time.time()
        last_bytes = 0
        last_time = start_time

        while time.time() - start_time < self.duration and not self.stop_signal:
            time.sleep(0.1)
            now = time.time()
            elapsed_total = now - start_time
            dt = now - last_time

            with bytes_lock:
                current_bytes = total_bytes_transferred

            d_bytes = current_bytes - last_bytes
            instant_mbps = (d_bytes * 8) / (dt * 1e6) if dt > 0 else 0.0

            last_bytes = current_bytes
            last_time = now

            with self.lock:
                self.phase_progress = min(1.0, elapsed_total / float(self.duration))
                self.current_speed_mbps = instant_mbps
                self.download_bytes = current_bytes
                self.speed_history.append(instant_mbps)
                if instant_mbps > self.peak_speed_mbps:
                    self.peak_speed_mbps = instant_mbps

        running_download = False
        for t in threads_list:
            t.join(timeout=0.5)

        total_elapsed = max(0.1, time.time() - start_time)
        with self.lock:
            self.download_bytes = total_bytes_transferred
            self.avg_download_mbps = (total_bytes_transferred * 8) / (total_elapsed * 1e6)
            self.current_speed_mbps = self.avg_download_mbps

    def run_upload_test(self):
        """Multi-threaded parallel upload test."""
        if not self.test_upload:
            return

        self.current_phase = "UPLOAD"
        self.speed_history = []
        candidate_urls = self._get_server_test_urls(self.server_info, "upload")

        active_upload_url = None
        probe_chunk = b"content1=" + (b"0" * (8 * 1024))  # 8KB probe for rapid health check
        payload_chunk = b"content1=" + (b"0" * (64 * 1024))  # 64KB chunks for smooth sampling

        for u in candidate_urls:
            try:
                req = urllib.request.Request(u, data=probe_chunk, method="POST")
                with urllib.request.urlopen(req, timeout=2.5, context=SSL_CTX) as res:
                    res.read()
                active_upload_url = u
                break
            except Exception:
                continue

        if not active_upload_url and candidate_urls:
            active_upload_url = candidate_urls[0]

        total_bytes_uploaded = 0
        running_upload = True
        bytes_lock = threading.Lock()

        def worker():
            nonlocal total_bytes_uploaded
            chunk_to_send = payload_chunk
            while running_upload and not self.stop_signal:
                try:
                    req = urllib.request.Request(active_upload_url, data=chunk_to_send, method="POST")
                    with urllib.request.urlopen(req, timeout=4.0, context=SSL_CTX) as res:
                        res.read()
                        with bytes_lock:
                            total_bytes_uploaded += len(chunk_to_send)
                except Exception:
                    time.sleep(0.08)

        # Scale thread count for upload: 2-4 threads
        upload_threads = min(self.threads, 3)
        threads_list = []
        for _ in range(upload_threads):
            t = threading.Thread(target=worker, daemon=True)
            threads_list.append(t)
            t.start()

        start_time = time.time()
        last_bytes = 0
        last_time = start_time

        while time.time() - start_time < self.duration and not self.stop_signal:
            time.sleep(0.1)
            now = time.time()
            elapsed_total = now - start_time
            dt = now - last_time

            with bytes_lock:
                current_bytes = total_bytes_uploaded

            d_bytes = current_bytes - last_bytes
            instant_mbps = (d_bytes * 8) / (dt * 1e6) if dt > 0 else 0.0

            last_bytes = current_bytes
            last_time = now

            with self.lock:
                self.phase_progress = min(1.0, elapsed_total / float(self.duration))
                self.current_speed_mbps = instant_mbps
                self.upload_bytes = current_bytes
                self.speed_history.append(instant_mbps)

        running_upload = False
        for t in threads_list:
            t.join(timeout=0.5)

        total_elapsed = max(0.1, time.time() - start_time)
        with self.lock:
            self.upload_bytes = total_bytes_uploaded
            self.avg_upload_mbps = (total_bytes_uploaded * 8) / (total_elapsed * 1e6)
            self.current_speed_mbps = self.avg_upload_mbps


# ---------------------------------------------------------------------------
# Rating & Quality Evaluation
# ---------------------------------------------------------------------------
def compute_quality_rating(dl_mbps, ul_mbps, ping_ms, jitter_ms):
    """Calculate internet connection quality score and human description."""
    score = 100

    # Latency penalty
    if ping_ms > 150:
        score -= 30
    elif ping_ms > 80:
        score -= 15
    elif ping_ms > 40:
        score -= 5

    # Jitter penalty
    if jitter_ms > 40:
        score -= 25
    elif jitter_ms > 15:
        score -= 10
    elif jitter_ms > 5:
        score -= 3

    # Download throughput weight
    if dl_mbps < 5:
        score -= 35
    elif dl_mbps < 25:
        score -= 15
    elif dl_mbps < 50:
        score -= 5

    score = max(10, min(100, score))
    if score >= 90:
        return ("A+", "Ultra Broadband (Flawless Gaming, 4K/8K, Low-Latency)", (0, 240, 140))
    elif score >= 80:
        return ("A", "High-Speed Broadband (Great for Video Calls & Gaming)", (80, 220, 100))
    elif score >= 68:
        return ("B", "Standard Broadband (Good for HD Streaming & Browsing)", (240, 200, 40))
    elif score >= 50:
        return ("C", "Moderate Connection (May buffer on high-bandwidth tasks)", (240, 130, 40))
    else:
        return ("D", "Low Bandwidth / High Latency (Experiencing bottlenecks)", (240, 60, 60))


# ---------------------------------------------------------------------------
# UI Terminal Display Loop
# ---------------------------------------------------------------------------
def run_interactive_display(engine, target_fps=60, use_bytes=False):
    """
    Clock-paced high-FPS display loop with physics spring-damped needle kinematics.
    """
    sys.stdout.write(HIDE_CURSOR)
    sys.stdout.write(CLEAR_SCREEN)
    sys.stdout.flush()

    needle_pos = 0.0
    needle_vel = 0.0
    max_scale = 100.0
    dt_frame = 1.0 / target_fps
    running = True

    def sig_handler(sig, frame):
        nonlocal running
        running = False
        engine.stop_signal = True

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    test_thread = threading.Thread(target=_execute_speedtest_phases, args=(engine,), daemon=True)
    test_thread.start()

    try:
        while running and engine.current_phase != "DONE":
            frame_start = time.time()

            with engine.lock:
                target_speed = engine.current_speed_mbps
                phase = engine.current_phase
                progress = engine.phase_progress
                ping = engine.ping_ms
                jitter = engine.jitter_ms
                dl_avg = engine.avg_download_mbps
                ul_avg = engine.avg_upload_mbps
                dl_bytes = engine.download_bytes
                ul_bytes = engine.upload_bytes
                history = list(engine.speed_history)
                client = dict(engine.client_info)
                server = dict(engine.server_info)

            # Auto-scale dial
            max_scale = get_appropriate_scale(target_speed, max_scale)

            # Physics spring equation (critically damped needle)
            omega = 16.0
            zeta = 0.85
            accel = (omega ** 2) * (target_speed - needle_pos) - 2.0 * zeta * omega * needle_vel
            needle_vel += accel * dt_frame
            needle_pos += needle_vel * dt_frame
            needle_pos = max(0.0, needle_pos)

            # Render frame lines
            frame_lines = []
            frame_lines.append(CURSOR_HOME)
            frame_lines.append(rgb_bold(0, 200, 255, "  ╔════════════════════════════════════════════════════════════════╗"))
            frame_lines.append(rgb_bold(0, 200, 255, "  ║                INTERNET SPEED TEST TERMINAL                   ║"))
            frame_lines.append(rgb_bold(0, 200, 255, "  ╚════════════════════════════════════════════════════════════════╝"))
            frame_lines.append("")

            # Client & Server banner
            isp_str = f"Client: {client.get('isp', 'Detecting...')} ({client.get('ip', '')})"
            srv_str = f"Server: {server.get('sponsor', 'Selecting...')} - {server.get('name', '')} [{server.get('country', '')}]"
            frame_lines.append(pad_visible(f"  {rgb(140, 180, 220, isp_str)}", 66))
            frame_lines.append(pad_visible(f"  {rgb(160, 200, 140, srv_str)}", 66))
            frame_lines.append("  " + "─" * 64)

            # Dial Speedometer
            dial_lines = render_speedometer_dial(needle_pos, max_scale)
            frame_lines.extend(dial_lines)

            # Current Speed readout & Phase
            unit = "MB/s" if use_bytes else "Mbps"
            display_val = (needle_pos / 8.0) if use_bytes else needle_pos
            val_str = f"{display_val:6.1f} {unit}"
            r, g, b = get_speed_rgb(needle_pos, max_scale)

            phase_tag = f"[{phase}]"
            if phase == "DISCOVERY":
                phase_colored = rgb_bold(100, 200, 255, f"● {phase_tag} Probing closest server...")
            elif phase == "PING":
                phase_colored = rgb_bold(255, 200, 60, f"● {phase_tag} Testing Ping & Jitter...")
            elif phase == "DOWNLOAD":
                phase_colored = rgb_bold(0, 240, 140, f"▼ {phase_tag} Testing Download Speed...")
            elif phase == "UPLOAD":
                phase_colored = rgb_bold(180, 120, 255, f"▲ {phase_tag} Testing Upload Speed...")
            else:
                phase_colored = rgb_bold(200, 200, 200, f"✓ {phase_tag} Complete")

            center_readout = f"Speed: {rgb_bold(r, g, b, val_str)}   (Scale: 0-{int(max_scale)} Mbps)"
            frame_lines.append(pad_visible(f"  {center_readout}", 66))
            frame_lines.append(pad_visible(f"  Status: {phase_colored}", 66))
            frame_lines.append("")

            # Sub-block progress bar
            bar_line = render_subblock_bar(needle_pos, max_scale, width=54)
            pct_str = f"{int(progress * 100):3d}%"
            frame_lines.append(f"  {bar_line} {rgb_bold(160, 180, 200, pct_str)}")

            # Real-time scrolling speed graph
            wave_line = render_oscilloscope_wave(history, max_scale, width=54)
            frame_lines.append(f"  {wave_line} {rgb(120, 130, 150, 'Live')}")
            frame_lines.append("  " + "─" * 64)

            # Live Metrics Card
            dl_disp = (dl_avg / 8.0) if use_bytes else dl_avg
            ul_disp = (ul_avg / 8.0) if use_bytes else ul_avg
            m1 = f"Ping: {rgb_bold(255, 220, 80, f'{ping:.1f} ms')}  Jitter: {rgb_bold(255, 180, 60, f'{jitter:.1f} ms')}"
            m2 = f"DL: {rgb_bold(0, 240, 140, f'{dl_disp:.1f} {unit}')} ({dl_bytes / 1e6:.1f} MB)"
            m3 = f"UL: {rgb_bold(180, 120, 255, f'{ul_disp:.1f} {unit}')} ({ul_bytes / 1e6:.1f} MB)"
            frame_lines.append(f"  {pad_visible(m1, 30)} {pad_visible(m2, 34)}")
            frame_lines.append(f"  {pad_visible(m3, 64)}")
            frame_lines.append(rgb_bold(0, 200, 255, "  ╚════════════════════════════════════════════════════════════════╝"))

            # Write buffer in a single atomic call
            sys.stdout.write("\n".join(frame_lines) + "\n")
            sys.stdout.flush()

            # Pace frame
            dt = time.time() - frame_start
            sleep_time = max(0.001, dt_frame - dt)
            time.sleep(sleep_time)

    finally:
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.flush()

    test_thread.join(timeout=2.0)
    print_final_summary(engine, use_bytes=use_bytes)


def _execute_speedtest_phases(engine):
    """Background worker driving the speed test phases sequentially."""
    try:
        engine.fetch_client_and_servers()
        if not engine.stop_signal:
            engine.run_ping_test()
        if not engine.stop_signal and engine.test_download:
            engine.run_download_test()
        if not engine.stop_signal and engine.test_upload:
            engine.run_upload_test()
    except Exception:
        pass
    finally:
        engine.current_phase = "DONE"


def print_final_summary(engine, use_bytes=False):
    """Print the final clean Unicode box-drawing summary card."""
    unit = "MB/s" if use_bytes else "Mbps"
    dl = (engine.avg_download_mbps / 8.0) if use_bytes else engine.avg_download_mbps
    ul = (engine.avg_upload_mbps / 8.0) if use_bytes else engine.avg_upload_mbps

    grade, grade_desc, grade_rgb = compute_quality_rating(
        engine.avg_download_mbps, engine.avg_upload_mbps, engine.ping_ms, engine.jitter_ms
    )

    total_mb = (engine.download_bytes + engine.upload_bytes) / 1e6
    client_isp = engine.client_info.get("isp", "Unknown")
    client_ip = engine.client_info.get("ip", "")
    server_sponsor = engine.server_info.get("sponsor", "Unknown")
    server_name = engine.server_info.get("name", "")
    server_country = engine.server_info.get("country", "")
    server_dist = engine.server_info.get("distance", 0)

    print("\n")
    print(rgb_bold(0, 200, 255, "  ╔════════════════════════════════════════════════════════════════╗"))
    print(rgb_bold(0, 200, 255, "  ║                   SPEED TEST RESULT SUMMARY                    ║"))
    print(rgb_bold(0, 200, 255, "  ╠════════════════════════════════════════════════════════════════╣"))
    print(f"  ║ {pad_visible(f'ISP / Client:   {client_isp} ({client_ip})', 62)} ║")
    print(f"  ║ {pad_visible(f'Server:         {server_sponsor} - {server_name} [{server_country}]', 62)} ║")
    print(f"  ║ {pad_visible(f'Distance:       {server_dist} km', 62)} ║")
    print(rgb_bold(0, 200, 255, "  ╟────────────────────────────────────────────────────────────────╢"))
    rtt_str = rgb_bold(255, 220, 80, f"{engine.ping_ms:.2f} ms")
    print(f"  ║ {pad_visible(f'Latency (RTT):  {rtt_str} (Min: {engine.ping_min:.1f}ms, Max: {engine.ping_max:.1f}ms)', 62)} ║")
    jit_str = rgb_bold(255, 180, 60, f"{engine.jitter_ms:.2f} ms")
    print(f"  ║ {pad_visible(f'Jitter:         {jit_str}', 62)} ║")
    dl_str = rgb_bold(0, 240, 140, f"{dl:.2f} {unit}")
    print(f"  ║ {pad_visible(f'Download:       {dl_str} ({engine.avg_download_mbps:.2f} Mbps, {engine.download_bytes / 1e6:.2f} MB)', 62)} ║")
    ul_str = rgb_bold(180, 120, 255, f"{ul:.2f} {unit}")
    print(f"  ║ {pad_visible(f'Upload:         {ul_str} ({engine.avg_upload_mbps:.2f} Mbps, {engine.upload_bytes / 1e6:.2f} MB)', 62)} ║")
    print(f"  ║ {pad_visible(f'Total Data:     {total_mb:.2f} MB transferred', 62)} ║")
    print(rgb_bold(0, 200, 255, "  ╟────────────────────────────────────────────────────────────────╢"))
    gr_r, gr_g, gr_b = grade_rgb
    grade_tag = rgb_bold(gr_r, gr_g, gr_b, f'[{grade}]')
    print(f"  ║ {pad_visible(f'Quality Grade:  {grade_tag} {grade_desc}', 62)} ║")
    print(rgb_bold(0, 200, 255, "  ╚════════════════════════════════════════════════════════════════╝\n"))


# ---------------------------------------------------------------------------
# Simple & JSON Non-Interactive Output Modes
# ---------------------------------------------------------------------------
def run_simple_mode(engine, use_bytes=False):
    """Simple plain-text output suitable for logging, cron, or scripting."""
    print("Initializing Speed Test...")
    engine.fetch_client_and_servers()
    print(f"Client: {engine.client_info.get('isp', 'Unknown')} ({engine.client_info.get('ip', '')})")
    print(f"Server: {engine.server_info.get('sponsor', 'Unknown')} ({engine.server_info.get('name', '')})")

    print("Measuring ping and jitter...")
    engine.run_ping_test()
    print(f"Latency: {engine.ping_ms:.2f} ms (Jitter: {engine.jitter_ms:.2f} ms)")

    unit = "MB/s" if use_bytes else "Mbps"
    if engine.test_download:
        print("Testing download speed...")
        engine.run_download_test()
        dl = (engine.avg_download_mbps / 8.0) if use_bytes else engine.avg_download_mbps
        print(f"Download: {dl:.2f} {unit}")

    if engine.test_upload:
        print("Testing upload speed...")
        engine.run_upload_test()
        ul = (engine.avg_upload_mbps / 8.0) if use_bytes else engine.avg_upload_mbps
        print(f"Upload: {ul:.2f} {unit}")

    grade, desc, _ = compute_quality_rating(
        engine.avg_download_mbps, engine.avg_upload_mbps, engine.ping_ms, engine.jitter_ms
    )
    print(f"Grade: [{grade}] {desc}")


def run_json_mode(engine):
    """Output full test data in JSON format."""
    engine.fetch_client_and_servers()
    engine.run_ping_test()
    if engine.test_download:
        engine.run_download_test()
    if engine.test_upload:
        engine.run_upload_test()

    grade, desc, _ = compute_quality_rating(
        engine.avg_download_mbps, engine.avg_upload_mbps, engine.ping_ms, engine.jitter_ms
    )

    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "client": engine.client_info,
        "server": {
            "id": engine.server_info.get("id"),
            "sponsor": engine.server_info.get("sponsor"),
            "name": engine.server_info.get("name"),
            "country": engine.server_info.get("country"),
            "distance_km": engine.server_info.get("distance"),
            "host": engine.server_info.get("host"),
        },
        "ping": {
            "avg_ms": round(engine.ping_ms, 2),
            "min_ms": round(engine.ping_min, 2),
            "max_ms": round(engine.ping_max, 2),
            "jitter_ms": round(engine.jitter_ms, 2),
            "samples": [round(x, 2) for x in engine.all_pings],
        },
        "download": {
            "mbps": round(engine.avg_download_mbps, 2),
            "mb_per_sec": round(engine.avg_download_mbps / 8.0, 2),
            "bytes": engine.download_bytes,
        },
        "upload": {
            "mbps": round(engine.avg_upload_mbps, 2),
            "mb_per_sec": round(engine.avg_upload_mbps / 8.0, 2),
            "bytes": engine.upload_bytes,
        },
        "quality": {
            "grade": grade,
            "description": desc,
        }
    }
    print(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# CLI Argument Parser & Entry Point
# ---------------------------------------------------------------------------
def main():
    global USE_COLORS

    parser = argparse.ArgumentParser(
        description="High-Precision Internet Speed Test CLI with Braille Speedometer Dial"
    )
    parser.add_argument("-s", "--simple", action="store_true", help="Output simple plain text (no animations)")
    parser.add_argument("-j", "--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--bytes", action="store_true", help="Display speeds in MegaBytes/sec (MB/s) instead of Mbps")
    parser.add_argument("-d", "--duration", type=int, default=8, help="Test duration in seconds per phase (default: 8)")
    parser.add_argument("-t", "--threads", type=int, default=4, help="Parallel connection threads (default: 4)")
    parser.add_argument("--server", type=str, default=None, help="Force testing against a specific server ID")
    parser.add_argument("--list-servers", action="store_true", help="List closest available servers and exit")
    parser.add_argument("--no-download", action="store_true", help="Skip download test")
    parser.add_argument("--no-upload", action="store_true", help="Skip upload test")
    parser.add_argument("-f", "--fps", type=int, default=60, help="Display frame rate (default: 60)")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI color output")

    args = parser.parse_args()

    if args.no_color or not sys.stdout.isatty():
        USE_COLORS = False

    engine = SpeedTestEngine(
        duration=args.duration,
        threads=args.threads,
        force_server_id=args.server,
        test_download=not args.no_download,
        test_upload=not args.no_upload
    )

    if args.list_servers:
        print("Discovering closest servers...")
        engine.fetch_client_and_servers()
        print(f"\nClient Location: {engine.client_info.get('isp', '')} [{engine.client_info.get('country', '')}]\n")
        print(f"{'ID':<10} {'Distance':<12} {'Sponsor':<30} {'City/Country':<25}")
        print("-" * 80)
        for s in engine.servers_list[:15]:
            dist_str = f"{s.get('distance', 0)} km"
            print(f"{str(s.get('id')):<10} {dist_str:<12} {s.get('sponsor', ''):<30} {s.get('name', '') + ', ' + s.get('country', ''):<25}")
        sys.exit(0)

    if args.json:
        USE_COLORS = False
        run_json_mode(engine)
    elif args.simple:
        run_simple_mode(engine, use_bytes=args.bytes)
    else:
        run_interactive_display(engine, target_fps=args.fps, use_bytes=args.bytes)


if __name__ == "__main__":
    main()
