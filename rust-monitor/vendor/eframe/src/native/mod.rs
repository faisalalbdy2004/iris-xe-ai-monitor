mod app_icon;
mod epi_integration;
mod event_loop_context;
pub mod run;

#[cfg(all(target_os = "linux", feature = "experimental_wayland_redraw"))]
use crate::egui;
#[cfg(all(target_os = "linux", feature = "experimental_wayland_redraw"))]
mod pointer_redraw;

/// File storage which can be used by native backends.
#[cfg(feature = "persistence")]
pub mod file_storage;

pub(crate) mod winit_integration;

#[cfg(feature = "glow")]
mod glow_integration;

#[cfg(feature = "wgpu")]
mod wgpu_integration;
