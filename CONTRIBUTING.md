# Contributing to Iris Xe AI Monitor

Thanks for helping build an open-source, lightweight Linux dashboard for local AI inference on Intel integrated graphics.

## Project status

This is an experimental project in its planning stage. Hardware compatibility, GPU acceleration, and performance claims must be tested before they are presented as verified.

## How to contribute

1. Open an issue describing a bug or feature proposal before major changes.
2. Keep monitoring read-only by default. Do not change fan curves, power limits, firmware, or disk partitions.
3. Include reproducible steps and tests for code changes.
4. For benchmarks, report hardware model, kernel, driver, inference backend, model and quantization, exact settings, and measurement methodology.
5. Never commit passwords, tokens, personal data, or identifiable device information.
6. Use pull requests for proposed changes and explain what was tested.

## Initial priorities

- Linux CPU, memory, thermal, and power telemetry with graceful handling of unavailable sensors.
- Repeatable llama.cpp CPU, Vulkan, and SYCL benchmarks.
- A responsive dashboard with minimal monitoring overhead.
- Clear documentation, tests, and safe defaults.

The project is MIT-licensed. Contributions are welcome.
