use crate::telemetry::{Sampler, Snapshot};
use eframe::egui::{self, Color32, RichText};
use std::sync::mpsc::{self, Receiver, TrySendError};
use std::time::Duration;

struct Dashboard {
    channel: Receiver<Snapshot>,
    latest: Option<Snapshot>,
}

pub fn run() -> eframe::Result {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([700.0, 500.0])
            .with_min_inner_size([460.0, 360.0]),
        ..Default::default()
    };
    eframe::run_native(
        "Iris Xe AI Monitor",
        options,
        Box::new(|app| {
            let mut visuals = egui::Visuals::dark();
            visuals.panel_fill = Color32::from_rgb(15, 21, 28);
            visuals.widgets.inactive.bg_fill = Color32::from_rgb(33, 44, 57);
            app.egui_ctx.set_visuals(visuals);

            let context = app.egui_ctx.clone();
            let (sender, channel) = mpsc::sync_channel(1);
            std::thread::spawn(move || {
                let mut sampler = Sampler::new();
                loop {
                    match sender.try_send(sampler.sample()) {
                        Ok(()) => context.request_repaint(),
                        Err(TrySendError::Full(_)) => (),
                        Err(TrySendError::Disconnected(_)) => break,
                    }
                    std::thread::sleep(Duration::from_secs(1));
                }
            });
            Ok(Box::new(Dashboard {
                channel,
                latest: None,
            }))
        }),
    )
}

fn metric(ui: &mut egui::Ui, name: &str, value: Option<f64>) {
    ui.label(RichText::new(name).strong());
    if let Some(value) = value {
        ui.add(
            egui::ProgressBar::new((value / 100.0) as f32)
                .desired_width(ui.available_width().min(280.0))
                .fill(Color32::from_rgb(93, 198, 174))
                .text(format!("{value:.1}%")),
        );
    } else {
        ui.weak("Unavailable");
    }
}

impl eframe::App for Dashboard {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        if let Ok(sample) = self.channel.try_recv() {
            self.latest = Some(sample);
        }
        egui::CentralPanel::default().show(ctx, |ui| {
            ui.add_space(10.0);
            ui.heading(RichText::new("Iris Xe AI Monitor").size(28.0).strong());
            let Some(snapshot) = &self.latest else {
                ui.weak("Reading system sensors…");
                return;
            };
            ui.weak(snapshot.platform);
            ui.add_space(10.0);
            ui.separator();
            egui::ScrollArea::vertical().show(ui, |ui| {
                ui.columns(2, |columns| {
                    metric(&mut columns[0], "CPU", snapshot.cpu_percent);
                    metric(&mut columns[1], "RAM", snapshot.ram_percent);
                });
                ui.add_space(13.0);
                ui.columns(2, |columns| {
                    metric(&mut columns[0], "Battery", snapshot.battery_percent);
                    columns[1].label(RichText::new("AC power").strong());
                    columns[1].label(match snapshot.ac_online {
                        Some(true) => "Connected",
                        Some(false) => "Disconnected",
                        None => "Unavailable",
                    });
                });
                ui.add_space(15.0);
                ui.separator();
                ui.heading("Intel graphics");
                if let Some(gpus) = &snapshot.intel_gpus {
                    for gpu in gpus {
                        let name = gpu.name.as_deref().unwrap_or(&gpu.device);
                        ui.label(name);
                        if let Some(busy) = gpu.utilization_percent {
                            metric(ui, "Busiest engine", busy);
                        }
                        ui.weak(gpu.frequency_mhz.map_or_else(
                            || "Clock unavailable".into(),
                            |mhz| format!("{mhz} MHz"),
                        ));
                    }
                } else {
                    ui.weak("Unavailable");
                }
                ui.add_space(10.0);
                ui.heading("Temperatures");
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
    }
}
