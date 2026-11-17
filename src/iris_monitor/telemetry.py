"""Collect a read-only snapshot of system telemetry."""

import ctypes
import math
import platform
import re
from pathlib import Path

import psutil


class SystemPowerStatus(ctypes.Structure):
    _fields_ = [
        ("ac_line_status", ctypes.c_uint8),
        ("battery_flag", ctypes.c_uint8),
        ("battery_life_percent", ctypes.c_uint8),
        ("system_status_flag", ctypes.c_uint8),
        ("battery_life_time", ctypes.c_uint32),
        ("battery_full_life_time", ctypes.c_uint32),
    ]


def _read_sensor(read, *args, **kwargs):
    try:
        return read(*args, **kwargs)
    except (OSError, NotImplementedError, psutil.Error):
        return None


def _read_text(path):
    try:
        return path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        return None


def _entries(path):
    try:
        return sorted(path.iterdir())
    except OSError:
        return []


def _percent(value):
    return value if value is not None and 0 <= value <= 100 else None


def _windows_power(get_status):
    status = SystemPowerStatus()
    if not get_status(ctypes.byref(status)):
        return None, None
    ac_online = {0: False, 1: True}.get(status.ac_line_status)
    if status.battery_flag == 255 or status.battery_flag & 128:
        return ac_online, None
    return ac_online, _percent(status.battery_life_percent)


def _linux_power(sysfs):
    battery = _read_sensor(psutil.sensors_battery)
    online_states = []
    for supply in _entries(sysfs / "class/power_supply"):
        supply_type = _read_text(supply / "type")
        if supply_type == "Mains" or (supply_type or "").startswith("USB"):
            online_states.append(_read_text(supply / "online"))
    ac_online = None
    if "1" in online_states:
        ac_online = True
    elif online_states and all(state == "0" for state in online_states):
        ac_online = False
    elif not online_states and battery is not None:
        ac_online = battery.power_plugged
    return ac_online, _percent(battery.percent) if battery is not None else None


def _temperatures():
    groups = _read_sensor(psutil.sensors_temperatures) or {}
    return [
        {"sensor": source, "label": reading.label or None, "celsius": reading.current}
        for source, readings in sorted(groups.items())
        for reading in readings
        if reading.current is not None and math.isfinite(reading.current)
    ] or None


def _intel_gpus(sysfs):
    gpus = []
    for card in _entries(sysfs / "class/drm"):
        if not re.fullmatch(r"card[0-9]+", card.name):
            continue
        if _read_text(card / "device/vendor") != "0x8086":
            continue
        raw_frequency = _read_text(card / "gt_act_freq_mhz")
        frequency = None
        if raw_frequency and re.fullmatch(r"[0-9]{1,10}", raw_frequency):
            frequency = int(raw_frequency)
        gpus.append({
            "device": card.name,
            "frequency_mhz": frequency,
        })
    return gpus or None


def collect_status(sysfs=Path("/sys")):
    """Return a snapshot with None for unavailable readings."""
    system = platform.system()
    cpu_percent = _read_sensor(psutil.cpu_percent, interval=0.2)
    memory = _read_sensor(psutil.virtual_memory)
    ac_online = battery_percent = temperatures = intel_gpus = None

    if system == "Windows":
        power = _read_sensor(_windows_power, ctypes.windll.kernel32.GetSystemPowerStatus)
        if power is not None:
            ac_online, battery_percent = power
    elif system == "Linux":
        ac_online, battery_percent = _linux_power(sysfs)
        temperatures = _temperatures()
        intel_gpus = _intel_gpus(sysfs)

    return {
        "platform": system,
        "cpu_percent": _percent(cpu_percent),
        "ram_percent": _percent(memory.percent) if memory is not None else None,
        "ram_total_bytes": memory.total if memory is not None else None,
        "ram_available_bytes": memory.available if memory is not None else None,
        "ac_online": ac_online,
        "battery_percent": battery_percent,
        "temperatures": temperatures,
        "intel_gpus": intel_gpus,
    }
