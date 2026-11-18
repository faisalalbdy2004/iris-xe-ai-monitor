use crate::telemetry::{Sampler, Snapshot};
use eframe::egui::{self, Color32, RichText, Stroke, Theme, Vec2};
use std::collections::VecDeque;
use std::sync::mpsc::{self, Receiver, RecvTimeoutError, SyncSender};
use std::time::{Duration, Instant};

const HISTORY: usize = 60;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Cadence {
    Active,
    Background,
    Minimized,
}

impl Cadence {
    fn from_window(minimized: Option<bool>, focused: Option<bool>) -> Self {
        if minimized == Some(true) {
            Self::Minimized
        } else if focused == Some(false) {
            Self::Background
        } else {
            Self::Active
        }
    }

    fn period(self) -> Option<Duration> {
        match self {
            Self::Active => Some(Duration::from_secs(1)),
            Self::Background => Some(Duration::from_secs(2)),
            Self::Minimized => None,
        }
    }
}

#[derive(Default)]
struct History(VecDeque<Option<f32>>);

impl History {
    fn push(&mut self, value: Option<f64>) {
        if self.0.len() == HISTORY {
            self.0.pop_front();
        }
        self.0.push_back(value.map(|v| v as f32));
    }

    fn line(&self, ui: &mut egui::Ui, color: Color32) {
        let (response, painter) =
            ui.allocate_painter(Vec2::new(ui.available_width(), 62.0), egui::Sense::hover());
        let rect = response.rect.shrink(2.0);
        let grid = Stroke::new(1.0_f32, ui.visuals().widgets.noninteractive.bg_stroke.color);
        for ratio in [0.0, 0.5, 1.0] {
            let y = egui::lerp(rect.y_range(), ratio);
            painter.hline(rect.x_range(), y, grid);
        }
        let mut segment = Vec::with_capacity(self.0.len());
        let stroke = Stroke::new(2.0_f32, color);
        for (index, value) in self.0.iter().enumerate() {
            let x = egui::lerp(
                rect.x_range(),
                (HISTORY - self.0.len() + index) as f32 / (HISTORY - 1) as f32,
            );
            if let Some(v) = value {
                segment.push(egui::pos2(x, rect.bottom() - rect.height() * v / 100.0));
            } else if segment.len() > 1 {
                painter.add(egui::Shape::line(std::mem::take(&mut segment), stroke));
            } else {
                segment.clear();
            }
        }
        if segment.len() > 1 {
            painter.add(egui::Shape::line(segment, stroke));
        }
    }
}

struct Dashboard {
    readings: Receiver<Snapshot>,
    requests: SyncSender<Option<Instant>>,
    scheduled: Option<Cadence>,
    last_poll: Option<Instant>,
    latest: Option<Snapshot>,
    cpu: History,
    gpu: History,
    gpu_device: Option<String>,
    trace: Option<[u64; 2]>,
}

impl Drop for Dashboard {
    fn drop(&mut self) {
        if let Some([updates, samples]) = self.trace {
            eprintln!("CorePulse GUI trace: {updates} updates, {samples} snapshots");
        }
    }
}

