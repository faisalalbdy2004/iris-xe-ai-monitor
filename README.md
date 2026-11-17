# Iris Xe AI Monitor

# IT'S FREE FOR THE TAKING! — FREE & OPEN SOURCE

**Free to use. Free to study. Free to modify. Free to share.**

An open-source **Windows and Linux** project for monitoring and benchmarking local AI inference on Intel integrated GPUs, including Iris Xe.

## Project status

**Early development — experimental.** The application has not been implemented or validated yet. Windows and Linux are *targets*, not claims of working compatibility. GPU acceleration and sensor availability depend on drivers, hardware and OS.

## Planned interfaces

- **Desktop application:** A cross-platform graphical dashboard built with Python and Qt (PySide6).
- **Command-line interface:** A lightweight terminal tool for readings, repeatable benchmarks and machine-readable exports.
- **Shared core:** Both interfaces will use the same Python telemetry, benchmark and result-storage modules.

Planned CLI examples (not available yet):

```sh
iris-monitor status
iris-monitor benchmark
iris-monitor export results.json
```

## Cross-platform design

| Area | Windows | Linux |
| --- | --- | --- |
| CPU and RAM | Portable Python APIs | Portable Python APIs |
| Temperature and GPU counters | Windows-specific sensor or Intel tooling where supported | sysfs, hwmon and Intel GPU tooling where supported |
| AC/battery status | OS power API | Linux power_supply interfaces |
| AI benchmarks | llama.cpp executable for Windows | llama.cpp executable for Linux |
| GUI | PySide6 | PySide6 |

Sensors must report **unavailable** when unsupported rather than inventing values. Platform-specific capabilities will be documented and tested independently. The monitoring app will be **read-only by default**; it will not alter fan curves, CPU power limits, firmware, or partitions.

## Project goals

- Read-only monitoring of CPU, integrated GPU, memory, temperatures and power when supported.
- Reproducible CPU, Vulkan and (when supported) SYCL local AI benchmarks.
- Clear performance comparisons and lightweight visualization.
- Safe defaults, documentation, automated tests and community contributions.

## Contribute

Ideas, bug reports, benchmarks and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Released under the [MIT License](LICENSE). You may use, modify, redistribute and sell copies under MIT license terms, including retaining required copyright and license notices. **Free to take doesn't mean the license has no conditions.**
