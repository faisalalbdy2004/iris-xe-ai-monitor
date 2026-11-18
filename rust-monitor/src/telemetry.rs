use serde::Serialize;
use std::thread;
use std::time::Duration;
use sysinfo::{System, MINIMUM_CPU_UPDATE_INTERVAL};

#[cfg(target_os = "linux")]
use crate::linux as platform;
#[cfg(windows)]
use crate::windows as platform;

#[derive(Serialize, Debug)]
pub struct Snapshot {
    pub platform: &'static str,
    pub cpu_percent: Option<f64>,
    pub ram_percent: Option<f64>,
    pub ram_total_bytes: Option<u64>,
    pub ram_available_bytes: Option<u64>,
    pub ac_online: Option<bool>,
    pub battery_percent: Option<f64>,
    pub temperatures: Option<Vec<Temperature>>,
    pub intel_gpus: Option<Vec<Gpu>>,
}

#[derive(Serialize, Debug)]
pub struct Temperature {
    pub sensor: String,
    pub label: Option<String>,
    pub celsius: f64,
}

#[derive(Serialize, Debug)]
pub struct Gpu {
    pub device: String,
    pub frequency_mhz: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    // Linux retains the two-field GPU entry used by Python. Windows reports
    // an explicit null when its utilization counter is unavailable.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub utilization_percent: Option<Option<f64>>,
}

pub struct Sampler {
    system: System,
    platform: platform::Sensors,
}

impl Sampler {
    pub fn new() -> Self {
        let platform = platform::Sensors::new();
        let mut system = System::new();
        system.refresh_cpu_usage();
        thread::sleep(Duration::from_millis(200).max(MINIMUM_CPU_UPDATE_INTERVAL));
        Self { system, platform }
    }

    pub fn sample(&mut self) -> Snapshot {
        self.system.refresh_cpu_usage();
        self.system.refresh_memory();
        let total = self.system.total_memory();
        let available = self.system.available_memory().min(total);
        let cpu = f64::from(self.system.global_cpu_usage());
        let (ac_online, battery_percent) = self.platform.power();
        Snapshot {
            platform: if cfg!(windows) { "Windows" } else { "Linux" },
            cpu_percent: (!self.system.cpus().is_empty() && (0.0..=100.0).contains(&cpu))
                .then_some(cpu),
            ram_percent: (total > 0).then(|| 100.0 * (total - available) as f64 / total as f64),
            ram_total_bytes: (total > 0).then_some(total),
            ram_available_bytes: (total > 0).then_some(available),
            ac_online,
            battery_percent,
            temperatures: self.platform.temperatures(),
            intel_gpus: self.platform.gpus(),
        }
    }
}

pub fn nonempty<T>(values: Vec<T>) -> Option<Vec<T>> {
    (!values.is_empty()).then_some(values)
}
