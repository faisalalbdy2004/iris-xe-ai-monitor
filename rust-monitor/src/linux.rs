use crate::telemetry::{nonempty, Gpu, Temperature};
use std::fs;
use std::path::{Path, PathBuf};

pub struct Sensors {
    root: PathBuf,
}

fn text(path: PathBuf) -> Option<String> {
    fs::read_to_string(path).ok().map(|v| v.trim().to_owned())
}

fn files(path: &Path) -> Vec<PathBuf> {
    let mut paths: Vec<_> = fs::read_dir(path)
        .into_iter()
        .flatten()
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .collect();
    paths.sort_unstable();
    paths
}

impl Sensors {
    pub fn new() -> Self {
        Self {
            root: "/sys/class".into(),
        }
    }

    pub fn power(&self) -> (Option<bool>, Option<f64>) {
        let mut online = Vec::new();
        let mut battery = None;
        for device in files(&self.root.join("power_supply")) {
            match text(device.join("type")).as_deref() {
                Some("Battery") if battery.is_none() => {
                    battery = text(device.join("capacity"))
                        .and_then(|v| v.parse::<u8>().ok())
                        .filter(|v| *v <= 100)
                        .map(f64::from);
                }
                Some(kind) if kind == "Mains" || kind.starts_with("USB") => {
                    online.push(text(device.join("online")));
                }
                _ => {}
            }
        }
        let ac = if online.iter().any(|v| v.as_deref() == Some("1")) {
            Some(true)
        } else if !online.is_empty() && online.iter().all(|v| v.as_deref() == Some("0")) {
            Some(false)
        } else {
            None
        };
        (ac, battery)
    }

    pub fn temperatures(&self) -> Option<Vec<Temperature>> {
        let mut values = Vec::new();
        for device in files(&self.root.join("hwmon")) {
            let Some(sensor) = text(device.join("name")) else {
                continue;
            };
            for file in files(&device) {
                let Some(channel) = file
                    .file_name()
                    .and_then(|name| name.to_str())
                    .and_then(|name| name.strip_prefix("temp"))
                    .and_then(|name| name.strip_suffix("_input"))
                    .filter(|name| !name.is_empty() && name.bytes().all(|b| b.is_ascii_digit()))
                else {
                    continue;
                };
                let label =
                    text(device.join(format!("temp{channel}_label"))).filter(|v| !v.is_empty());
                if let Some(celsius) = text(file)
                    .and_then(|v| v.parse::<i64>().ok())
                    .filter(|&millidegrees| millidegrees > -273_150)
                    .map(|v| v as f64 / 1000.0)
                {
                    values.push(Temperature {
                        sensor: sensor.clone(),
                        label,
                        celsius,
                    });
                }
            }
        }
        nonempty(values)
    }

    pub fn gpus(&self) -> Option<Vec<Gpu>> {
        let mut cards = Vec::new();
        for card in files(&self.root.join("drm")) {
            let Some(name) = card.file_name().and_then(|name| name.to_str()) else {
                continue;
            };
            if !name
                .strip_prefix("card")
                .is_some_and(|n| !n.is_empty() && n.bytes().all(|b| b.is_ascii_digit()))
                || text(card.join("device/vendor")).as_deref() != Some("0x8086")
            {
                continue;
            }
            let frequency_mhz = [
                "gt_act_freq_mhz",
                "gt/gt0/rps_act_freq_mhz",
                "device/tile0/gt0/freq0/act_freq",
            ]
            .into_iter()
            .find_map(|file| text(card.join(file))?.parse::<u64>().ok());
            cards.push(Gpu {
                device: name.to_owned(),
                frequency_mhz,
                name: None,
                utilization_percent: None,
            });
        }
        nonempty(cards)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reads_supported_sysfs_values_and_keeps_missing_values_unknown() {
        let temp = tempfile::tempdir().unwrap();
        let sensors = Sensors {
            root: temp.path().into(),
        };
        assert_eq!(sensors.power(), (None, None));
        assert!(sensors.temperatures().is_none());
        assert!(sensors.gpus().is_none());
        for (file, value) in [
            ("power_supply/AC/type", "Mains"),
            ("power_supply/AC/online", "0"),
            ("power_supply/BAT0/type", "Battery"),
            ("power_supply/BAT0/capacity", "0"),
            ("hwmon/hwmon0/name", "coretemp"),
            ("hwmon/hwmon0/temp1_input", "41500"),
            ("hwmon/hwmon0/temp1_label", "Package"),
            ("hwmon/hwmon0/temp2_input", "bad"),
            ("hwmon/hwmon0/temp3_input", "-273150"),
            ("drm/card0/device/vendor", "0x8086"),
            ("drm/card0/gt_act_freq_mhz", "bad"),
            ("drm/card0/device/tile0/gt0/freq0/act_freq", "300"),
            ("drm/card1/device/vendor", "0x1002"),
            ("drm/card2/device/vendor", "0x8086"),
        ] {
            let path = temp.path().join(file);
            fs::create_dir_all(path.parent().unwrap()).unwrap();
            fs::write(path, value).unwrap();
        }
        assert_eq!(sensors.power(), (Some(false), Some(0.0)));
        let temperatures = sensors.temperatures().unwrap();
        assert_eq!(temperatures.len(), 1);
        assert_eq!(temperatures[0].celsius, 41.5);
        let cards = sensors.gpus().unwrap();
        assert_eq!(cards.len(), 2);
        assert_eq!(cards[0].frequency_mhz, Some(300));
        assert_eq!(cards[1].frequency_mhz, None);
    }
}