pub fn run() -> eframe::Result {
    let options = eframe::NativeOptions {
        vsync: std::env::var_os("COREPULSE_GUI_VSYNC").as_deref()
            != Some(std::ffi::OsStr::new("0")),
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([820.0, 610.0])
            .with_min_inner_size([360.0, 400.0]),
        ..Default::default()
    };
    eframe::run_native(
        "CorePulse",
        options,
        Box::new(|app| {
            let mut dark = egui::Visuals::dark();
            dark.panel_fill = Color32::from_rgb(14, 19, 27);
            dark.extreme_bg_color = Color32::from_rgb(15, 23, 34);
            dark.widgets.inactive.bg_fill = Color32::from_rgb(31, 43, 57);
            app.egui_ctx.set_visuals_of(Theme::Dark, dark);
            app.egui_ctx.set_theme(Theme::Dark);
            app.egui_ctx.style_mut(|style| style.animation_time = 0.0);

            let context = app.egui_ctx.clone();
            let (sender, readings) = mpsc::sync_channel(1);
            let (requests, receiver) = mpsc::sync_channel::<Option<Instant>>(1);
            std::thread::spawn(move || {
                let mut sampler = None;
                let mut deadline: Option<Instant> = None;
                loop {
                    let command = match deadline {
                        Some(at) => {
                            receiver.recv_timeout(at.saturating_duration_since(Instant::now()))
                        }
                        None => receiver.recv().map_err(|_| RecvTimeoutError::Disconnected),
                    };
                    match command {
                        Ok(next) => {
                            deadline = next;
                            continue;
                        }
                        Err(RecvTimeoutError::Disconnected) => break,
                        Err(RecvTimeoutError::Timeout) => deadline = None,
                    }
                    let reading = sampler.get_or_insert_with(Sampler::new).sample();
                    if sender.send(reading).is_err() {
                        break;
                    }
                    context.request_repaint();
                }
            });
            Ok(Box::new(Dashboard {
                readings,
                requests,
                scheduled: None,
                last_poll: None,
                latest: None,
                cpu: History::default(),
                gpu: History::default(),
                gpu_device: None,
                trace: std::env::var_os("COREPULSE_GUI_TRACE").map(|_| [0, 0]),
            }))
        }),
    )
}

fn card(ui: &mut egui::Ui, content: impl FnOnce(&mut egui::Ui)) {
    egui::Frame::new()
        .fill(ui.visuals().faint_bg_color)
        .stroke(ui.visuals().widgets.noninteractive.bg_stroke)
        .corner_radius(12)
        .inner_margin(15)
        .show(ui, |ui| {
            ui.set_min_width(ui.available_width());
            content(ui);
        });
}

fn value(ui: &mut egui::Ui, name: &str, reading: Option<f64>, caption: &str) {
    ui.label(RichText::new(name).strong());
    ui.label(
        RichText::new(reading.map_or_else(|| "Unavailable".into(), |v| format!("{v:.1}%")))
            .size(26.0),
    );
    ui.weak(caption);
}

impl eframe::App for Dashboard {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        if let Some([updates, _]) = &mut self.trace {
            *updates += 1;
        }
        let cadence = ctx.input(|input| {
            let viewport = input.viewport();
            Cadence::from_window(viewport.minimized, viewport.focused)
        });
        if let Ok(snapshot) = self.readings.try_recv() {
            self.scheduled = None;
            self.last_poll = Some(Instant::now());
            if let Some([_, samples]) = &mut self.trace {
                *samples += 1;
            }
            let gpu = snapshot.intel_gpus.as_ref().and_then(|cards| cards.first());
            let device = gpu.map(|card| card.device.as_str());
            if device != self.gpu_device.as_deref() {
                self.gpu = History::default();
                self.gpu_device = device.map(str::to_owned);
            }
            self.cpu.push(snapshot.cpu_percent);
            self.gpu
                .push(gpu.and_then(|card| card.utilization_percent.flatten()));
            self.latest = Some(snapshot);
        }
        // Timeout work lives on the sampler thread. Idle UI frames are only
        // requested after new readings. A paused mode cancels the next poll.
        if self.scheduled != Some(cadence) {
            let deadline = cadence.period().map(|period| {
                self.last_poll
                    .map_or_else(Instant::now, |last| last + period)
            });
            if self.requests.try_send(deadline).is_ok() {
                self.scheduled = Some(cadence);
            }
        }
        let Some(period) = cadence.period() else {
            return;
        };

