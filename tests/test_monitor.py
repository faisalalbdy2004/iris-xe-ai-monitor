import ctypes
import io
import json
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from iris_monitor import telemetry
from iris_monitor.__main__ import main


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        temp = stack.enter_context(tempfile.TemporaryDirectory())
        self.sysfs = Path(temp)
        self.cpu = stack.enter_context(patch.object(
            telemetry.psutil, "cpu_percent", return_value=0,
        ))
        self.memory = stack.enter_context(patch.object(
            telemetry.psutil, "virtual_memory",
            return_value=SimpleNamespace(percent=25, total=4000, available=3000),
        ))

    def write_sensor(self, path, value):
        path = self.sysfs / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="ascii")

    def linux_snapshot(self, battery=None, temperatures=None):
        with (
            patch.object(telemetry.platform, "system", return_value="Linux"),
            patch.object(telemetry.psutil, "sensors_battery", return_value=battery, create=True),
            patch.object(
                telemetry.psutil, "sensors_temperatures", return_value=temperatures, create=True,
            ),
        ):
            return telemetry.collect_status(self.sysfs)

    def test_linux_available_metrics(self):
        self.write_sensor("class/power_supply/AC/type", "Mains")
        self.write_sensor("class/power_supply/AC/online", "1")
        self.write_sensor("class/drm/card0/device/vendor", "0x8086")
        self.write_sensor("class/drm/card0/gt_act_freq_mhz", "450")
        self.write_sensor("class/drm/card1/device/vendor", "0x1002")
        snapshot = self.linux_snapshot(
            SimpleNamespace(percent=42, power_plugged=False),
            {"coretemp": [
                SimpleNamespace(label="Package id 0", current=38.5),
                SimpleNamespace(label="Invalid", current=float("nan")),
            ]},
        )
        self.cpu.assert_called_once_with(interval=0.2)
        self.assertEqual(snapshot, {
            "platform": "Linux",
            "cpu_percent": 0,
            "ram_percent": 25,
            "ram_total_bytes": 4000,
            "ram_available_bytes": 3000,
            "ac_online": True,
            "battery_percent": 42,
            "temperatures": [{"sensor": "coretemp", "label": "Package id 0", "celsius": 38.5}],
            "intel_gpus": [{"device": "card0", "frequency_mhz": 450}],
        })

    def test_linux_fallback_and_malformed_frequency(self):
        self.write_sensor("class/drm/card0/device/vendor", "0x8086")
        self.write_sensor("class/drm/card0/gt_act_freq_mhz", "invalid")
        snapshot = self.linux_snapshot(SimpleNamespace(percent=0, power_plugged=False))
        self.assertIs(snapshot["ac_online"], False)
        self.assertEqual(snapshot["battery_percent"], 0)
        self.assertEqual(snapshot["intel_gpus"], [{"device": "card0", "frequency_mhz": None}])

    def test_linux_no_battery_with_offline_adapter(self):
        self.write_sensor("class/power_supply/AC/type", "Mains")
        self.write_sensor("class/power_supply/AC/online", "0")
        snapshot = self.linux_snapshot()
        self.assertIs(snapshot["ac_online"], False)
        self.assertIsNone(snapshot["battery_percent"])

    def test_linux_telemetry_unavailable(self):
        self.cpu.side_effect = PermissionError
        self.memory.side_effect = OSError
        snapshot = self.linux_snapshot()
        self.assertTrue(all(value is None for key, value in snapshot.items() if key != "platform"))

    def test_linux_optional_sensor_errors(self):
        with (
            patch.object(telemetry.platform, "system", return_value="Linux"),
            patch.object(telemetry.psutil, "sensors_battery", side_effect=OSError, create=True),
            patch.object(
                telemetry.psutil, "sensors_temperatures", side_effect=PermissionError, create=True,
            ),
        ):
            snapshot = telemetry.collect_status(self.sysfs)
        self.assertIsNone(snapshot["ac_online"])
        self.assertIsNone(snapshot["battery_percent"])
        self.assertIsNone(snapshot["temperatures"])
        self.assertEqual(snapshot["ram_percent"], 25)

    def windows_snapshot(self, ac, flag, percent, success=1):
        def get_status(pointer):
            status = ctypes.cast(pointer, ctypes.POINTER(telemetry.SystemPowerStatus)).contents
            status.ac_line_status = ac
            status.battery_flag = flag
            status.battery_life_percent = percent
            return success

        windll = SimpleNamespace(kernel32=SimpleNamespace(GetSystemPowerStatus=get_status))
        with (
            patch.object(telemetry.platform, "system", return_value="Windows"),
            patch.object(telemetry.ctypes, "windll", windll, create=True),
        ):
            return telemetry.collect_status(self.sysfs)

    def test_windows_reports_ac_without_battery(self):
        snapshot = self.windows_snapshot(1, 128, 255)
        self.assertIs(snapshot["ac_online"], True)
        self.assertIsNone(snapshot["battery_percent"])
        self.assertIsNone(snapshot["temperatures"])
        self.assertIsNone(snapshot["intel_gpus"])

    def test_windows_reports_discharged_battery(self):
        snapshot = self.windows_snapshot(0, 4, 0)
        self.assertIs(snapshot["ac_online"], False)
        self.assertEqual(snapshot["battery_percent"], 0)

    def test_windows_unknown_and_unsuccessful_readings(self):
        for ac, flag, percent, success in [(255, 0, 255, 1), (255, 255, 40, 1), (1, 4, 30, 0)]:
            with self.subTest(ac=ac, flag=flag, percent=percent, success=success):
                snapshot = self.windows_snapshot(ac, flag, percent, success)
                self.assertIsNone(snapshot["ac_online"])
                self.assertIsNone(snapshot["battery_percent"])


class CliTests(unittest.TestCase):
    snapshot = {
        "platform": "Windows",
        "cpu_percent": 0,
        "ram_percent": 25,
        "ram_total_bytes": 4000,
        "ram_available_bytes": 3000,
        "ac_online": False,
        "battery_percent": None,
        "temperatures": None,
        "intel_gpus": None,
    }

    def capture(self, argv):
        output = io.StringIO()
        with patch("iris_monitor.__main__.collect_status", return_value=self.snapshot):
            with redirect_stdout(output):
                self.assertEqual(main(argv), 0)
        return output.getvalue()

    def test_json_preserves_null_false_and_zero(self):
        self.assertEqual(json.loads(self.capture(["status", "--json"])), self.snapshot)

    def test_text_distinguishes_unavailable_from_zero_and_offline(self):
        output = self.capture(["status"])
        self.assertIn("CPU utilization: 0%", output)
        self.assertIn("AC power: offline", output)
        self.assertIn("Battery charge: unavailable", output)
        self.assertIn("Temperatures: unavailable", output)
        self.assertIn("Intel GPU telemetry: unavailable", output)
