# Pinned eframe and egui sources

These are the published eframe and egui 0.33.3 sources from upstream commit
`44cdd653e2317d300fb8a6c9c36b03f23991e803`, under either the [MIT](LICENSE-MIT)
or [Apache 2.0](LICENSE-APACHE) license. The original crate checksums are:

| Crate | SHA-256 |
|---|---|
| eframe | `457481173e6db5ca9fa2be93a58df8f4c7be639587aeb4853b526c6cf87db4e6` |
| egui | `6a9b567d356674e9a5121ed3fedfb0a7c31e059fe71f6972b691bcd0bfc284e3` |

The local patches add opt-in repaint provenance and retirement in egui, and
the native Linux Wayland paint policy in eframe. The primary review files
are `egui/src/context.rs`, `eframe/src/native/pointer_redraw.rs`,
`eframe/src/native/glow_integration.rs`, and `eframe/src/native/run.rs`.
Other edits pass the feature, renderer option, and repaint event field
through the existing interfaces. Tests in the CorePulse crate exercise the
actual paint policy and egui's wake-up state.

Cargo uses the pinned copies for GUI builds so the feature works through the
normal Cargo entry point. Other dependencies stay on crates.io. The
experimental hooks are disabled by default. On an upstream version bump,
review the repaint invariants again and drop the local copies if the hooks
are available upstream.
