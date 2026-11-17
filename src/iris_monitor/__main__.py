"""Terminal entry point for Iris Xe AI Monitor."""

import argparse
import json

from .telemetry import collect_status


def _value(value, unit=""):
    return "unavailable" if value is None else f"{value}{unit}"


def _print_status(status):
    ac_label = {True: "online", False: "offline"}.get(status["ac_online"])
    print(f"Platform: {status['platform']}")
    print(f"CPU utilization: {_value(status['cpu_percent'], '%')}")
    print(f"RAM utilization: {_value(status['ram_percent'], '%')}")
    print(f"RAM total: {_value(status['ram_total_bytes'], ' bytes')}")
    print(f"RAM available: {_value(status['ram_available_bytes'], ' bytes')}")
    print(f"AC power: {_value(ac_label)}")
    print(f"Battery charge: {_value(status['battery_percent'], '%')}")

    if status["temperatures"] is None:
        print("Temperatures: unavailable")
    else:
        for reading in status["temperatures"]:
            label = reading["label"] or "unlabeled"
            print(f"Temperature ({reading['sensor']}, {label}): {reading['celsius']} C")

    if status["intel_gpus"] is None:
        print("Intel GPU telemetry: unavailable")
    else:
        for gpu in status["intel_gpus"]:
            frequency = _value(gpu["frequency_mhz"], " MHz")
            print(f"Intel GPU ({gpu['device']}) frequency: {frequency}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read system telemetry.")
    commands = parser.add_subparsers(dest="command", required=True)
    status = commands.add_parser("status", help="print one telemetry snapshot")
    status.add_argument("--json", action="store_true", help="print JSON")
    args = parser.parse_args(argv)

    snapshot = collect_status()
    if args.json:
        print(json.dumps(snapshot, indent=2, allow_nan=False))
    else:
        _print_status(snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
