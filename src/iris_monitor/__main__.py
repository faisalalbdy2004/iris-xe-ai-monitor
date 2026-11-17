"""Terminal entry point for Iris Xe AI Monitor."""

import argparse
import json
import math
import platform
import sys

from .dashboard import temperature_sampler, watch
from .telemetry import collect_status, status_sampler
from .windows_temperature import read_temperatures


def _value(value, unit=""):
    return "unavailable" if value is None else f"{value}{unit}"


def _safe_text(value):
    return "".join(character for character in value if character.isprintable())


def _status_lines(status):
    ac_label = {True: "online", False: "offline"}.get(status["ac_online"])
    yield f"Platform: {status['platform']}"
    yield f"CPU utilization: {_value(status['cpu_percent'], '%')}"
    yield f"RAM utilization: {_value(status['ram_percent'], '%')}"
    yield f"RAM total: {_value(status['ram_total_bytes'], ' bytes')}"
    yield f"RAM available: {_value(status['ram_available_bytes'], ' bytes')}"
    yield f"AC power: {_value(ac_label)}"
    yield f"Battery charge: {_value(status['battery_percent'], '%')}"

    if status["intel_gpus"] is None:
        yield "Intel GPU telemetry: unavailable"
    else:
        for gpu in status["intel_gpus"]:
            device = _safe_text(gpu.get("name") or gpu["device"])
            if "utilization_percent" in gpu:
                busy = _value(gpu["utilization_percent"], "%")
                yield f"Intel GPU ({device}) busiest engine: {busy}"
            frequency = _value(gpu["frequency_mhz"], " MHz")
            yield f"Intel GPU ({device}) frequency: {frequency}"

    if status["temperatures"] is None:
        yield "Temperatures: unavailable"
    else:
        for reading in status["temperatures"]:
            label = _safe_text(reading["label"] or "unlabeled")
            sensor = _safe_text(reading["sensor"])
            yield f"Temperature ({sensor}, {label}): {reading['celsius']} C"


def _interval(value):
    seconds = float(value)
    if not math.isfinite(seconds) or not 0.5 <= seconds <= 3600:
        raise argparse.ArgumentTypeError("interval must be between 0.5 and 3600 seconds")
    return seconds


def _count(value):
    count = int(value)
    if count < 1:
        raise argparse.ArgumentTypeError("count must be positive")
    return count


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read system telemetry.")
    commands = parser.add_subparsers(dest="command", required=True)
    status = commands.add_parser("status", help="print one telemetry snapshot")
    status.add_argument("--json", action="store_true", help="print JSON")
    dashboard = commands.add_parser("watch", help="refresh telemetry until Ctrl+C")
    dashboard.add_argument("--interval", type=_interval, default=1.0, help="seconds between refreshes")
    dashboard.add_argument("--count", type=_count, help="stop after this many refreshes")
    for command in (status, dashboard):
        command.add_argument("--lhm", action="store_true",
                             help="read Windows temperatures from a running Libre Hardware Monitor")
    args = parser.parse_args(argv)

    if args.command == "watch":
        read = read_temperatures if args.lhm and platform.system() == "Windows" else None
        try:
            with temperature_sampler(read) as temperatures, status_sampler(
                windows_temperatures=temperatures,
            ) as sample:
                watch(sample, _status_lines, args.interval, args.count, sys.stdout)
        except KeyboardInterrupt:
            pass
        return 0

    snapshot = collect_status(lhm=True) if args.lhm else collect_status()
    if args.json:
        print(json.dumps(snapshot, indent=2, allow_nan=False))
    else:
        print("\n".join(_status_lines(snapshot)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
