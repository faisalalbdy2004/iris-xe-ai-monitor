use crate::telemetry::{nonempty, Gpu, Temperature};
use std::collections::HashMap;
use std::mem::size_of;
use std::ptr::null;
use windows::Win32::Graphics::Dxgi::{
    CreateDXGIFactory1, IDXGIFactory1, DXGI_ADAPTER_FLAG_SOFTWARE,
};
use windows_sys::Win32::System::{Performance::*, Power::*};

type Luid = (u32, u32);

struct Adapter {
    index: u32,
    name: String,
    luid: Luid,
}

fn intel_adapters() -> Vec<Adapter> {
    let Ok(factory) = (unsafe { CreateDXGIFactory1::<IDXGIFactory1>() }) else {
        return Vec::new();
    };
    let mut adapters = Vec::new();
    for index in 0.. {
        let Ok(adapter) = (unsafe { factory.EnumAdapters1(index) }) else { break };
        let Ok(desc) = (unsafe { adapter.GetDesc1() }) else { continue };
        if desc.VendorId != 0x8086 || desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE.0 as u32 != 0 {
            continue;
        }
        let end = desc.Description.iter().position(|&v| v == 0).unwrap_or(desc.Description.len());
        adapters.push(Adapter {
            index,
            name: String::from_utf16_lossy(&desc.Description[..end]),
            luid: (desc.AdapterLuid.HighPart as u32, desc.AdapterLuid.LowPart),
        });
    }
    adapters
}

fn instance(name: &str) -> Option<(Luid, u32, u32)> {
    let mut fields = name.splitn(11, '_');
    fn field<'a>(fields: &mut impl Iterator<Item = &'a str>, key: &str) -> Option<&'a str> {
        (fields.next()? == key).then_some(())?;
        fields.next()
    }
    fn hex(value: &str) -> Option<u32> {
        u32::from_str_radix(value.strip_prefix("0x")?, 16).ok()
    }
    field(&mut fields, "pid")?.parse::<u32>().ok()?;
    let high = hex(field(&mut fields, "luid")?)?;
    let low = hex(fields.next()?)?;
    let physical = field(&mut fields, "phys")?.parse().ok()?;
    let engine = field(&mut fields, "eng")?.parse().ok()?;
    if field(&mut fields, "engtype")?.is_empty() {
        return None;
    }
    Some(((high, low), physical, engine))
}

fn busiest(rows: impl IntoIterator<Item = (String, f64)>) -> HashMap<Luid, f64> {
    let mut engines = HashMap::new();
    for (name, value) in rows {
        if (0.0..=100.0).contains(&value) {
            if let Some(key) = instance(&name) {
                *engines.entry(key).or_insert(0.0) += value;
            }
        }
    }
    let mut result = HashMap::new();
    for ((luid, _, _), load) in engines {
        let max = result.entry(luid).or_insert(0.0_f64);
        *max = max.max(load.min(100.0));
    }
    result
}

struct EngineQuery {
    query: PDH_HQUERY,
    counter: PDH_HCOUNTER,
    // The typed allocation preserves the alignment PDH uses for records and names.
    buffer: Vec<PDH_FMT_COUNTERVALUE_ITEM_W>,
}

impl EngineQuery {
    fn new() -> Option<Self> {
        let mut handle = Self {
            query: std::ptr::null_mut(),
            counter: std::ptr::null_mut(),
            buffer: Vec::new(),
        };
        let path: Vec<_> = r"\GPU Engine(*)\Utilization Percentage"
            .encode_utf16().chain([0]).collect();
        // All calls use an owned, local query and a NUL-terminated UTF-16 path.
        unsafe {
            if PdhOpenQueryW(null(), 0, &mut handle.query) != 0 {
                return None;
            }
            if PdhAddEnglishCounterW(handle.query, path.as_ptr(), 0, &mut handle.counter) != 0
                && PdhAddCounterW(handle.query, path.as_ptr(), 0, &mut handle.counter) != 0
            {
                return None;
            }
            PdhCollectQueryData(handle.query);
        }
        Some(handle)
    }

