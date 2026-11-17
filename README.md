# Iris Xe AI Monitor

## IT'S FREE FOR THE TAKING! — FREE & OPEN SOURCE

**Free to use. Free to study. Free to modify. Free to share.**

A read-only terminal monitor for Windows and Linux. Version 0.2.0 adds live
monitoring, Windows Intel GPU utilization where counters are available, and
optional Windows temperature readings. A desktop dashboard and local AI
inference benchmarks are future goals.

## Run from a checkout

Requires Python 3.10 or later. The monitor runs as a regular user and reads OS
telemetry without changing power settings, fan curves, firmware, or partitions.

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\iris-monitor.exe status
.\.venv\Scripts\iris-monitor.exe status --json
.\.venv\Scripts\iris-monitor.exe watch --interval 1
```

### Linux

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/iris-monitor status
.venv/bin/iris-monitor status --json
.venv/bin/iris-monitor watch --interval 1
```

With the virtual environment active, you can also run `python -m iris_monitor status`.
Press Ctrl+C to exit `watch`. The default interval is one second. Use
`watch --count 3` for a bounded run. Redirected output uses plain text with one
frame per refresh.

## Readings

| Reading | Windows | Linux |
| --- | --- | --- |
| CPU utilization and RAM | psutil | psutil |
| AC power and battery charge | Windows system power status API | Power supply sysfs and psutil battery data |
| CPU / GPU temperatures | Optional Libre Hardware Monitor WMI provider via `--lhm` | Hardware sensors exposed through psutil |
| Intel GPU utilization | WDDM GPU Engine counters associated with Intel DXGI adapters | Unavailable |
| Intel GPU frequency | Unavailable | Actual GT0 clock from legacy i915, per-GT i915, or Xe sysfs where exposed |

The first CPU reading uses a 0.2-second sample. Later dashboard readings use
the time since the previous sample. RAM sizes are in bytes, temperatures in
Celsius, and GPU frequency in MHz.

Windows GPU utilization represents the busiest engine for each Intel adapter.
The monitor sums process counters for each engine and reports the highest engine
value. It requires a WDDM driver exposing usable counter samples. The GPU name
can appear with unavailable utilization when Windows supplies no valid samples.
To check the reading, compare its trend with Task Manager's GPU Performance page
during a normal graphics workload. Different sampling windows can yield different
values. [Microsoft's GPU utilization methodology](https://devblogs.microsoft.com/directx/gpus-in-the-task-manager/)

### Optional Windows temperatures

If you already run Libre Hardware Monitor and it exposes the local
`root\LibreHardwareMonitor` WMI namespace, pass `--lhm` to `status` or `watch`.
Some sensors require elevation in the provider or are absent on particular
hardware, including some Intel integrated GPUs. Iris Xe AI Monitor runs as a
regular user and queries the provider only when requested. No web server or
additional service is required. The dashboard fetches these readings in the
background at most once per 10 seconds. [Libre Hardware Monitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor)

```powershell
.\.venv\Scripts\iris-monitor.exe status --json --lhm
.\.venv\Scripts\iris-monitor.exe watch --lhm
```

### JSON compatibility

The top-level keys and existing field types are unchanged. Text shows
`unavailable` for missing readings. JSON uses `null` and preserves real zeros
and `false` for offline AC. Windows can now populate the existing `intel_gpus`
array. Its entries preserve `device` and `frequency_mhz` and add `name` and
`utilization_percent`. Linux entries keep their v0.1.0 shape. The command
succeeds when optional readings are unavailable.

## Tests and contributions

After installing the package, run `python -m unittest discover -s tests -v`
using the virtual environment's Python. Sensor tests use mocks and temporary
sysfs fixtures. A Windows-only smoke test exercises native APIs without
requiring a specific GPU or valid engine samples. GitHub Actions installs the
package and exercises both snapshot formats and a bounded dashboard run on
Windows and Linux.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution process.

## License

Released under the [MIT License](LICENSE). Keep the copyright and license notices when redistributing the project.
