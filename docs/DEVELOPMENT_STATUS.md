# CorePulse development status

Development continues on `experiment/rust-native` in [draft PR #6](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/pull/6). [PR #4](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/pull/4) is the Python reference.

## Verified baseline

- Commit `35ae0f4432af06714e89f9789bcea9775d133a13` shipped the optional CorePulse desktop with two themes, bounded histories, and minimized sampling pause.
- Windows passed 6 headless and 8 GUI-feature tests. Ubuntu passed 7 headless and 9 GUI-feature tests. [Rust CI](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/actions/runs/44211345625)
- Windows laptop GUI CPU was 8.75% of one core idle, 27.80% with pointer input, and 0.16% minimized. RSS was 110.70, 114.95, and 115.39 MiB. Windows CLI RSS was 13.73 MiB at one-second polling.
- Over 12 aligned Windows windows, median absolute differences were 0.371 percentage points versus PDH Processor Time and 0.002 points versus a separate PDH Intel GPU busiest-engine query. Ubuntu matched psutil within 0.050 points over eight windows. Direct Task Manager access was blocked.

## Current work

Move telemetry wakeups off the UI repaint timer and batch contiguous chart geometry. Compare CPU, RSS, and GPU activity on matched desktop workloads before deciding whether to change the renderer. The optional `COREPULSE_GUI_TRACE` diagnostic prints total UI updates and consumed snapshots on exit. `COREPULSE_GUI_VSYNC=0` allows a measured renderer comparison without touching OS settings.

Unsupported readings include Windows temperatures and GPU clock, and Linux GPU utilization. AMD and NVIDIA GPU adapters are outside the verified scope.

## Resume

```text
git fetch origin
git switch experiment/rust-native
git pull --ff-only
cargo fmt --manifest-path rust-monitor/Cargo.toml --check
cargo test --manifest-path rust-monitor/Cargo.toml --locked
cargo test --manifest-path rust-monitor/Cargo.toml --locked --features gui
cargo clippy --manifest-path rust-monitor/Cargo.toml --locked --all-targets --all-features
```

Use the [benchmark instructions](../rust-monitor/README.md) to build separate CLI and GUI release binaries, compare counters, and record idle, active, and minimized desktop measurements. Update this file and draft PR #6 after retrieving the CI artifacts and running the Windows hardware benchmark.