    fn read(&mut self) -> Vec<(String, f64)> {
        const MORE_DATA: u32 = 0x8000_07d2;
        const MAX_BYTES: usize = 16 * 1024 * 1024;
        let record_size = size_of::<PDH_FMT_COUNTERVALUE_ITEM_W>();
        // SAFETY: PDH writes into initialized, properly aligned storage. Before
        // accessing records and names we bound both to the returned byte count.
        unsafe {
            if PdhCollectQueryData(self.query) != 0 {
                return Vec::new();
            }
            for _ in 0..2 {
                let (mut bytes, mut count) = (0, 0);
                if PdhGetFormattedCounterArrayW(self.counter, PDH_FMT_DOUBLE, &mut bytes,
                    &mut count, std::ptr::null_mut()) != MORE_DATA
                    || bytes == 0 || bytes as usize > MAX_BYTES
                {
                    break;
                }
                self.buffer.resize((bytes as usize).div_ceil(record_size), Default::default());
                let status = PdhGetFormattedCounterArrayW(self.counter, PDH_FMT_DOUBLE,
                    &mut bytes, &mut count, self.buffer.as_mut_ptr());
                if status == MORE_DATA {
                    continue;
                }
                let bytes = bytes as usize;
                let count = count as usize;
                if status != 0 || bytes > self.buffer.len() * record_size || count > bytes / record_size {
                    break;
                }
                let start = self.buffer.as_ptr() as usize;
                return self.buffer[..count].iter().filter_map(|record| {
                    let offset = (record.szName as usize).checked_sub(start)?;
                    if !(0..=1).contains(&record.FmtValue.CStatus)
                        || offset < count * record_size || offset >= bytes || offset % 2 != 0
                    {
                        return None;
                    }
                    let units = std::slice::from_raw_parts(
                        self.buffer.as_ptr().cast::<u8>().add(offset).cast::<u16>(),
                        (bytes - offset) / 2,
                    );
                    let end = units.iter().position(|&unit| unit == 0)?;
                    Some((String::from_utf16_lossy(&units[..end]), record.FmtValue.Anonymous.doubleValue))
                }).collect();
            }
        }
        Vec::new()
    }
}

impl Drop for EngineQuery {
    fn drop(&mut self) {
        if !self.query.is_null() {
            unsafe { PdhCloseQuery(self.query); }
        }
    }
}

pub struct Sensors {
    adapters: Vec<Adapter>,
    engine: Option<EngineQuery>,
}

impl Sensors {
    pub fn new() -> Self {
        let adapters = intel_adapters();
        let engine = (!adapters.is_empty()).then(EngineQuery::new).flatten();
        Self { adapters, engine }
    }

    pub fn power(&self) -> (Option<bool>, Option<f64>) {
        let mut status = SYSTEM_POWER_STATUS::default();
        if unsafe { GetSystemPowerStatus(&mut status) } == 0 {
            return (None, None);
        }
        let ac = match status.ACLineStatus {
            0 => Some(false), 1 => Some(true), _ => None,
        };
        let battery = (status.BatteryFlag != 255 && status.BatteryFlag & 128 == 0
            && status.BatteryLifePercent <= 100).then_some(f64::from(status.BatteryLifePercent));
        (ac, battery)
    }

    pub fn temperatures(&self) -> Option<Vec<Temperature>> {
        None
    }

    pub fn gpus(&mut self) -> Option<Vec<Gpu>> {
        let values = self.engine.as_mut().map(|query| busiest(query.read())).unwrap_or_default();
        nonempty(self.adapters.iter().map(|adapter| Gpu {
            device: format!("dxgi{}", adapter.index),
            frequency_mhz: None,
            name: Some(adapter.name.clone()),
            utilization_percent: Some(values.get(&adapter.luid).copied()),
        }).collect())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn aggregates_processes_by_luid_and_engine_and_ignores_bad_samples() {
        let rows = [
            ("pid_1_luid_0x0_0xa_phys_0_eng_0_engtype_3D", 18.0),
            ("pid_2_luid_0x0_0xa_phys_0_eng_0_engtype_3D", 22.0),
            ("pid_2_luid_0x0_0xa_phys_0_eng_1_engtype_Video_Decode", 15.0),
            ("pid_2_luid_0x0_0xb_phys_0_eng_0_engtype_3D", 0.0),
            ("pid_3_luid_0x0_0xa_phys_0_eng_0_engtype_3D", f64::NAN),
            ("unexpected counter instance", 100.0),
        ];
        let actual = busiest(rows.map(|(name, value)| (name.into(), value)));
        assert_eq!(actual, HashMap::from([((0, 10), 40.0), ((0, 11), 0.0)]));
    }
}
