"""Compare adjacent Rust watch frames with independently collected OS counters."""

import argparse
import ctypes as ct
import json
import statistics
import subprocess
import time

import psutil


class CpuCounter:
    """Read a single English-named Windows PDH counter with its own query."""

    def __init__(self, counter):
        from iris_monitor.windows_gpu import DWORD, HANDLE, FormattedValue, _bind

        pdh = ct.WinDLL("pdh.dll")
        self.query, self.counter = HANDLE(), HANDLE()
        self.value_type = FormattedValue
        self.collect = _bind(pdh, "PdhCollectQueryData", DWORD, HANDLE)
        self.close_query = _bind(pdh, "PdhCloseQuery", DWORD, HANDLE)
        self.format = _bind(pdh, "PdhGetFormattedCounterValue", DWORD, HANDLE, DWORD,
                            ct.c_void_p, ct.POINTER(FormattedValue))
        open_query = _bind(pdh, "PdhOpenQueryW", DWORD, ct.c_wchar_p, ct.c_size_t,
                           ct.POINTER(HANDLE))
        add = _bind(pdh, "PdhAddEnglishCounterW", DWORD, HANDLE, ct.c_wchar_p,
                    ct.c_size_t, ct.POINTER(HANDLE))
        add_local = _bind(pdh, "PdhAddCounterW", DWORD, HANDLE, ct.c_wchar_p,
                          ct.c_size_t, ct.POINTER(HANDLE))
        if open_query(None, 0, ct.byref(self.query)):
            return
        if add(self.query, counter, 0, ct.byref(self.counter)):
            if add_local(self.query, counter, 0, ct.byref(self.counter)):
                self.close()

    def read(self):
        if not self.query or self.collect(self.query):
            return None
        sample = self.value_type()
        if self.format(self.counter, 0x200 | 0x8000, None, ct.byref(sample)):
            return None
        value = sample.value.double
        return value if sample.status in (0, 1) and 0 <= value <= 100 else None

    def close(self):
        if self.query:
            self.close_query(self.query)
            self.query = None


def run(binary, interval, count):
    import sys
    refs = {}
    gpu = None
    if sys.platform == "win32":
        from iris_monitor.windows_gpu import WindowsGpu
        refs = {
            "pdh_processor_time": CpuCounter(r"\Processor Information(_Total)\% Processor Time"),
            "pdh_processor_utility": CpuCounter(r"\Processor Information(_Total)\% Processor Utility"),
        }
        gpu = WindowsGpu()
    frames = []
    started = time.monotonic()
    proc = subprocess.Popen(
        [binary, "watch", "--json", "--interval", str(interval), "--count", str(count + 1)],
        stdout=subprocess.PIPE, text=True, encoding="utf-8",
    )
    try:
        for index, line in enumerate(proc.stdout):
            arrival = time.monotonic()
            psutil_time = psutil.cpu_percent(interval=None)
            counter_values = {name: ref.read() for name, ref in refs.items()}
            gpu_reference = {card["device"]: card["utilization_percent"]
                             for card in ((gpu.read() or []) if gpu else [])}
            if index == 0:
                previous = arrival
                continue
            data = json.loads(line)
            frames.append({
                "elapsed_seconds": round(arrival - started, 3),
                "interval_seconds": round(arrival - previous, 3),
                "rust_cpu_percent": data["cpu_percent"],
                "psutil_cpu_percent": psutil_time,
                **counter_values,
                "gpus": [
                    {"device": card["device"], "name": card.get("name"),
                     "rust_busiest_engine": card.get("utilization_percent"),
                     "pdh_busiest_engine": gpu_reference.get(card["device"])}
                    for card in data["intel_gpus"] or []
                ],
            })
            previous = arrival
        if proc.wait(timeout=3):
            raise RuntimeError("Rust watch exited with an error")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=3)
        proc.stdout.close()
        for ref in refs.values():
            ref.close()
        if gpu:
            gpu.close()
    if len(frames) != count:
        raise RuntimeError(f"expected {count} frames, received {len(frames)}")
    return frames


def compare(pairs):
    errors = [abs(a - b) for a, b in pairs if a is not None and b is not None]
    return {"pairs": len(errors),
            "median_abs_difference_pp": round(statistics.median(errors), 3) if errors else None,
            "max_abs_difference_pp": round(max(errors), 3) if errors else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rust-monitor", required=True)
    parser.add_argument("--interval", type=float, default=1)
    parser.add_argument("--count", type=int, default=12)
    args = parser.parse_args()
    if not 0.5 <= args.interval <= 10 or not 2 <= args.count <= 120:
        parser.error("choose 0.5–10 seconds and 2–120 samples")
    frames = run(args.rust_monitor, args.interval, args.count)
    summaries = {
        name: compare((frame["rust_cpu_percent"], frame.get(name)) for frame in frames)
        for name in ("psutil_cpu_percent", "pdh_processor_time", "pdh_processor_utility")
    }
    summaries["pdh_gpu_busiest_engine"] = compare(
        (gpu["rust_busiest_engine"], gpu["pdh_busiest_engine"])
        for frame in frames for gpu in frame["gpus"]
    )
    print(json.dumps({"summary": summaries, "frames": frames}, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
