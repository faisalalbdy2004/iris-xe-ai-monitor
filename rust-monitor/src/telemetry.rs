use serde::Serialize;
use std::thread;
use std::time::Duration;
use sysinfo::{MemoryRefreshKind, System};

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
    previous_cpu: Option<CpuTimes>,
}

#[derive(Clone, Copy)]
pub struct CpuTimes {
    pub busy: u64,
    pub idle: u64,
}

impl CpuTimes {
    fn utilization_since(self, previous: Self) -> Option<f64> {
        let busy = self.busy.checked_sub(previous.busy)?;
        let idle = self.idle.checked_sub(previous.idle)?;
        let total = busy.checked_add(idle)?;
        (total != 0).then(|| 100.0 * busy as f64 / total as f64)
    }
}

impl Sampler {
    pub fn new() -> Self {
        let platform = platform::Sensors::new();
        let previous_cpu = platform.cpu_times();
        thread::sleep(Duration::from_millis(200));
        Self {
            system: System::new(),
            platform,
            previous_cpu,
        }
    }

    pub fn sample(&mut self) -> Snapshot {
        let current = self.platform.cpu_times();
        let cpu_percent = current
            .zip(self.previous_cpu)
            .and_then(|(now, previous)| now.utilization_since(previous));
        self.previous_cpu = current;
        self.system
            .refresh_memory_specifics(MemoryRefreshKind::nothing().with_ram());
        let total = self.system.total_memory();
        let available = self.system.available_memory().min(total);
        let (ac_online, battery_percent) = self.platform.power();
        Snapshot {
            platform: if cfg!(windows) { "Windows" } else { "Linux" },
            cpu_percent,
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn utilization_preserves_idle_zero_and_rejects_invalid_deltas() {
        let start = CpuTimes { busy: 40, idle: 50 };
        assert_eq!(start.utilization_since(start), None);
        assert_eq!(
            CpuTimes { busy: 30, idle: 70 }.utilization_since(start),
            None
        );
        assert_eq!(
            CpuTimes { busy: 40, idle: 70 }.utilization_since(start),
            Some(0.0)
        );
        assert_eq!(
            CpuTimes { busy: 45, idle: 65 }.utilization_since(start),
            Some(25.0)
        );
    }
}
