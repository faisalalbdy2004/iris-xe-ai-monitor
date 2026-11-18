import ctypes as ct
import io
import json
import platform
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch

from iris_monitor import dashboard, telemetry, windows_gpu, windows_temperature
from iris_monitor.__main__ import main


class WindowsGpuTests(unittest.TestCase):
    adapters = {
        (0, 0x10A): ("dxgi0", "Intel Iris Xe"),
        (0xFFFFFFFF, 0x10B): ("dxgi1", "Intel Arc"),
    }

    def test_busiest_engine_aggregates_processes_without_summing_engines(self):
        rows = [
            ("pid_1_luid_0x0_0x10A_phys_0_eng_0_engtype_3D", 25),
            ("pid_2_luid_0x0_0x10A_phys_0_eng_0_engtype_3D", 35),
            ("pid_3_luid_0x0_0x10A_phys_0_eng_1_engtype_Copy", 42),
            ("pid_4_luid_0x0_0x10A_phys_1_eng_0_engtype_3D", 50),
            ("pid_1_luid_0xFFFFFFFF_0x10B_phys_0_eng_0_engtype_Copy", 0),
            ("pid_5_luid_0x0_0x10C_phys_0_eng_0_engtype_3D", 100),
            ("pid_6_luid_0x0_0x10A_phys_0_eng_0_engtype_3D", float("nan")),
            ("pid_7_luid_0x0_0x10A_phys_0_eng_0_engtype_3D", -1),
            ("malformed", 100),
        ]
        self.assertEqual(windows_gpu._busiest_engines(rows, self.adapters), {
            (0, 0x10A): 60.0, (0xFFFFFFFF, 0x10B): 0.0,
        })

    def test_query_is_primed_and_missing_rows_keep_inventory(self):
        with (
            patch.object(windows_gpu, "_intel_adapters", return_value=self.adapters),
            patch.object(windows_gpu, "EngineQuery") as query,
        ):
            gpu = windows_gpu.WindowsGpu()
            query.return_value.read.return_value = []
            readings = gpu.read()
            gpu.close()
        query.return_value.prime.assert_called_once_with()
        query.return_value.close.assert_called_once_with()
        self.assertEqual(readings[0], {
            "device": "dxgi0", "name": "Intel Iris Xe", "frequency_mhz": None,
            "utilization_percent": None,
        })

    def test_pdh_missing_counter_closes_query(self):
        def open_query(_source, _user, handle):
            ct.cast(handle, ct.POINTER(windows_gpu.HANDLE))[0] = 1
            return 0

        close = Mock(return_value=0)
        functions = {
            "PdhOpenQueryW": open_query,
            "PdhAddEnglishCounterW": Mock(return_value=1),
            "PdhAddCounterW": Mock(return_value=1),
            "PdhCollectQueryData": Mock(return_value=0),
            "PdhCloseQuery": close,
            "PdhGetFormattedCounterArrayW": Mock(),
        }
        with (
            patch.object(windows_gpu.ct, "WinDLL", create=True),
            patch.object(windows_gpu, "_bind", side_effect=lambda _dll, name, *_: functions[name]),
        ):
            query = windows_gpu.EngineQuery()
            self.assertEqual(query.read(), [])
            query.close()
        close.assert_called_once()
        functions["PdhCollectQueryData"].assert_not_called()

    def test_pdh_formats_only_valid_samples_and_retries_growing_buffer(self):
        names = [ct.create_unicode_buffer("valid"), ct.create_unicode_buffer("invalid")]
        size_bytes = 2 * ct.sizeof(windows_gpu.CounterItem)
        calls = []

        def array(_counter, _format, size, count, buffer):
            calls.append(buffer is None)
            ct.cast(size, ct.POINTER(windows_gpu.DWORD))[0] = size_bytes
            if buffer is None or len(calls) == 2:
                return windows_gpu.PDH_MORE_DATA
            ct.cast(count, ct.POINTER(windows_gpu.DWORD))[0] = 2
            records = (windows_gpu.CounterItem * 2).from_buffer(buffer)
            for index, record in enumerate(records):
                record.name = ct.cast(names[index], ct.c_wchar_p)
                record.formatted.status = 1 if index == 0 else 0xC0000BC6
                record.formatted.value.double = 0 if index == 0 else 77
            return 0

        query = windows_gpu.EngineQuery.__new__(windows_gpu.EngineQuery)
        query.query = query.counter = windows_gpu.HANDLE(1)
        query._collect = Mock(return_value=0)
        query._array = array
        self.assertEqual(query.read(), [("valid", 0.0)])
        self.assertEqual(calls, [True, False, True, False])

    def test_sampler_reuses_and_closes_gpu_query(self):
        gpu = Mock()
        gpu.read.return_value = [{"device": "dxgi0", "frequency_mhz": None,
                                  "utilization_percent": 0}]
        with (
            patch.object(telemetry.platform, "system", return_value="Windows"),
            patch.object(telemetry, "WindowsGpu", return_value=gpu) as factory,
            patch.object(telemetry.ctypes, "windll", create=True),
            patch.object(telemetry, "_windows_power", return_value=(None, None)),
            patch.object(telemetry.psutil, "cpu_percent", return_value=0) as cpu,
        ):
            with telemetry.status_sampler() as sample:
                self.assertEqual(sample()["intel_gpus"], gpu.read.return_value)
                sample()
        factory.assert_called_once()
        gpu.close.assert_called_once()
        self.assertEqual([call.kwargs["interval"] for call in cpu.call_args_list], [0.2, None])

    @unittest.skipUnless(platform.system() == "Windows", "requires Windows system DLLs")
    def test_native_dxgi_and_pdh_return_supported_shapes(self):
        adapters = windows_gpu._intel_adapters()
        self.assertIsInstance(adapters, dict)
        query = windows_gpu.EngineQuery()
        try:
            query.prime()
            self.assertIsInstance(query.read(), list)
        finally:
            query.close()


