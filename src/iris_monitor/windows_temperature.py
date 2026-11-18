"""Optional read-only access to a running Libre Hardware Monitor WMI provider."""

import json
import os
import subprocess
from pathlib import Path

_QUERY = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$rows = @(Get-CimInstance -Namespace 'root\LibreHardwareMonitor' -ClassName Sensor -Filter "SensorType = 'Temperature'" | Select-Object Identifier, Name, Value)
ConvertTo-Json -InputObject $rows -Compress
"""


def read_temperatures():
    system_root = os.environ.get("SystemRoot")
    if not system_root:
        return None
    powershell = Path(system_root) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    try:
        result = subprocess.run(
            [str(powershell), "-NoProfile", "-NonInteractive", "-Command", _QUERY],
            capture_output=True, check=True, timeout=3, encoding="utf-8-sig",
        )
        rows = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if not isinstance(rows, list):
        return None

    readings = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        identifier = row.get("Identifier")
        label = row.get("Name")
        value = row.get("Value")
        if not isinstance(identifier, str) or not identifier.startswith("/"):
            continue
        hardware = identifier.split("/")[1]
        if not (hardware.endswith("cpu") or hardware.startswith("gpu-")):
            continue
        if type(value) not in (int, float) or not -273.15 <= value <= 250:
            continue
        readings.append({
            "sensor": f"librehardwaremonitor/{hardware}",
            "label": label if isinstance(label, str) and label else None,
            "celsius": value,
        })
    return readings or None
