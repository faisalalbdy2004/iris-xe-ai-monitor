# CorePulse

**Read-only hardware monitoring for Windows and Linux.** See CPU load, memory use, battery and AC status, and the GPU and temperature readings your system exposes. CorePulse is developed in the `iris-xe-ai-monitor` repository and aims to keep the monitor's own resource use low.

[![Python preview tests](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/actions/workflows/tests.yml/badge.svg?branch=feat%2Fmonitor-v0.2.0&event=pull_request)](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/actions/workflows/tests.yml?query=branch%3Afeat%2Fmonitor-v0.2.0+event%3Apull_request)
[![Rust experiment checks](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/actions/workflows/rust-experiment.yml/badge.svg?branch=experiment%2Frust-native&event=pull_request)](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/actions/workflows/rust-experiment.yml?query=branch%3Aexperiment%2Frust-native+event%3Apull_request)

[Try the terminal monitor](#try-the-python-terminal-monitor) · [Build the desktop](#build-the-experimental-rust-desktop) · [Roadmap](#roadmap) · [Contribute](#contributing)

## Development status

`main` contains project documentation. There are currently no published GitHub Releases. Use one of the source branches below to try a preview. The CI badges refer to the Python and Rust preview branches.

| Track | What you can try | Status |
| --- | --- | --- |
| [Python CLI foundation](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/pull/2) | Text and JSON snapshots of available readings | Open for review |
| [Python v0.2 terminal preview](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/pull/4) | Live terminal dashboard, expanded Intel telemetry and optional Windows temperatures | Open for review, based on the CLI foundation |
| [Rust CLI and desktop](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/pull/6) | Native sampling, terminal snapshots and an optional egui dashboard with charts | Draft, based on the Python v0.2 branch |
| [Wayland redraw experiment](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/blob/review/experimental-wayland-redraw/docs/EXPERIMENTAL_WAYLAND_REDRAW.md) | Opt-in redraw scheduling for native Linux Wayland | Separate experimental branch, with an Intel/KWin smoke test |

The Rust checkpoint documents sensor comparisons on a Windows 11 Iris Xe laptop and Ubuntu checks using a software-rendered virtual display. Idle overhead improved in measured trials, while CPU use during pointer movement remains an open performance issue. [Measurements, test results and limitations](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/blob/experiment/rust-native/docs/DEVELOPMENT_STATUS.md)

## Hardware and sensor coverage

| Reading | Windows previews | Linux previews |
| --- | --- | --- |
| CPU, memory and power | CPU load, RAM, AC status and battery charge where available | CPU load, RAM, AC status and battery charge where available |
| Intel graphics | Iris Xe is the initial testing focus. Utilization uses the busiest reported engine through WDDM when usable counters are available. | Actual Intel GPU frequency where i915 or Xe exposes it. GPU utilization is currently unavailable. |
| Temperatures | Python v0.2 supports optional Libre Hardware Monitor readings. Rust temperatures are unavailable. | Sensors exposed through the OS, with coverage dependent on hardware and drivers. |
| AMD and NVIDIA graphics | GPU adapters and validation are planned. | GPU adapters and validation are planned. |

Missing readings appear as `unavailable` in text or `null` in JSON. CorePulse reads telemetry and leaves fan curves, power limits and firmware settings alone.

## Try the Python terminal monitor

Install Git and Python 3.10 or later. Clone the v0.2 preview branch and enter the checkout.

```sh
git clone --branch feat/monitor-v0.2.0 https://github.com/faisalalbdy2004/iris-xe-ai-monitor.git corepulse-terminal
cd corepulse-terminal
```

**Linux**

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/iris-monitor status --json
.venv/bin/iris-monitor watch --interval 1 --count 3
```

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\iris-monitor.exe status --json
.\.venv\Scripts\iris-monitor.exe watch --interval 1 --count 3
```

Run `status` without `--json` for a text snapshot. Omit `--count 3` for continuous monitoring and press Ctrl+C to stop. For optional Windows temperatures, see the `--lhm` setup in the [Python preview README](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/tree/feat/monitor-v0.2.0#optional-windows-temperatures).

## Build the experimental Rust desktop

Install Git and a current stable Rust toolchain with Cargo and your platform's linker. The desktop requires a working OpenGL context. On Linux it supports X11 or Wayland and needs libxkbcommon, plus libxkbcommon-x11 when using X11.

```sh
git clone --branch experiment/rust-native https://github.com/faisalalbdy2004/iris-xe-ai-monitor.git corepulse-rust
cd corepulse-rust
cargo run --manifest-path rust-monitor/Cargo.toml --locked --release --features gui -- gui
```

Run a headless snapshot from the same checkout.

```sh
cargo run --manifest-path rust-monitor/Cargo.toml --locked --release -- status --json
```

The desktop shows live charts with gaps where readings are missing. See the [Rust build and validation guide](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/tree/experiment/rust-native/rust-monitor) for tests, watch mode and benchmarks, and the [Arch/Hyprland acceptance guide](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/blob/experiment/rust-native/docs/ARCH_HYPRLAND.md) for compositor testing.

## Roadmap

- [x] Prototype Python snapshots and a live terminal dashboard.
- [x] Prototype a native Rust CLI and a desktop dashboard with live charts.
- [x] Record initial sensor comparisons and desktop overhead measurements.
- [ ] Validate sensor accuracy and overhead across more Intel systems, drivers and Linux compositors.
- [ ] Reduce desktop rendering overhead during input and validate the opt-in Wayland scheduler.
- [ ] Build and test Windows and Linux release packages.
- [ ] Expand Intel coverage and implement and validate AMD and NVIDIA GPU adapters.

## Contributing

Hardware reports are welcome. Include the branch or commit, OS, GPU model and driver, the command you ran and the reading you expected. If you share a benchmark, include the sampling interval, workload and reference tool.

[Open an issue](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/issues/new) · [Read the contribution guide](CONTRIBUTING.md)

## License

CorePulse is available under the [MIT License](LICENSE).