class WindowsTemperatureTests(unittest.TestCase):
    def test_parses_only_finite_cpu_and_gpu_temperatures(self):
        rows = [
            {"Identifier": "/intelcpu/0/temperature/0", "Name": "CPU Package", "Value": 41.5},
            {"Identifier": "/gpu-intel/1/temperature/0", "Name": "GPU Core", "Value": 0},
            {"Identifier": "/storage/0/temperature/0", "Name": "SSD", "Value": 34},
            {"Identifier": "/intelcpu/0/temperature/1", "Name": "CPU Core", "Value": None},
            {"Identifier": "/intelcpu/0/temperature/2", "Name": "CPU Core", "Value": float("nan")},
            {"Identifier": "/intelcpu/0/temperature/3", "Name": "CPU Core", "Value": True},
        ]
        with (
            patch.dict(windows_temperature.os.environ, {"SystemRoot": "C:/Windows"}),
            patch.object(windows_temperature.subprocess, "run",
                         return_value=SimpleNamespace(stdout=json.dumps(rows))) as run,
        ):
            readings = windows_temperature.read_temperatures()
        self.assertEqual(readings, [
            {"sensor": "librehardwaremonitor/intelcpu", "label": "CPU Package", "celsius": 41.5},
            {"sensor": "librehardwaremonitor/gpu-intel", "label": "GPU Core", "celsius": 0},
        ])
        self.assertEqual(run.call_args.kwargs["timeout"], 3)
        self.assertIn("-NonInteractive", run.call_args.args[0])

    def test_missing_provider_timeout_and_invalid_json(self):
        with (
            patch.dict(windows_temperature.os.environ, {"SystemRoot": "C:/Windows"}),
            patch.object(windows_temperature.subprocess, "run", side_effect=[
                FileNotFoundError, subprocess.CalledProcessError(1, "powershell"),
                subprocess.TimeoutExpired("powershell", 3), SimpleNamespace(stdout="invalid"),
            ]),
        ):
            for _ in range(4):
                self.assertIsNone(windows_temperature.read_temperatures())