        egui::CentralPanel::default().show(ctx, |ui| {
            egui::ScrollArea::vertical().show(ui, |ui| {
                ui.horizontal(|ui| {
                    ui.heading(RichText::new("CorePulse").size(30.0).strong());
                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        let theme = ctx.theme();
                        let label = if theme == Theme::Dark {
                            "Light theme"
                        } else {
                            "Dark theme"
                        };
                        if ui.button(label).clicked() {
                            ctx.set_theme(if theme == Theme::Dark {
                                Theme::Light
                            } else {
                                Theme::Dark
                            });
                        }
                    });
                });

                let Some(snapshot) = &self.latest else {
                    ui.weak("Reading system sensors…");
                    return;
                };
                ui.weak(format!(
                    "{} · {} s refresh",
                    snapshot.platform,
                    period.as_secs()
                ));
                ui.add_space(14.0);
                let gpu = snapshot.intel_gpus.as_ref().and_then(|cards| cards.first());
                let accent = if ui.visuals().dark_mode {
                    Color32::from_rgb(102, 223, 188)
                } else {
                    Color32::from_rgb(0, 112, 92)
                };
                let cpu_card = |ui: &mut egui::Ui| {
                    card(ui, |ui| {
                        value(ui, "CPU usage", snapshot.cpu_percent, "System time");
                        self.cpu.line(ui, accent);
                    })
                };
                let gpu_card = |ui: &mut egui::Ui| {
                    card(ui, |ui| {
                        value(
                            ui,
                            "Intel GPU · busiest engine",
                            gpu.and_then(|card| card.utilization_percent.flatten()),
                            gpu.map(|card| card.name.as_deref().unwrap_or(&card.device))
                                .unwrap_or("No Intel adapter reading"),
                        );
                        self.gpu.line(ui, accent);
                        if let Some(mhz) = gpu.and_then(|card| card.frequency_mhz) {
                            ui.label(format!("GT0 clock · {mhz} MHz"));
                        }
                    })
                };
                if ui.available_width() >= 590.0 {
                    ui.columns(2, |columns| {
                        cpu_card(&mut columns[0]);
                        gpu_card(&mut columns[1]);
                    });
                } else {
                    cpu_card(ui);
                    ui.add_space(8.0);
                    gpu_card(ui);
                }
                ui.add_space(10.0);
                card(ui, |ui| {
                    let memory = snapshot.ram_total_bytes.map_or_else(
                        || "Capacity unavailable".into(),
                        |bytes| format!("{:.1} GiB total", bytes as f64 / 1073741824.0),
                    );
                    let power = match snapshot.ac_online {
                        Some(true) => "AC connected",
                        Some(false) => "AC disconnected",
                        None => "AC status unavailable",
                    };
                    ui.columns(2, |columns| {
                        value(&mut columns[0], "RAM usage", snapshot.ram_percent, &memory);
                        value(&mut columns[1], "Battery", snapshot.battery_percent, power);
                    });
                });
                ui.add_space(10.0);
                card(ui, |ui| {
                    ui.label(RichText::new("Temperatures").strong());
                    if let Some(readings) = &snapshot.temperatures {
                        for sensor in readings {
                            ui.label(format!(
                                "{} · {:.1} °C",
                                sensor.label.as_deref().unwrap_or(&sensor.sensor),
                                sensor.celsius
                            ));
                        }
                    } else {
                        ui.weak("Unavailable");
                    }
                });
            });
        });
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn history_is_bounded_and_keeps_unavailable_as_a_gap() {
        let mut history = History::default();
        for i in 0..HISTORY {
            history.push(Some(i as f64));
        }
        history.push(None);
        assert_eq!(history.0.len(), HISTORY);
        assert_eq!(history.0.front(), Some(&Some(1.0)));
        assert_eq!(history.0.back(), Some(&None));
    }

    #[test]
    fn minimized_and_background_window_states_reduce_sampling() {
        assert_eq!(Cadence::from_window(Some(true), Some(false)).period(), None);
        assert_eq!(
            Cadence::from_window(None, Some(false)).period(),
            Some(Duration::from_secs(2))
        );
        assert_eq!(
            Cadence::from_window(Some(false), Some(true)).period(),
            Some(Duration::from_secs(1))
        );
    }
}
