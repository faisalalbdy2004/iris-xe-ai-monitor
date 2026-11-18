#[cfg(feature = "gui")]
mod gui;
#[cfg(target_os = "linux")]
mod linux;
mod telemetry;
#[cfg(windows)]
mod windows;

use clap::{Parser, Subcommand};
use std::io::{self, Write};
use std::time::{Duration, Instant};
use telemetry::{Sampler, Snapshot};

#[derive(Parser)]
#[command(version, about = "Read-only Windows and Linux telemetry")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Print one telemetry snapshot.
    Status {
        #[arg(long)]
        json: bool,
    },
    /// Print successive snapshots. Press Ctrl+C to stop.
    Watch {
        #[arg(long, default_value = "1", value_parser = interval)]
        interval: Duration,
        #[arg(long, value_parser = clap::value_parser!(u32).range(1..))]
        count: Option<u32>,
    },
    /// Open the experimental desktop dashboard.
    #[cfg(feature = "gui")]
    Gui,
}

fn interval(value: &str) -> Result<Duration, String> {
    let seconds = value.parse::<f64>().map_err(|e| e.to_string())?;
    if !(0.5..=3600.0).contains(&seconds) {
        return Err("interval must be between 0.5 and 3600 seconds".into());
    }
    Ok(Duration::from_secs_f64(seconds))
}

fn percent(value: Option<f64>) -> String {
    value.map_or_else(|| "unavailable".into(), |v| format!("{v:.1}%"))
}

fn write_snapshot(mut out: impl Write, snapshot: &Snapshot) -> io::Result<()> {
    let bytes = |v: Option<u64>| v.map_or_else(|| "unavailable".into(), |n| format!("{n} bytes"));
    writeln!(out, "Platform: {}", snapshot.platform)?;
    writeln!(out, "CPU utilization: {}", percent(snapshot.cpu_percent))?;
    writeln!(out, "RAM utilization: {}", percent(snapshot.ram_percent))?;
    writeln!(out, "RAM total: {}", bytes(snapshot.ram_total_bytes))?;
    writeln!(
        out,
        "RAM available: {}",
        bytes(snapshot.ram_available_bytes)
    )?;
    writeln!(
        out,
        "AC power: {}",
        match snapshot.ac_online {
            Some(true) => "online",
            Some(false) => "offline",
            None => "unavailable",
        }
    )?;
    writeln!(out, "Battery charge: {}", percent(snapshot.battery_percent))?;
    if let Some(gpus) = &snapshot.intel_gpus {
        for gpu in gpus {
            let device = gpu.name.as_deref().unwrap_or(&gpu.device);
            if let Some(utilization) = gpu.utilization_percent {
                writeln!(
                    out,
                    "Intel GPU ({device}) busiest engine: {}",
                    percent(utilization)
                )?;
            }
            let clock = gpu
                .frequency_mhz
                .map_or_else(|| "unavailable".into(), |f| format!("{f} MHz"));
            writeln!(out, "Intel GPU ({device}) frequency: {clock}")?;
        }
    } else {
        writeln!(out, "Intel GPU telemetry: unavailable")?;
    }
    if let Some(readings) = &snapshot.temperatures {
        for t in readings {
            writeln!(
                out,
                "Temperature ({}, {}): {:.1} C",
                t.sensor,
                t.label.as_deref().unwrap_or("unlabeled"),
                t.celsius
            )?;
        }
    } else {
        writeln!(out, "Temperatures: unavailable")?;
    }
    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();
    match cli.command {
        Command::Status { json } => {
            let snapshot = Sampler::new().sample();
            let mut out = io::stdout().lock();
            if json {
                serde_json::to_writer(&mut out, &snapshot)?;
                writeln!(out)?;
            } else {
                write_snapshot(out, &snapshot)?;
            }
        }
        Command::Watch { interval, count } => {
            let mut sampler = Sampler::new();
            let mut out = io::stdout().lock();
            for index in 0..u32::MAX {
                let start = Instant::now();
                write_snapshot(&mut out, &sampler.sample())?;
                writeln!(out)?;
                out.flush()?;
                if count == Some(index + 1) {
                    break;
                }
                std::thread::sleep(interval.saturating_sub(start.elapsed()));
            }
        }
        #[cfg(feature = "gui")]
        Command::Gui => gui::run().map_err(|err| err.to_string())?,
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn status_uses_legacy_keys_and_null_for_unknown_values() {
        let sample = Snapshot {
            platform: "Linux",
            cpu_percent: Some(0.0),
            ram_percent: None,
            ram_total_bytes: None,
            ram_available_bytes: None,
            ac_online: Some(false),
            battery_percent: None,
            temperatures: None,
            intel_gpus: None,
        };
        assert_eq!(
            serde_json::to_value(sample).unwrap(),
            serde_json::json!({
                "platform": "Linux", "cpu_percent": 0.0, "ram_percent": null,
                "ram_total_bytes": null, "ram_available_bytes": null, "ac_online": false,
                "battery_percent": null, "temperatures": null, "intel_gpus": null,
            })
        );
        assert!(interval("NaN").is_err());
        assert_eq!(interval("0.5").unwrap(), Duration::from_millis(500));
    }
}
