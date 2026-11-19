# Contributing to CorePulse

CorePulse is an open-source, read-only hardware monitor in development for Windows and Linux. The [development preview](README.md#development-preview) lists the active previews and review branches.

## Report a bug or propose a change

1. [Open an issue](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/issues) before starting a major change.
2. Include the branch and commit, operating system and version, relevant hardware and driver, exact command, expected result and observed result. For desktop issues on Linux, include the compositor and whether the session uses Wayland or X11.
3. For sensor comparisons or performance measurements, include the workload, sampling interval, measurement duration and reference tool. Use aligned sampling windows when comparing counters. Remove secrets and personal or device identifiers from shared output.

## Submit a pull request

- Base documentation changes on `main`. For prototype changes, target the branch that owns the feature and state the target branch in the PR.
- Keep monitoring read-only. Preserve real zero readings and report unavailable data explicitly.
- Include reproducible steps and the checks you ran. For Python changes, install the package and run `python -m unittest discover -s tests -v` with the same interpreter. For Rust changes, run `cargo test --manifest-path rust-monitor/Cargo.toml --locked` and repeat with `--features gui` when changing the desktop.
- Label experimental features and describe the hardware and environments you tested.

CorePulse uses the [MIT License](LICENSE).
