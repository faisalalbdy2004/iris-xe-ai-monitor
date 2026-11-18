# CorePulse desktop experiment

**IT’S FREE FOR THE TAKING! FREE & OPEN SOURCE.** This MIT-licensed proof of concept
lives beside the Python v0.2 application. The CLI and GUI share one sampler.

## Build and run

With a Rust toolchain already available, from the repository root:

```sh
cargo run --manifest-path rust-monitor/Cargo.toml --release -- status --json
cargo run --manifest-path rust-monitor/Cargo.toml --release -- watch --interval 1
cargo run --manifest-path rust-monitor/Cargo.toml --release --features gui -- gui
cargo test --manifest-path rust-monitor/Cargo.toml
```

`watch` prints successive frames and accepts `--count` for a bounded run.
`watch --json` writes one snapshot per line. Both JSON commands preserve the
Python v0.2 top-level keys and write `null` for unavailable readings. The GUI feature uses eframe
with its Glow renderer, and requires a working desktop OpenGL context. The
headless build excludes eframe and does not initialize a graphics renderer.
On Linux the GUI uses X11 or Wayland, libxkbcommon, and a desktop OpenGL
implementation. Its X11 backend also uses libxkbcommon-x11.
The desktop offers dark and light themes, 60-sample CPU and GPU histories
with gaps for missing readings, and stacked cards at narrow widths. Its
single worker polls on demand. The desktop requests a sample every one second
while focused, two seconds when unfocused, and five seconds when minimized
if the backend still supplies frames. A backend that suspends minimized
frames also suspends polling.

## Sensor coverage

| Reading | Windows | Linux |
| --- | --- | --- |
| CPU and RAM | GetSystemTimes and GlobalMemoryStatusEx | /proc/stat and /proc/meminfo |
| AC and battery | GetSystemPowerStatus | sysfs power supply state and battery capacity |
| Intel GPU | DXGI adapter inventory and PDH busiest-engine utilization | Actual GT0 frequency from i915 or Xe sysfs |
| Temperatures | Unavailable in the Rust prototype | Exposed hwmon temperature channels |

Windows GPU utilization uses the highest engine load after summing process
samples for each adapter and engine. Missing PDH samples produce `null`.
The Windows JSON entry has `utilization_scope: "busiest_engine"`. It is the
highest observed engine load, in percent, for that adapter. Total engine
utilization is unavailable. A counter interval with invalid values or an
impossible combined engine percentage is unavailable.
Linux utilization and Windows GPU clock and temperature remain unavailable.
The Rust Linux battery reader uses the first reported battery capacity. It
does not aggregate multiple batteries or infer AC state from battery status.
Temperatures at or below absolute zero are discarded.
Windows CPU utilization is unavailable on hosts with multiple processor groups,
where a single GetSystemTimes call cannot represent all CPUs.
CPU percentages require two valid counter reads at least 100 ms apart.
Regressing counters, an unchanged total, and failed reads yield `null`.
Hardware reads sit behind a platform interface. Intel is the only GPU vendor
implemented in this experiment.

[DXGI adapter descriptions](https://learn.microsoft.com/en-us/windows/win32/api/dxgi/ns-dxgi-dxgi_adapter_desc1)
· [PDH counter arrays](https://learn.microsoft.com/en-us/windows/win32/api/pdh/nf-pdh-pdhgetformattedcounterarrayw)
· [Windows busiest-engine methodology](https://devblogs.microsoft.com/directx/gpus-in-the-task-manager/)
· [Linux Xe frequency interface](https://docs.kernel.org/gpu/xe/xe_gt_freq.html)

## Repeat the comparison

Build the release CLI and install Python v0.2 in a project virtual environment.
Use the installed executable paths with this command:

```sh
python rust-monitor/benchmark.py --python-monitor /path/to/iris-monitor --rust-monitor /path/to/iris-monitor-rs --repeats 10 --watch-seconds 10
```

Use the `.exe` paths on Windows. The benchmark alternates warmed startup runs
for `--help` and `status --json`. Snapshot timing includes the intentional CPU
sampling interval. It then observes each CLI for ten seconds at 5-second and
1-second polling intervals, with plain-text output drained through a pipe.
Median resident memory and CPU time include the launcher and its descendants.
Summed RSS can double-count shared pages. Extra CPU time per additional frame
is an estimate from those two windows. Values near the OS accounting resolution
are inconclusive. Measurements cover the CLI only.

Concurrent snapshot pairs report agreement, in each metric's own units, on
readings both implementations expose. They are not an independent accuracy
reference and the sample windows are not identical. Zero matched samples are
reported separately from a measured zero difference. Repeated temperature
labels are excluded when they cannot identify one sensor on each side.

### Compare CPU and GPU counters on adjacent intervals

Install the Python v0.2 reference into the active virtual environment, then run:

```sh
python rust-monitor/validate.py --rust-monitor /path/to/iris-monitor-rs --interval 1 --count 12
```

The script primes its OS references on the first JSON frame and samples them
as subsequent frames arrive. Linux uses psutil's aggregate CPU reference.
Windows also samples PDH Processor Time, Processor Utility, and GPU Engine
counters through separate queries. The report keeps time-based CPU utilization
and utility separate. Your Windows build can expose both metrics in Task
Manager. To compare visually, open **Performance > CPU** and **Performance >
GPU**, then compare synchronized trends during the same steady workload.
The script reports no paired values when a counter is missing. Both GPU
readers use WDDM, so agreement verifies the implementation against that
counter source. It cannot establish accuracy against an independent GPU trace.
[Task Manager's CPU metric change](https://blogs.windows.com/windows-insider/2025/02/28/announcing-windows-11-insider-preview-build-26120-3360-dev-and-beta-channels/)

### Measure the desktop separately

Build the GUI release binary and run the measurement driver:

```sh
cargo build --manifest-path rust-monitor/Cargo.toml --locked --release --features gui
python rust-monitor/gui_benchmark.py --rust-monitor /path/to/gui-enabled/iris-monitor-rs --seconds 10
```

Run the Windows test in an interactive desktop session. On Linux run it on
an isolated X11 display with a window manager, `xdotool`, and `xprop`. CI uses
Xvfb with Openbox and software OpenGL. The driver records time to a visible
window and samples the GUI process's CPU and RSS with no input, while sending
pointer input, and after confirming minimization. Windows GPU cost is the
GUI process's observed busiest-engine counter where PDH supplies it. A
missing counter and the Linux virtual display GPU measurement report `null`.
Startup excludes build time and ends when the window becomes visible, before
sensor readiness is guaranteed.
