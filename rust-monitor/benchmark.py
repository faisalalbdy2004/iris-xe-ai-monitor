"""Compare release Rust and installed Python CLI under an identical text-watch workload."""

import argparse
from collections import Counter
import concurrent.futures
import json
import statistics
import subprocess
import threading
import time

import psutil


def run(command):
    start = time.perf_counter()
    result = subprocess.run(command, capture_output=True, check=True, timeout=20)
    return 1000 * (time.perf_counter() - start), result.stdout


def process_totals(root):
    processes = [root, *root.children(recursive=True)]
    cpu_seconds = resident = 0
    for process in processes:
        with process.oneshot():
            cpu = process.cpu_times()
            cpu_seconds += cpu.user + cpu.system
            resident += process.memory_info().rss
    return cpu_seconds, resident


def watch(executable, interval, seconds):
    ready = threading.Event()
    frames = []
    proc = subprocess.Popen(
        [executable, "watch", "--interval", str(interval)],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    root = psutil.Process(proc.pid)

    def drain():
        for line in proc.stdout:
            if line.startswith(b"Platform: "):
                frames.append(time.perf_counter())
                ready.set()

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    try:
        if not ready.wait(10):
            raise RuntimeError(f"watch printed no frames: {executable}")
        started = time.perf_counter()
        first_cpu, resident = process_totals(root)
        rss = [resident]
        while time.perf_counter() < started + seconds:
            time.sleep(min(0.5, max(0, started + seconds - time.perf_counter())))
            last_cpu, resident = process_totals(root)
            rss.append(resident)
        ended = time.perf_counter()
        cpu = last_cpu - first_cpu
        if cpu < 0:
            raise RuntimeError("watch process tree changed during observation")
        return {
            "duration_seconds": round(ended - started, 3),
            "frames": sum(started <= frame <= ended for frame in frames),
            "cpu_seconds": round(cpu, 5),
            "cpu_percent_of_one_core": round(100 * cpu / (ended - started), 4),
            "median_rss_mib": round(statistics.median(rss) / 2**20, 2),
        }
    finally:
        for process in reversed(root.children(recursive=True)):
            try:
                process.terminate()
            except psutil.NoSuchProcess:
                pass
        if proc.poll() is None:
            proc.terminate()
        proc.wait(timeout=5)
        reader.join(timeout=2)
        proc.stdout.close()


def pairwise_stats(pairs):
    if not pairs:
        return {"matched_samples": 0, "median_abs_difference": None}
    return {
        "matched_samples": len(pairs),
        "median_abs_difference": round(statistics.median(abs(a - b) for a, b in pairs), 3),
    }


def comparison(python, rust, repeats):
    metrics = ("cpu_percent", "ram_percent", "ram_total_bytes", "ac_online", "battery_percent")
    matched = {metric: [] for metric in metrics}
    frequencies, gpu_busy, temperatures = [], [], []
    ambiguous_temperature_keys = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        for _ in range(repeats):
            jobs = [executor.submit(run, [exe, "status", "--json"]) for exe in (python, rust)]
            left, right = [json.loads(job.result()[1]) for job in jobs]
            if left.keys() != right.keys():
                raise RuntimeError("top-level status JSON keys differ")
            for metric in metrics:
                if left[metric] is not None and right[metric] is not None:
                    matched[metric].append((left[metric], right[metric]))
            left_cards = {gpu["device"]: gpu for gpu in left["intel_gpus"] or []}
            for gpu in right["intel_gpus"] or []:
                other = left_cards.get(gpu["device"], {})
                for name, pairs in (("frequency_mhz", frequencies), ("utilization_percent", gpu_busy)):
                    if gpu.get(name) is not None and other.get(name) is not None:
                        pairs.append((gpu[name], other[name]))
            left_rows, right_rows = [snapshot["temperatures"] or [] for snapshot in (left, right)]
            left_counts, right_counts = [
                Counter((row["sensor"], row["label"]) for row in rows)
                for rows in (left_rows, right_rows)
            ]
            common = left_counts.keys() & right_counts.keys()
            unique = {key for key in common if left_counts[key] == right_counts[key] == 1}
            ambiguous_temperature_keys += len(common - unique)
            left_temp = {(row["sensor"], row["label"]): row["celsius"] for row in left_rows}
            right_temp = {(row["sensor"], row["label"]): row["celsius"] for row in right_rows}
            temperatures.extend((left_temp[key], right_temp[key]) for key in unique)
    return {
        **{metric: pairwise_stats(pairs) for metric, pairs in matched.items()},
        "gpu_frequency_mhz": pairwise_stats(frequencies),
        "gpu_utilization_percentage_points": pairwise_stats(gpu_busy),
        "temperature_celsius": pairwise_stats(temperatures),
        "ambiguous_temperature_keys_skipped": ambiguous_temperature_keys,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-monitor", required=True)
    parser.add_argument("--rust-monitor", required=True)
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--watch-seconds", type=float, default=10)
    args = parser.parse_args()
    if args.repeats < 2 or not 5 <= args.watch_seconds <= 120:
        parser.error("use at least two repeats and a 5–120 second watch window")

    executables = {"python": args.python_monitor, "rust": args.rust_monitor}
    timings = {name: {"help": [], "snapshot": []} for name in executables}
    for executable in executables.values():
        run([executable, "--help"])
        run([executable, "status", "--json"])
    for index in range(args.repeats):
        order = list(executables.items())
        for name, exe in (order if index % 2 == 0 else order[::-1]):
            timings[name]["help"].append(run([exe, "--help"])[0])
            timings[name]["snapshot"].append(run([exe, "status", "--json"])[0])
    report = {}
    for name, executable in executables.items():
        idle = watch(executable, 5, args.watch_seconds)
        active = watch(executable, 1, args.watch_seconds)
        extra_frames = active["frames"] - idle["frames"]
        extra_cpu = active["cpu_seconds"] - idle["cpu_seconds"]
        report[name] = {
            "help_median_ms": round(statistics.median(timings[name]["help"]), 2),
            "snapshot_median_ms": round(statistics.median(timings[name]["snapshot"]), 2),
            "watch_5s_interval": idle,
            "watch_1s_interval": active,
            "estimated_extra_cpu_ms_per_frame": round(1000 * extra_cpu / extra_frames, 3)
            if extra_frames > 0 and extra_cpu >= 0 else None,
        }
    print(json.dumps({
        "repeats": args.repeats,
        "watch_seconds_per_interval": args.watch_seconds,
        "overhead": report,
        "pairwise_agreement": comparison(args.python_monitor, args.rust_monitor, args.repeats),
    }, indent=2))


if __name__ == "__main__":
    main()
