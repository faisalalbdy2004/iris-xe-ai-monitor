# CorePulse on Arch, Hyprland, and Noctalia

CorePulse builds with native Wayland and X11 support. On an existing Arch
session, use Mesa for Iris Xe OpenGL and the kernel's supported Intel driver.
Tiger Lake is supported by i915. CorePulse reads the driver and sensor files
the kernel exposes and requires no kernel options, privileged service, or
Noctalia plugin. [Arch Intel graphics guide](https://wiki.archlinux.org/title/Intel_graphics) · [Noctalia session guide](https://docs.noctalia.dev/noctalia/getting-started/running-the-shell/)

From the repository root in the Hyprland session, build and run as your regular user with Rust, Mesa, Wayland and libxkbcommon available:

```sh
cargo build --manifest-path rust-monitor/Cargo.toml --locked --release --features gui
rust-monitor/target/release/iris-monitor-rs status --json
env -u DISPLAY rust-monitor/target/release/iris-monitor-rs gui
hyprctl clients
```

Run the last command from another terminal. Find CorePulse and check that
Hyprland reports it as a native Wayland client. The process-scoped `env`
command leaves the session configuration alone. XWayland is an alternative
for diagnosing display issues. [Hyprland XWayland guide](https://wiki.hypr.land/0.55.0/configuring/advanced-and-cool/xwayland/)

On the IdeaPad, compare CPU and memory with an OS monitor, check AC and
battery while plugged and unplugged, and compare exposed temperatures and
GT frequency with their sysfs readings. Linux GPU utilization is unavailable.
Test layout and pointer controls at normal and fractional scale. Confirm that
sampling pauses and resumes when the compositor reports minimization and
restore. Compositor behavior and physical Intel readings on this Arch stack
remain unverified. Ubuntu Xvfb CI exercises the X11 path with software OpenGL.
