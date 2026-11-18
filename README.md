<div align="center">

# ⚡ CorePulse

### IT'S FREE FOR THE TAKING! — FREE & OPEN SOURCE

**A lightweight, cross-platform hardware monitor for Windows and Linux.**

*Know your hardware. Keep your resources.*

**CPU · GPU · Memory · Battery · Sensors · Live charts**

</div>

---

> **Development preview — not a stable release.** CorePulse is the working product name for this project, which is still hosted in the `iris-xe-ai-monitor` repository. Hardware support and performance vary by system; see the status below.

## Why CorePulse?

A monitor shouldn't become the workload. CorePulse aims to show useful system information with **minimal CPU, RAM, and GPU overhead**, clear reporting, and no unnecessary background services.

- 🪶 **Lightweight by design** — benchmark the monitor's own resource consumption.
- 🖥️ **Windows + Linux** — platform-specific sensor adapters with shared interfaces.
- 📊 **Desktop + terminal** — graphical dashboard and script-friendly CLI.
- 🔍 **Honest measurements** — unsupported readings say **unavailable**, never invented values.
- 🔓 **Open source** — free to use, inspect, modify, and contribute under the MIT license.

## Current development status

The stable default branch is **not yet a finished downloadable application**. Development and experiments are tracked in pull requests:

| Track | State | Details |
| --- | --- | --- |
| Python terminal monitor | Working prototype under review | [PR #2](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/pull/2) |
| Python live dashboard and Intel GPU sensors | Experimental; tested on one Windows 11 / Iris Xe laptop | [PR #4](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/pull/4) |
| Rust CLI and graphical dashboard | Experimental Rust work; performance and sensor validation ongoing | [Draft PR #6](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/pull/6) |

The Rust prototype is being evaluated for its startup time, memory use, monitoring accuracy, and GUI overhead. **No universal hardware compatibility or performance guarantee is implied.**

## Planned hardware support

| Hardware | Direction |
| --- | --- |
| Intel CPU and Iris Xe GPU | Initial implementation and testing focus |
| AMD CPU and GPU | Future adapter support, not yet validated |
| NVIDIA GPU | Future adapter support, not yet validated |
| Battery, power, memory, temperature | Availability depends on operating system and sensor provider |

CorePulse aims to be universal **over time**, not to advertise hardware support before it has been verified.

## Design principles

1. **Performance first:** bounded history, efficient refresh scheduling, and no busy loops.
2. **Accuracy before aesthetics:** compare measurements with trustworthy OS counters.
3. **Native where practical:** Rust is under evaluation for the final application.
4. **Safe by default:** read-only monitoring; no fan, firmware, power-limit, or disk changes.
5. **Graceful degradation:** missing permissions, drivers, and sensor data should not crash the app.
6. **Community-driven:** reproducible reports and focused contributions are welcome.

## Roadmap

- [x] Prototype Python CLI and validate basic Windows hardware readings
- [x] Prototype Intel Iris Xe activity monitoring and live terminal display
- [x] Begin experimental Rust CLI and desktop GUI development
- [ ] Complete cross-platform accuracy and overhead validation
- [ ] Reduce Rust GUI idle CPU and GPU overhead
- [ ] Provide tested Windows and Linux releases
- [ ] Expand verified AMD and NVIDIA sensor support

Checked items refer to **prototype milestones**, not to features already released from `main`.

## Try it and contribute

For the latest experimental source and testing instructions, see the pull requests linked above. These branches may change and are intended for testing, not production deployment.

Have compatible hardware or a sensor report to share? [Open an issue](https://github.com/faisalalbdy2004/iris-xe-ai-monitor/issues) or read [CONTRIBUTING.md](CONTRIBUTING.md).

## License

**MIT** — [read the license](LICENSE). You may use, modify and redistribute this code, including commercially, subject to preserving the required copyright and license notices.

---

<div align="center">

### IT'S FREE FOR THE TAKING! ❤️

**Built in the open. Made to run light.**

</div>
