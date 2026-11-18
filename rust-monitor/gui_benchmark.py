"""Measure the CorePulse GUI process during idle, pointer input, and minimization."""

import argparse
import ctypes as ct
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
import time
from collections import defaultdict

import psutil

from benchmark import process_totals


class WindowsWindow:
    def __init__(self, pid):
        from ctypes import wintypes as w
        from iris_monitor.windows_gpu import EngineQuery

        self.pid = pid
        self.handle = None
        self.gpu = EngineQuery()
        self.gpu.prime()
        user = ct.WinDLL("user32")
        self.callback_type = ct.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)

        def bind(name, result, *args):
            function = getattr(user, name)
            function.restype, function.argtypes = result, args
            return function

        self.enum = bind("EnumWindows", w.BOOL, self.callback_type, w.LPARAM)
        self.get_pid = bind("GetWindowThreadProcessId", w.DWORD, w.HWND, ct.POINTER(w.DWORD))
        self.get_title = bind("GetWindowTextW", ct.c_int, w.HWND, w.LPWSTR, ct.c_int)
        self.is_visible = bind("IsWindowVisible", w.BOOL, w.HWND)
        self.is_minimized = bind("IsIconic", w.BOOL, w.HWND)
        self.show = bind("ShowWindow", w.BOOL, w.HWND, ct.c_int)
        self.post = bind("PostMessageW", w.BOOL, w.HWND, w.UINT, w.WPARAM, w.LPARAM)

    def discover(self):
        def find(handle, _):
            owner = ct.c_uint32()
            self.get_pid(handle, ct.byref(owner))
            if owner.value != self.pid or not self.is_visible(handle):
                return True
            title = ct.create_unicode_buffer(128)
            self.get_title(handle, title, len(title))
            if title.value == "CorePulse":
                self.handle = handle
                return False
            return True

        self.enum(self.callback_type(find), 0)
        return self.handle is not None

    def input(self, index):
        x, y = 40 + index % 20 * 4, 120
        self.post(self.handle, 0x0200, 0, (y << 16) | x)  # WM_MOUSEMOVE to this window only

    def minimize(self):
        self.show(self.handle, 6)

    def minimized(self):
        return self.is_minimized(self.handle)

    def restore(self):
        self.show(self.handle, 9)

    def utilization(self):
        values = defaultdict(float)
        for name, value in self.gpu.read():
            match = re.fullmatch(rf"pid_{self.pid}_(luid_\w+_phys_\d+_eng_\d+)_engtype_.+", name)
            if match and 0 <= value <= 100:
                values[match[1]] += value
        return max(values.values()) if values and max(values.values()) <= 100 else None

    def close(self):
        if self.handle:
            self.post(self.handle, 0x0010, 0, 0)  # WM_CLOSE
        self.gpu.close()


