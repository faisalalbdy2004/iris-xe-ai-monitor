# Iris Xe AI Monitor Rust experiment

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

`watch` prints successive frames and accepts `--count` for a bounded run. Its
one-shot JSON uses the Python v0.2 top-level keys and sensor record shapes,
including JSON `null` for unavailable readings. The GUI feature uses eframe
with its Glow renderer, and requires a working desktop OpenGL context. The
headless build excludes eframe and does not initialize a graphics renderer.

## Sensor coverage

| Reading | Windows | Linux |
| --- | --- | --- |
| CPU and RAM | sysinfo OS counters | sysinfo OS counters |
| AC and battery | GetSystemPowerStatus | sysfs power supply state and battery capacity |
| Intel GPU | DXGI adapter inventory and PDH busiest-engine utilization | Actual GT0 frequency from i915 or Xe sysfs |
| Temperatures | Unavailable in the Rust prototype | Exposed hwmon temperature channels |

Windows GPU utilization uses the highest engine load after summing process
samples for each adapter and engine. Missing PDH samples produce `null`.
Linux utilization and Windows GPU clock and temperature remain unavailable.
The Rust Linux battery reader uses the first reported battery capacity. It
does not aggregate multiple batteries or infer AC state from battery status.

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
reported separately from a measured zero difference.
