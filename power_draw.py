#!/usr/bin/env python3
"""
Android Power Meter (Max 30W, 100ms Sampling, 60 FPS Display)
=============================================================
Real-time power monitoring with 100ms hardware sampling and 60 FPS display:
- Braille dot-matrix speedometer dial with physics-damped needle (0 - 30W)
- High-resolution sub-block power gauge
- Scrolling power history graph
- Power flow direction indicator
"""

import sys
import os
import time
import subprocess
import argparse
import json
import signal
import re
import math
import threading
from datetime import datetime

# ANSI Color Helpers
CLR_RESET    = "\033[0m"
CLR_BOLD     = "\033[1m"
CLR_DIM      = "\033[2m"
CLEAR_SCREEN = "\033[2J\033[H"
CURSOR_HOME  = "\033[H"
HIDE_CURSOR  = "\033[?25l"
SHOW_CURSOR  = "\033[?25h"

USE_COLORS = True


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


def get_wattage_rgb(val, max_w=30.0):
    """Interpolate RGB color: Green (low) -> Yellow (medium) -> Red (high)."""
    ratio = min(1.0, max(0.0, val / max_w))
    if ratio < 0.30:  # Low power: Cyan-Green
        sub = ratio / 0.30
        r = int(0 + sub * 60)
        g = int(220 + sub * 35)
        b = int(240 - sub * 180)
    elif ratio < 0.70:  # Medium power: Green to Yellow-Amber
        sub = (ratio - 0.30) / 0.40
        r = int(60 + sub * 195)
        g = int(255 - sub * 55)
        b = 30
    else:  # High power: Amber to Red
        sub = (ratio - 0.70) / 0.30
        r = 255
        g = int(200 * (1.0 - sub))
        b = int(30 + sub * 50)
    return (r, g, b)


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