class X11Window:
    def __init__(self, pid):
        self.pid = pid
        self.handle = None

    def discover(self):
        result = subprocess.run(
            ["xdotool", "search", "--pid", str(self.pid), "--onlyvisible", "--name", "^CorePulse$"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            self.handle = result.stdout.splitlines()[0]
        return self.handle is not None

    def input(self, index):
        subprocess.run(["xdotool", "mousemove", "--window", self.handle, str(40 + index % 20 * 4), "120"],
                       check=True, timeout=2)

    def minimize(self):
        subprocess.run(["xdotool", "windowminimize", self.handle], check=True, timeout=3)

    def minimized(self):
        result = subprocess.run(["xprop", "-id", self.handle, "_NET_WM_STATE"],
                                capture_output=True, text=True, timeout=2)
        return "_NET_WM_STATE_HIDDEN" in result.stdout

    def restore(self):
        subprocess.run(["xdotool", "windowactivate", "--sync", self.handle],
                       check=True, timeout=3)

    def utilization(self):
        return None

    def close(self):
        if self.handle:
            # This key goes to the CorePulse window in an isolated Xvfb session.
            subprocess.run(["xdotool", "windowactivate", "--sync", self.handle],
                           check=False, timeout=3)
            subprocess.run(["xdotool", "key", "Alt+F4"],
                           check=False, timeout=3)


def measure(root, window, state, seconds):
    first_cpu, resident = process_totals(root)
    rss = [resident]
    gpu = []
    window.utilization()  # Prime the reference at the phase boundary.
    started = time.monotonic()
    wall_start = time.time_ns()
    next_read = started + 0.5
    index = 0
    while time.monotonic() < started + seconds:
        if state == "active":
            window.input(index)
            index += 1
        now = time.monotonic()
        if now >= next_read:
            _, resident = process_totals(root)
            rss.append(resident)
            value = window.utilization()
            if value is not None:
                gpu.append(value)
            next_read += 0.5
        delay = 0.1 if state == "active" else max(0, next_read - time.monotonic())
        time.sleep(min(delay, max(0, started + seconds - time.monotonic())))
    last_cpu, resident = process_totals(root)
    elapsed = time.monotonic() - started
    return {
        "_window": (wall_start, time.time_ns()),
        "cpu_percent_of_one_core": round(100 * (last_cpu - first_cpu) / elapsed, 4),
        "median_rss_mib": round(statistics.median([*rss, resident]) / 2**20, 2),
        "gpu_busiest_engine_median_percent": round(statistics.median(gpu), 4) if gpu else None,
        "gpu_samples": len(gpu),
    }


def frame_profile(lines, start, end):
    durations = []
    updates = 0
    for line in lines:
        if not line.startswith("COREPULSE_FRAME "):
            continue
        _, timestamp, previous_us = line.split()
        if start <= int(timestamp) < end:
            updates += 1
            if float(previous_us) >= 0:
                durations.append(float(previous_us))
    return {"updates": updates, "previous_frame_median_us":
            statistics.median(durations) if durations else None}


def run(binary, seconds, trace=None):
    started = time.monotonic()
    env = {**os.environ, "COREPULSE_GUI_PROFILE": "1"} if trace else None
    proc = subprocess.Popen([binary, "gui"], env=env, stderr=trace)
    window = None
    graceful = None
    try:
        root = psutil.Process(proc.pid)
        window = WindowsWindow(proc.pid) if sys.platform == "win32" else X11Window(proc.pid)
        while not window.discover():
            if proc.poll() is not None or time.monotonic() - started > 12:
                raise RuntimeError("CorePulse window did not become visible")
            time.sleep(0.05)
        startup = round(1000 * (time.monotonic() - started), 2)
        time.sleep(1)
        results = {state: measure(root, window, state, seconds) for state in ("idle", "active")}
        window.minimize()
        until = time.monotonic() + 3
        while not window.minimized():
            if time.monotonic() > until:
                raise RuntimeError("window manager did not minimize CorePulse")
            time.sleep(0.05)
        time.sleep(1)
        results["minimized"] = measure(root, window, "minimized", seconds)
        window.restore()
        until = time.monotonic() + 3
        while window.minimized():
            if time.monotonic() > until:
                raise RuntimeError("window manager did not restore CorePulse")
            time.sleep(0.05)
    finally:
        try:
            if window:
                window.close()
            graceful = proc.wait(timeout=5) == 0
        except (subprocess.SubprocessError, OSError):
            proc.terminate()
            proc.wait(timeout=5)
            graceful = False
    if trace:
        trace.seek(0)
        lines = trace.read().splitlines()
    for phase in results.values():
        start, end = phase.pop("_window")
        if trace:
            phase["frame_profile"] = frame_profile(lines, start, end)
    return {"time_to_visible_ms": startup, "seconds_per_phase": seconds, "phases": results,
            "window_restored": True, "clean_window_close": graceful}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rust-monitor", required=True)
    parser.add_argument("--seconds", type=float, default=10)
    parser.add_argument("--profile", action="store_true", help="record eframe update counts and CPU timing")
    args = parser.parse_args()
    if not 5 <= args.seconds <= 60:
        parser.error("choose 5–60 seconds per phase")
    if args.profile:
        with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as trace:
            result = run(args.rust_monitor, args.seconds, trace)
    else:
        result = run(args.rust_monitor, args.seconds)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