class DashboardTests(unittest.TestCase):
    def test_temperature_failure_clears_previous_reading_and_allows_retry(self):
        read = Mock(side_effect=[["reading"], RuntimeError("provider failed"), ["recovered"]])

        def run_immediately(*, target, daemon):
            return SimpleNamespace(start=target, is_alive=lambda: False)

        with (
            patch.object(dashboard, "Thread", side_effect=run_immediately),
            patch.object(dashboard.time, "monotonic", side_effect=[0, 1, 10, 11, 20, 21]),
            dashboard.temperature_sampler(read) as sample,
        ):
            self.assertIsNone(sample())
            self.assertEqual(sample(), ["reading"])
            self.assertEqual(sample(), ["reading"])
            self.assertIsNone(sample())
            self.assertIsNone(sample())
            self.assertEqual(sample(), ["recovered"])

    def test_stuck_temperature_provider_does_not_keep_process_alive(self):
        script = """
from threading import Event
from unittest.mock import patch
from iris_monitor.dashboard import temperature_sampler

started = Event()
blocked = Event()
calls = []

def read():
    calls.append(1)
    started.set()
    blocked.wait()

with patch("iris_monitor.dashboard.time.monotonic", side_effect=[0, 100]):
    with temperature_sampler(read) as sample:
        assert sample() is None
        assert started.wait(2)
        assert sample() is None
        assert calls == [1]
print("sampler exited", flush=True)
"""
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, timeout=8,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "sampler exited")

    def test_redirected_output_has_plain_frames_and_honors_count(self):
        output = io.StringIO()
        sample = Mock(side_effect=["first", "second"])
        with patch.object(dashboard.time, "sleep") as sleep:
            dashboard.watch(sample, lambda reading: [reading], 0.5, 2, output)
        sleep.assert_called_once()
        self.assertEqual(output.getvalue(), "first\n\nsecond\n\n")

    def test_redraw_clips_generator_lines_to_terminal_size(self):
        output = io.StringIO()
        sample = Mock(return_value=["first line", "second line", "hidden"])
        with (
            patch.object(dashboard, "_ansi_output") as ansi,
            patch.object(dashboard.shutil, "get_terminal_size", return_value=(7, 3)),
        ):
            ansi.return_value.__enter__.return_value = True
            dashboard.watch(sample, lambda frame: (line for line in frame), 1, 1, output)
        self.assertEqual(
            output.getvalue(), "\x1b[?1049h\x1b[?25l\x1b[H\x1b[J"
            "first \nsecond\n\x1b[?25h\x1b[?1049l",
        )

    def test_interrupt_restores_terminal(self):
        output = io.StringIO()
        with (
            patch.object(dashboard, "_ansi_output") as ansi,
            self.assertRaises(KeyboardInterrupt),
        ):
            ansi.return_value.__enter__.return_value = True
            dashboard.watch(Mock(side_effect=KeyboardInterrupt), lambda reading: [], 1, None, output)
        self.assertTrue(output.getvalue().endswith("\x1b[?25h\x1b[?1049l"))

    def test_cli_rejects_non_finite_interval_and_zero_count(self):
        for arguments in (["--interval", "nan"], ["--interval", "inf"], ["--count", "0"]):
            with self.subTest(arguments=arguments), self.assertRaises(SystemExit) as raised:
                with patch("sys.stderr", new=io.StringIO()):
                    main(["watch", *arguments])
            self.assertEqual(raised.exception.code, 2)

    def test_status_keeps_legacy_fields_and_emits_windows_utilization(self):
        output = io.StringIO()
        snapshot = {
            "platform": "Windows", "cpu_percent": 1, "ram_percent": 2,
            "ram_total_bytes": 50, "ram_available_bytes": 49, "ac_online": False,
            "battery_percent": 0, "temperatures": None, "intel_gpus": [
                {"device": "dxgi0", "name": "Intel Iris Xe", "frequency_mhz": None,
                 "utilization_percent": 0},
            ],
        }
        with patch("iris_monitor.__main__.collect_status", return_value=snapshot) as collect:
            with redirect_stdout(output):
                main(["status", "--json", "--lhm"])
        collect.assert_called_once_with(lhm=True)
        self.assertEqual(json.loads(output.getvalue()), snapshot)
