# CorePulse development status

Development continues on `experiment/rust-native` in [draft PR #6](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/pull/6). [PR #4](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/pull/4) is the Python reference.

## Latest verified code

Phase 3 code `3228b4415bebf66ae0e01025dd3bd4d549f70c5d` adds per-phase eframe profiling, skips drawing absent and clipped graphs, improves caption contrast, and extends reference checks to RAM, battery, AC, and temperature availability. Formatting and Clippy passed without warnings. Windows passed 6 headless and 8 GUI tests. Ubuntu passed 7 headless and 9 GUI tests. The Python matrix passed all 10 jobs. [Rust CI](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/actions/runs/44394437221) · [Python CI](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/actions/runs/44394437545)

### Phase 3 measurements

Each cell shows CPU as a percentage of one core, followed by median RSS in MiB. Windows used ten-second phases on Iris Xe. Ubuntu used six-second phases under software-rendered Xvfb, using the previously recorded run as its baseline.

| Build | Idle CPU / RSS | Pointer CPU / RSS | Minimized CPU / RSS |
| --- | ---: | ---: | ---: |
| Windows fresh baseline | 16.55 / 98.60 | 16.56 / 107.74 | 0.16 / 99.24 |
| Windows Phase 3 | 0.62 / 106.55 | 19.37 / 108.84 | 0.16 / 112.20 |
| Ubuntu prior | 3.00 / 113.43 | 43.30 / 113.43 | 0.00 / 113.43 |
| Ubuntu Phase 3 | 2.33 / 114.11 | 32.15 / 114.11 | 0.00 / 114.11 |

Windows idle has varied across baseline runs. The new Windows run used more CPU during pointer input and more RSS across all phases. The Ubuntu pointer result was lower in this trial. Both desktops minimized, restored, and closed normally.

Separate six-second instrumented runs logged 12 idle, 275 pointer, and zero minimized updates on Windows. Ubuntu logged 12, 183, and zero. Median preceding-frame time was 747 µs idle and 531 µs during pointer input on Windows, and 718 µs and 634 µs on Ubuntu. The pinned egui-winit requests repaint for cursor movement before app update. The Glow frame timer excludes buffer swaps. These figures locate the increase in update frequency and leave presentation costs unmeasured. [egui-winit event handling](https://docs.rs/crate/egui-winit/0.33.3/source/src/lib.rs) · [eframe Glow frame timing](https://docs.rs/crate/eframe/0.33.3/source/src/native/glow_integration.rs)

On Windows, ten aligned comparisons against OS references measured median absolute differences of 0.300 percentage points for PDH Processor Time, 0.006 for a separate WDDM busiest-engine query, and 0.021 for RAM. Battery percentage and AC matched in all ten pairs. Ubuntu measured 0.048 points for CPU and 0.023 for RAM over eight pairs. Neither Linux battery nor AC had reference pairs. Temperature availability agreed across all comparisons. Temperature accuracy was outside this measurement.

[Arch and Hyprland validation plan](ARCH_HYPRLAND.md) covers native Wayland, Intel driver and Mesa checks, fractional scaling, and the read-only hardware checklist. The target Arch/Hyprland/Noctalia session remains untested.

- `ed351c36bfb24b78d00344ed93848cbdacac2f6d` moved telemetry deadlines from UI repaint timers to the existing sampler worker. New samples request redraws. Each chart emits one path per contiguous run of readings. Missing data remains a gap.
- `6002c97b4e772de0f61a9be062903c5050c032bc` clarified the stroke width types and passed formatting and Clippy without warnings. Windows passed 6 headless and 8 GUI tests. Ubuntu passed 7 headless and 9 GUI tests. Both GUI benchmark hosts restored and closed the window. [Rust CI](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/actions/runs/44213859019) · [Python CI](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/actions/runs/44213859301)
- Dark and light themes, responsive layouts, bounded histories, and minimized pause are available. The headless CLI remains independent of the renderer.

## Benchmarks

CPU is percent of one core. Each desktop cell is CPU percent / median RSS in MiB / median observed process busiest-engine GPU percent. Windows used 10-second phases on an Iris Xe laptop. Hosted Ubuntu used six-second phases under software-rendered Xvfb, so GPU overhead was unavailable.

| Build | Idle | Pointer input | Minimized | Visible startup |
| --- | ---: | ---: | ---: | ---: |
| Windows Phase 2 fresh baseline | 11.87 / 101.50 / 0.53 | 16.71 / 104.47 / 3.83 | 0.16 / 104.69 / 0.00 | 210.08 ms |
| Windows checkpoint, default VSync | 0.47 / 109.91 / 0.12 | 16.40 / 109.15 / 3.75 | 0.62 / 102.88 / 0.00 | 1294.55 ms |
| Windows final, default VSync | 1.56 / 109.29 / 0.43 | 16.40 / 112.12 / 3.73 | 0.31 / 108.09 / 0.00 | 1370.08 ms |
| Windows checkpoint, VSync off | 1.09 / 99.77 / 0.46 | 8.12 / 102.61 / 3.96 | 0.00 / 97.80 / 0.00 | 252.23 ms |
| Ubuntu Phase 2 | 5.83 / 113.89 / unavailable | 44.14 / 113.90 / unavailable | 0.00 / 113.90 / unavailable | 459.70 ms |
| Ubuntu final | 3.00 / 113.43 / unavailable | 43.30 / 113.43 / unavailable | 0.00 / 113.43 / unavailable | 4430.80 ms |

The Windows idle slowdown was reduced in these trials. The final run exceeded the 1% target. Visible input CPU stayed close to the fresh baseline with VSync enabled, and Windows GUI RSS increased in the default trials. Launch timing varied widely, so startup improvements are unproven. VSync remains enabled by default. The final Windows trace counted 351 UI updates and 23 consumed snapshots across all phases.

The unchanged Windows Rust CLI measured 10.37 ms warm help startup, 388.74 ms warm JSON snapshot, and 13.88 MiB RSS at one-second polling. Hosted Ubuntu measured 1.39 ms, 201.56 ms, and 2.76 MiB. Short CPU windows have coarse accounting granularity.

On the Windows host, ten aligned samples differed by a median of 0.122 percentage points from psutil and 1.323 points from PDH Processor Time. The Intel GPU median difference was 0.000 points against a separate PDH query, with a 0.011-point maximum. Both GPU queries read WDDM busiest-engine data. Ubuntu's eight aligned psutil samples differed by 0.001 points median and 0.251 maximum.

## Limitations and next step

Windows temperatures and GPU clocks, Linux GPU utilization, and AMD and NVIDIA GPU adapters remain outside verified support. Direct Task Manager access was blocked. The next milestone is to isolate presentation time and test upstream pointer-event coalescing while preserving clicks, hover, keyboard input, and resizing.

## Resume on Windows 11

Run from the repository root in PowerShell with the Rust MSVC toolchain and the existing Python reference installed in `.venv`.

```powershell
git fetch origin
git switch experiment/rust-native
git pull --ff-only
cargo fmt --manifest-path rust-monitor/Cargo.toml --check
cargo clippy --manifest-path rust-monitor/Cargo.toml --locked --all-targets --all-features
cargo test --manifest-path rust-monitor/Cargo.toml --locked --features gui
cargo build --manifest-path rust-monitor/Cargo.toml --locked --release
cargo build --manifest-path rust-monitor/Cargo.toml --locked --release --features gui --target-dir rust-monitor/target/gui
$cli = ".\rust-monitor\target\release\iris-monitor-rs.exe"
$gui = ".\rust-monitor\target\gui\release\iris-monitor-rs.exe"
& $cli status --json
& $gui gui
```

Close the GUI before running the measurement commands.

```powershell
.\.venv\Scripts\python.exe rust-monitor/validate.py --rust-monitor $cli --count 10
.\.venv\Scripts\python.exe rust-monitor/benchmark.py --python-monitor .\.venv\Scripts\iris-monitor.exe --rust-monitor $cli --repeats 10 --watch-seconds 10
$env:COREPULSE_GUI_TRACE = "1"
.\.venv\Scripts\python.exe rust-monitor/gui_benchmark.py --rust-monitor $gui --seconds 10
.\.venv\Scripts\python.exe rust-monitor/gui_benchmark.py --profile --rust-monitor $gui --seconds 6
```

Set `$env:COREPULSE_GUI_VSYNC = "0"` for the VSync-off comparison in that shell. See the [reproduction guide](../rust-monitor/README.md) for Linux and sensor coverage.
