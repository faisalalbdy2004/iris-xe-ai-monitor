# Experimental Wayland redraw scheduling

Build and run on Linux with:

```sh
cargo run --manifest-path rust-monitor/Cargo.toml --locked --release \
  --features experimental-wayland-redraw -- gui
```

This Cargo feature includes the regular GUI. Use `--features gui` on
its own to keep the existing scheduler. The experimental path requires a
native Linux Wayland window using Glow. Windows and X11, including XWayland,
use the existing path even when compiled with the feature. The headless CLI,
sensor worker, polling rules, and JSON layout are independent of the flag.
There is no GPU vendor or driver check.

The renderer evaluates the first motion frame normally. For up to two
pointer-only follow-ups, it skips drawing and swapping if meshes, clip
rectangles, framebuffer size, scale, and clear color are unchanged. Texture
updates, window changes, viewport commands, and renderer actions keep the
ordinary path. Input continues to be processed normally. A held mouse
button or keyboard modifier disables this comparison for that interaction.
Native focus and window events clear the comparison state. The Wayland
backend does not provide a minimized-state query, so compositor tests
cover visibility separately.

Only a tagged egui pointer carry-over for a matching unchanged pass can be
retired. Retirement resets the pending repaint state under the egui lock,
and is rejected if a newer or unrelated request has arrived. A delayed
request coalesced into the pointer carry-over also protects that callback. This matters
for telemetry and timed widgets. A prototype that removed the callback
without resetting the state stalled a sensor update for 8.22 seconds.
The [vendored dependency notes](../rust-monitor/vendor/README.md) explain
the pinned crate sources.

## Prototype measurements

The preceding KDE Wayland experiment used an Intel Iris Xe laptop with i915,
KWin 6.8.3, Mesa 26.2.7, and a 60 Hz display with VSync on. Across repeated
30 events/s motion phases, callback retirement reduced CPU from **8.60% to
7.61% of one logical core** and callbacks from **91.27 to 61.50 per second**
relative to presentation skipping alone. Presented performance was
**31.75 vs 31.74 FPS**. Idle CPU was **0.46% vs 0.47%**. All 41 acceptance
checks passed, including motion-to-idle, delayed telemetry and widgets,
window transitions, and mixed input. These numbers characterize the
instrumented prototype. The integration adds a conservative held-button
guard, and the figures are specific to Intel/KWin.

A feature-wiring smoke check used the real CorePulse binaries with native
Wayland protocol tracing. With 150 delivered motion events per run, the
regular GUI submitted 302 surface buffers and the flagged GUI submitted 158.
Both submitted six buffers during the three-second idle phase and zero
while minimized. Both resumed submissions after restore and resize.
These are surface submissions from a smoke test. The prototype's
presentation and CPU measurements used separate timing probes.

## Presentation latency

The prototype's 58.64 ms drag step split into **19.40 ms** from injection
to the native input handler, **0.86 ms** from the handler to submission,
and **38.37 ms** from submission to KWin presentation. The motion was
injected 0.23 ms after a preceding swap started, and the handler ran
0.27 ms after it returned. This is consistent with input waiting behind
the UI thread's preceding swap. The provenance trace does not isolate
compositor-side input scheduling from that wait. The changed drag frame
was drawn, and no unchanged-frame suppression decision caused the delay.
Of the time after its submission, **15.50 ms** elapsed before the swap
returned and **22.87 ms** elapsed before presentation.

For delayed telemetry in a sustained-motion probe, sample-ready to GUI apply
stayed at about **0.34 ms**. Median submission to presentation rose from
**23.00 to 26.85 ms**. End-to-end p95 rose from **35.32 to 38.92 ms**, within the
67 ms absolute limit and 16.67 ms regression budget. Swap and KWin pacing
can both contribute. Use compositor presentation feedback at additional
refresh rates before changing VSync or the event loop.

Run the policy regressions with:

```sh
cargo test --manifest-path rust-monitor/Cargo.toml --locked --release \
  --features experimental-wayland-redraw
```

Keep the feature opt-in while AMD, NVIDIA, additional compositors, and longer
drag stress runs are evaluated.
