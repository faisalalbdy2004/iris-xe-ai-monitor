# Iris Xe AI Monitor

## IT'S FREE FOR THE TAKING! — FREE & OPEN SOURCE

**Free to use. Free to study. Free to modify. Free to share.**

An experimental, read-only terminal monitor for Windows and Linux. Version 0.1.0 takes a snapshot of CPU, RAM, and available power, temperature, and Intel GPU readings. A desktop dashboard and local AI inference benchmarks are future goals.

## Run from a checkout

Requires Python 3.10 or later. The monitor runs as a regular user and reads OS telemetry without changing power settings, fan curves, firmware, or partitions.

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\iris-monitor.exe status
.\.venv\Scripts\iris-monitor.exe status --json
```

### Linux

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/iris-monitor status
.venv/bin/iris-monitor status --json
```

With the virtual environment active, you can also run `python -m iris_monitor status`.

## Readings

| Reading | Windows | Linux |
| --- | --- | --- |
| CPU utilization and RAM | psutil | psutil |
| AC power and battery charge | Windows system power status API | Power supply sysfs and psutil battery data |
| Hardware temperatures | Unavailable in this prototype | Sensors exposed through psutil |
| Intel GPU frequency | Unavailable in this prototype | Actual clock frequency when i915 exposes `gt_act_freq_mhz` |

CPU utilization is sampled over 0.2 seconds. RAM sizes are in bytes, temperatures in Celsius, and GPU frequency in MHz. Sensor availability depends on hardware, drivers, and read permissions. GPU utilization is outside the scope of this prototype.

Text output shows `unavailable` for missing readings. JSON uses `null` and preserves real zeros and `false` for offline AC. On Linux, `intel_gpus` lists detected Intel DRM cards, with a `null` frequency where the driver provides none. The command succeeds when optional readings are unavailable.

## Tests and contributions

After installing the package, run `python -m unittest discover -s tests -v` using the virtual environment's Python. Sensor tests use mocks and temporary sysfs fixtures. GitHub Actions also installs the package and runs both CLI formats on Windows and Linux.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution process.

## License

Released under the [MIT License](LICENSE). Keep the copyright and license notices when redistributing the project.
