use serde::Serialize;
use std::thread;
use std::time::{Duration, Instant};
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
    #[serde(skip_serializing_if = "Option::is_none")]
    pub utilization_scope: Option<&'static str>,
}

pub trait HardwareSensors {
    const PLATFORM: &'static str;
    fn cpu_times(&self) -> Option<CpuTimes>;
    fn power(&self) -> (Option<bool>, Option<f64>);
    fn temperatures(&self) -> Option<Vec<Temperature>>;
    fn gpus(&mut self) -> Option<Vec<Gpu>>;
}

pub struct Sampler<S = platform::Sensors> {
    system: System,
    platform: S,
    cpu: CpuTracker,
}

#[derive(Default)]
struct CpuTracker(Option<(Instant, CpuTimes)>);

impl CpuTracker {
    fn update(&mut self, now: Instant, current: Option<CpuTimes>) -> Option<f64> {
        let previous = self.0;
        self.0 = current.map(|times| (now, times));
        let (previous_at, previous_times) = previous?;
        if now.checked_duration_since(previous_at)? < Duration::from_millis(100) {
            return None;
        }
        current?.utilization_since(previous_times)
    }
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

impl Sampler<platform::Sensors> {
    pub fn new() -> Self {
        let platform = platform::Sensors::new();
        let mut cpu = CpuTracker::default();
        cpu.update(Instant::now(), platform.cpu_times());
        thread::sleep(Duration::from_millis(200));
        Self {
            system: System::new(),
            platform,
            cpu,
        }
    }
}

impl<S: HardwareSensors> Sampler<S> {
    pub fn sample(&mut self) -> Snapshot {
        let current = self.platform.cpu_times();
        let cpu_percent = self.cpu.update(Instant::now(), current);
        self.system
            .refresh_memory_specifics(MemoryRefreshKind::nothing().with_ram());
        let total = self.system.total_memory();
        let available = self.system.available_memory().min(total);
        let (ac_online, battery_percent) = self.platform.power();
        Snapshot {
            platform: S::PLATFORM,
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
    fn short_and_missing_sensor_intervals_cannot_publish_a_value() {
        let mut tracker = CpuTracker::default();
        let now = Instant::now();
        let reading = Some(CpuTimes {
            busy: 100,
            idle: 200,
        });
        assert_eq!(tracker.update(now, reading), None);
        assert_eq!(
            tracker.update(
                now,
                Some(CpuTimes {
                    busy: 101,
                    idle: 201
                })
            ),
            None
        );
        assert_eq!(tracker.update(now + Duration::from_secs(1), None), None);
        assert_eq!(tracker.update(now + Duration::from_secs(2), reading), None);
        assert_eq!(
            tracker.update(
                now + Duration::from_secs(3),
                Some(CpuTimes {
                    busy: 140,
                    idle: 260
                })
            ),
            Some(40.0)
        );
    }

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