class FastBinderReader:
    """Persistent shell process for low-latency Binder queries."""

    def __init__(self):
        self.proc = None
        self._spawn()

    def _spawn(self):
        try:
            if self.proc:
                try:
                    self.proc.stdin.close()
                except Exception:
                    pass
                self.proc.kill()
        except Exception:
            pass
        try:
            self.proc = subprocess.Popen(
                ["/system/bin/sh"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
        except Exception:
            self.proc = None

    def query(self, prop_id):
        if not self.proc or self.proc.poll() is not None:
            self._spawn()
        if not self.proc:
            return None

        token = f"__END_{prop_id}__"
        cmd = f"/system/bin/service call batteryproperties 1 i32 {prop_id}; echo {token}\n"
        try:
            self.proc.stdin.write(cmd)
            self.proc.stdin.flush()
            hex_words = []
            while True:
                line = self.proc.stdout.readline()
                if not line or token in line:
                    break
                line = line.strip()
                if line.startswith("0x"):
                    parts = line.split(":")[1].split("'")[0].split()
                    hex_words.extend(parts)

            if len(hex_words) >= 5:
                low = int(hex_words[3], 16)
                high = int(hex_words[4], 16)
                val = (high << 32) | low
                if val >= (1 << 63):
                    val -= (1 << 64)
                return val
        except Exception:
            self._spawn()
        return None

    def close(self):
        try:
            if self.proc:
                try:
                    self.proc.stdin.close()
                except Exception:
                    pass
                self.proc.kill()
                self.proc = None
        except Exception:
            pass


class PowerReaderEngine:
    """Background sampling engine reading hardware at 100ms intervals."""

    def __init__(self, override_voltage=None):
        self.override_voltage = override_voltage
        self.binder = FastBinderReader()
        self.capacity = 50
        self.charge_mah = 3500
        self.status = "UNKNOWN"
        self.is_charging = False
        self.voltage = 4.0
        self.current_ma = 0.0
        self.active_wattage = 0.0
        self.battery_net_wattage = 0.0
        self.total_input_wattage = 0.0
        self.target_wattage = 0.0

        self.running = True
        self.tick_count = 0
        self.lock = threading.Lock()
        self.worker_thread = threading.Thread(target=self._sample_loop, daemon=True)
        self.worker_thread.start()

    def estimate_voltage(self, percentage, is_charging):
        p = max(0.0, min(100.0, float(percentage)))
        if p >= 90:
            ocv = 4.25 + (p - 90) * 0.017
        elif p >= 70:
            ocv = 4.10 + (p - 70) * 0.0075
        elif p >= 50:
            ocv = 3.95 + (p - 50) * 0.0075
        elif p >= 30:
            ocv = 3.82 + (p - 30) * 0.0065
        elif p >= 15:
            ocv = 3.73 + (p - 15) * 0.0060
        else:
            ocv = 3.50 + p * 0.0153

        if is_charging:
            ocv += 0.08
        return round(ocv, 3)

    def _sample_loop(self):
        """100ms hardware polling loop."""
        while self.running:
            t0 = time.time()

            # Update capacity and status once every 10 samples (1s)
            if self.tick_count % 10 == 0 or self.tick_count == 0:
                cap = self.binder.query(4)
                if cap is not None:
                    self.capacity = int(cap)

                stat_code = self.binder.query(6)
                if stat_code is not None:
                    stat_map = {1: "UNKNOWN", 2: "CHARGING", 3: "DISCHARGING", 4: "NOT_CHARGING", 5: "FULL"}
                    self.status = stat_map.get(stat_code, "UNKNOWN")

                uah = self.binder.query(1)
                if uah is not None and uah > 0:
                    self.charge_mah = uah / 1000.0

            # Instantaneous current sampled every 100ms
            curr_ua = self.binder.query(2)
            curr_ma = (curr_ua / 1000.0) if curr_ua is not None else 0.0

            is_charging = (self.status == "CHARGING") or (curr_ma > 60)
            if is_charging and self.status != "CHARGING":
                self.status = "CHARGING"
            elif not is_charging and self.status == "CHARGING":
                self.status = "DISCHARGING"

            if self.override_voltage:
                volt = self.override_voltage
            else:
                volt = self.estimate_voltage(self.capacity, is_charging)

            curr_amps = abs(curr_ma) / 1000.0
            act_w = round(volt * curr_amps, 2)

            if is_charging:
                batt_w = act_w
                sys_w = round(volt * 0.45, 2)
                total_w = round((batt_w + sys_w) / 0.92, 2)
                target_w = total_w
            else:
                batt_w = 0.0
                sys_w = act_w
                total_w = 0.0
                target_w = act_w

            with self.lock:
                self.voltage = volt
                self.current_ma = curr_ma
                self.is_charging = is_charging
                self.active_wattage = act_w
                self.battery_net_wattage = batt_w
                self.total_input_wattage = total_w
                self.target_wattage = target_w
                self.tick_count += 1

            dt = time.time() - t0
            time.sleep(max(0.01, 0.1 - dt))

    def read_once(self):
        """Wait until at least one hardware reading has completed."""
        t0 = time.time()
        while time.time() - t0 < 3.0:
            with self.lock:
                if self.tick_count >= 1:
                    break
            time.sleep(0.03)
        return self.get_snapshot()

    def get_snapshot(self):
        with self.lock:
            return {
                "capacity": self.capacity,
                "charge_mah": self.charge_mah,
                "status": self.status,
                "is_charging": self.is_charging,
                "voltage": self.voltage,
                "current_ma": self.current_ma,
                "active_wattage": self.active_wattage,
                "battery_net_wattage": self.battery_net_wattage,
                "total_input_wattage": self.total_input_wattage,
                "target_wattage": self.target_wattage,
            }

    def close(self):
        self.running = False
        self.binder.close()


# Display Elements
V_BLOCKS = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
H_BLOCKS = ["", "▏", "▎", "▍", "▌", "▋", "▊", "▉"]


def render_braille_speedometer(wattage, max_w=30.0):
    """
    Render Braille dot-matrix speedometer dial (36 cols x 8 rows = 72x32 pixels).
    Features a 250-degree circular arc, radial tick marks, and rotating needle.
    """
    sc = BrailleCanvas(36, 8)
    x0, y0 = 36, 30
    rx, ry = 31, 23

    # Draw circular outer arc
    for deg in range(215, -36, -2):
        rad = math.radians(deg)
        sc.set(x0 + math.cos(rad) * rx, y0 - math.sin(rad) * ry)

    # Draw radial tick marks across the 250-degree sweep
    ticks = [215, 165, 115, 90, 65, 15, -35]
    for t in ticks:
        rad = math.radians(t)
        sc.line(
            x0 + math.cos(rad) * (rx - 4),
            y0 - math.sin(rad) * (ry - 3),
            x0 + math.cos(rad) * rx,
            y0 - math.sin(rad) * ry
        )

    # Calculate rotating needle position for 0 to max_w scale
    ratio = min(1.0, max(0.0, wattage / max_w))
    deg = 215.0 - ratio * 250.0
    rad = math.radians(deg)
    needle_len_x = 27
    needle_len_y = 20
    sc.line(x0, y0, x0 + math.cos(rad) * needle_len_x, y0 - math.sin(rad) * needle_len_y)

    raw_lines = sc.render()

    # Center dial with color formatting
    out_lines = []
    for l in raw_lines:
        line_colored = rgb(110, 160, 210, l)
        centered = " " * 13 + line_colored + " " * 14
        out_lines.append(centered)
    return out_lines


def render_subblock_bar(val, max_w=30.0, width=47):
    """Render 8th-step sub-character progress bar."""
    ratio = min(1.0, max(0.0, val / max_w))
    total_eighths = int(round(ratio * (width * 8)))
    full_blocks = total_eighths // 8
    rem = total_eighths % 8
    sub_char = H_BLOCKS[rem] if rem > 0 else ""
    empty_blocks = max(0, width - full_blocks - (1 if rem > 0 else 0))

    r, g, b = get_wattage_rgb(val, max_w)
    active_str = rgb_bold(r, g, b, ("█" * full_blocks) + sub_char)
    empty_str = rgb(65, 70, 80, "░" * empty_blocks)
    return active_str + empty_str


def render_oscilloscope_wave(history, max_w=30.0, width=42):
    """Render scrolling power waveform with vertical blocks."""
    padded = history[-width:] if len(history) >= width else [0.0] * (width - len(history)) + history
    chars = []
    for val in padded:
        ratio = min(1.0, max(0.0, val / max_w))
        idx = int(round(ratio * 8))
        r, g, b = get_wattage_rgb(val, max_w)
        chars.append(rgb_bold(r, g, b, V_BLOCKS[idx]))
    return "".join(chars)


def render_flow_stream(frame_idx, is_charging):
    """Render power flow direction indicator."""
    if is_charging:
        stream = "──>>──────>>──────>>──────>>──────>>──────>>────"
        shift = (frame_idx * 2) % 8
        animated = stream[shift:] + stream[:shift]
        flow_txt = rgb_bold(80, 220, 160, animated[:38])
        return f" Flow: {flow_txt}  "
    else:
        stream = "──<<──────<<──────<<──────<<──────<<──────<<────"
        shift = (frame_idx * 2) % 8
        animated = stream[shift:] + stream[:shift]
        flow_txt = rgb(230, 90, 90, animated[:38])
        return f" Flow: {flow_txt}  "


def run_monitor(engine, max_watts=30.0, fps=60):
    """Main display loop running at target FPS with physics spring needle interpolation."""
    running = True

    def sig_handler(sig, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    start_time = time.time()
    frame_idx = 0

    # Physics spring variables
    needle_pos = 0.0
    needle_vel = 0.0
    k_spring = 65.0   # Spring stiffness
    c_damping = 15.0  # Damping coefficient

    history_waveform = []
    min_w = 999.0
    max_w = 0.0
    samples_w = []

    sys.stdout.write(HIDE_CURSOR + CLEAR_SCREEN)
    sys.stdout.flush()

    fps_val = max(1.0, float(fps))
    dt_target = 1.0 / fps_val
    waveform_interval = max(1, int(round(fps_val * 0.10)))  # ~100ms per waveform sample
    next_frame = time.perf_counter()

    try:
        while running:
            frame_idx += 1

            snap = engine.get_snapshot()
            target_w = snap["target_wattage"]

            # Second-order critically damped spring integration
            force = k_spring * (target_w - needle_pos) - c_damping * needle_vel
            needle_vel += force * dt_target
            needle_pos += needle_vel * dt_target
            if needle_pos < 0.0:
                needle_pos = 0.0
                needle_vel = 0.0
            display_wattage = needle_pos

            samples_w.append(display_wattage)
            if len(samples_w) > int(fps_val * 30):
                samples_w.pop(0)

            # Update waveform history every ~100ms
            if frame_idx % waveform_interval == 0:
                history_waveform.append(display_wattage)
                if len(history_waveform) > 42:
                    history_waveform.pop(0)

            if display_wattage > max_w:
                max_w = display_wattage
            if display_wattage < min_w and display_wattage > 0.0:
                min_w = display_wattage

            avg_w = sum(samples_w) / len(samples_w)

            elapsed = time.time() - start_time
            mins, secs = divmod(int(elapsed), 60)

            # Dial rows
            dial_lines = render_braille_speedometer(display_wattage, max_w=max_watts)

            is_charging = snap["is_charging"]
            status_text = "CHARGING" if is_charging else "DISCHARGING"
            status_col = (60, 220, 120) if is_charging else (100, 190, 240)
            status_tag = "[+]" if is_charging else "[-]"

            wr, wg, wb = get_wattage_rgb(display_wattage, max_watts)
            watt_str = rgb_bold(wr, wg, wb, f"{display_wattage:>5.2f} W")
            max_str = rgb_bold(190, 195, 210, f"{max_watts:.0f} W")
            stat_lbl = rgb_bold(status_col[0], status_col[1], status_col[2], f"{status_tag} {status_text}")

            digital_readout = f"                 {watt_str}  /  {max_str}   {stat_lbl}             "

            subblock_bar = render_subblock_bar(display_wattage, max_w=max_watts, width=47)
            oscilloscope = render_oscilloscope_wave(history_waveform, max_w=max_watts, width=42)
            flow_stream = render_flow_stream(frame_idx, is_charging)

            curr_val = snap["current_ma"]
            curr_str = rgb_bold(60, 220, 120, f"{curr_val:>+7.1f} mA") if curr_val > 0 else rgb_bold(230, 80, 80, f"{curr_val:>+7.1f} mA")
            volt_str = rgb_bold(220, 220, 230, f"{snap['voltage']:.3f} V")
            level_str = rgb_bold(100, 200, 240, f"{snap['capacity']}%")
            mah_str = rgb(140, 145, 160, f"({int(snap['charge_mah'])} mAh)")

            box_width = 63

            w0 = 0.0
            w1 = max_watts * 0.25
            w2 = max_watts * 0.50
            w3 = max_watts * 0.75
            w4 = max_watts
            if abs(max_watts - 30.0) < 0.01:
                ticks_display = "        0W        7.5W         15W        22.5W        30W     "
            else:
                ticks_display = f"        {w0:.0f}W        {w1:.1f}W         {w2:.0f}W        {w3:.1f}W        {w4:.0f}W     "

            content_lines = [
                rgb_bold(100, 190, 240, f"                   POWER METER (0 - {int(max_watts)}W SCALE)                 "),
                "",
                dial_lines[0],
                dial_lines[1],
                dial_lines[2],
                dial_lines[3],
                dial_lines[4],
                dial_lines[5],
                dial_lines[6],
                dial_lines[7],
                digital_readout,
                rgb(130, 135, 150, ticks_display),
                f"       [{subblock_bar}]   ",
                f"       {rgb(130, 135, 150, 'HISTORY:')} {oscilloscope}   ",
                f"       Current: {curr_str}    Voltage: {volt_str}    Level: {level_str}   ",
            ]

            if is_charging:
                nb_str = rgb_bold(60, 220, 120, f"{snap['battery_net_wattage']:>5.2f} W")
                ci_str = rgb_bold(230, 190, 50, f"{snap['total_input_wattage']:>5.2f} W")
                content_lines.append(f"       Battery In: {nb_str}    Input Draw: {ci_str} {mah_str}   ")
            else:
                sd_str = rgb_bold(230, 80, 80, f"{snap['active_wattage']:>5.2f} W")
                content_lines.append(f"       Active Draw: {sd_str}   Remaining: {level_str} {mah_str}   ")

            content_lines.append(f"       {flow_stream}   ")

            # Border assembly
            b_edge = rgb(70, 140, 200, "╔" + ("═" * (box_width + 2)) + "╗")
            b_div  = rgb(70, 140, 200, "║")
            b_bot  = rgb(70, 140, 200, "╚" + ("═" * (box_width + 2)) + "╝")

            frame = [
                f"{CURSOR_HOME}{b_edge}",
            ]
            for c_str in content_lines:
                c_pad = pad_visible(c_str, box_width)
                frame.append(f"{b_div} {c_pad} {b_div}")
            frame.append(b_bot)

            footer_rate = rgb(100, 190, 240, "100ms")
            footer_fps = rgb(190, 195, 210, f"{int(fps_val)} FPS")
            footer_peak = rgb_bold(220, 220, 230, f"{max_w:5.2f} W")
            footer_avg = rgb_bold(190, 195, 210, f"{avg_w:5.2f} W")
            frame.append(
                f" {rgb(130, 135, 150, 'Sampling:')} {footer_rate}  "
                f"{rgb(130, 135, 150, 'Display:')} {footer_fps}  "
                f"{rgb(130, 135, 150, 'Peak:')} {footer_peak}  "
                f"{rgb(130, 135, 150, 'Avg:')} {footer_avg}  "
                f"{rgb(130, 135, 150, 'Stop: Ctrl+C')}"
            )

            sys.stdout.write("\n".join(frame) + "\n")
            sys.stdout.flush()

            # Target FPS pacing
            next_frame += dt_target
            sleep_time = next_frame - time.perf_counter()
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                next_frame = time.perf_counter()

    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write(SHOW_CURSOR + "\n")
        sys.stdout.flush()
        engine.close()

    if min_w == 999.0:
        min_w = 0.0
    print(f"\n{rgb_bold(60, 220, 120, f'Session finished: Peak: {max_w:.2f} W | Average: {avg_w:.2f} W (Duration: {mins}m {secs}s)')}")


def main():
    parser = argparse.ArgumentParser(
        description="Android Power Meter (Max 30W, 100ms Sampling, 60 FPS Display)",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-m", "--max-watts",
        type=float,
        default=30.0,
        help="Maximum scale on meter in Watts (default: 30.0).",
    )
    parser.add_argument(
        "-f", "--fps",
        type=int,
        default=60,
        help="Display refresh rate in frames per second (default: 60).",
    )
    parser.add_argument(
        "-s", "--snapshot",
        action="store_true",
        help="Print a single instantaneous measurement snapshot and exit.",
    )
    parser.add_argument(
        "-j", "--json",
        action="store_true",
        help="Output JSON format.",
    )
    parser.add_argument(
        "-v", "--voltage",
        type=float,
        default=None,
        help="Override battery/charger voltage in Volts.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors.",
    )

    args = parser.parse_args()

    global USE_COLORS
    if args.no_color or not sys.stdout.isatty():
        USE_COLORS = False

    engine = PowerReaderEngine(override_voltage=args.voltage)

    if args.json:
        data = engine.read_once()
        engine.close()
        print(json.dumps(data, indent=2))
        return

    if args.snapshot:
        data = engine.read_once()
        engine.close()
        print(f"\nStatus: {data['status']} | Current: {data['current_ma']:+.1f} mA | Wattage: {data['target_wattage']:.2f} W | Battery: {data['capacity']}% ({data['charge_mah']:.0f} mAh)")
        return

    # Default: Run the live 60 FPS monitor (Max 30W)
    run_monitor(engine, max_watts=args.max_watts, fps=args.fps)


if __name__ == "__main__":
    main()
