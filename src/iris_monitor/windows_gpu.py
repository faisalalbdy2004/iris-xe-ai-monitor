"""Read Windows WDDM GPU engine counters and associate them with DXGI adapters."""

import ctypes as ct
import re
from collections import defaultdict
from contextlib import contextmanager
from uuid import UUID

DWORD = ct.c_uint32
HANDLE = ct.c_void_p
HRESULT = ct.c_int32
INTEL_VENDOR_ID = 0x8086
DXGI_ERROR_NOT_FOUND = 0x887A0002
DXGI_ADAPTER_FLAG_SOFTWARE = 2
IID_FACTORY1 = UUID("770aae78-f26f-4dba-a829-253c83d1b387")
GPU_ENGINE_PATH = r"\GPU Engine(*)\Utilization Percentage"
PDH_MORE_DATA = 0x800007D2
PDH_FMT_DOUBLE = 0x200
ENGINE_INSTANCE = re.compile(
    r"pid_\d+_luid_0x([0-9a-f]{1,8})_0x([0-9a-f]{1,8})"
    r"_phys_(\d+)_eng_(\d+)_engtype_.+", re.IGNORECASE,
)


class AdapterDescription(ct.Structure):
    _fields_ = [
        ("description", ct.c_wchar * 128),
        ("vendor_id", DWORD),
        ("device_id", DWORD),
        ("subsystem_id", DWORD),
        ("revision", DWORD),
        ("dedicated_video_memory", ct.c_size_t),
        ("dedicated_system_memory", ct.c_size_t),
        ("shared_system_memory", ct.c_size_t),
        ("luid_low", DWORD),
        ("luid_high", DWORD),
        ("flags", DWORD),
    ]


class CounterValue(ct.Union):
    # PDH_FMT_COUNTERVALUE uses a union. The DOUBLE member has its full size
    # and alignment on Windows.
    _fields_ = [("double", ct.c_double)]


class FormattedValue(ct.Structure):
    _fields_ = [("status", DWORD), ("value", CounterValue)]


class CounterItem(ct.Structure):
    _fields_ = [("name", ct.c_wchar_p), ("formatted", FormattedValue)]


def _bind(dll, name, result, *arguments):
    function = getattr(dll, name)
    function.argtypes = arguments
    function.restype = result
    return function


def _com_method(interface, slot, result, *arguments):
    table = ct.cast(interface, ct.POINTER(ct.POINTER(HANDLE))).contents
    return ct.WINFUNCTYPE(result, HANDLE, *arguments)(table[slot])


@contextmanager
def _release(interface):
    try:
        yield
    finally:
        _com_method(interface, 2, DWORD)(interface)  # IUnknown::Release


def _intel_adapters():
    dxgi = ct.WinDLL("dxgi.dll")
    create = _bind(dxgi, "CreateDXGIFactory1", HRESULT, ct.c_void_p, ct.POINTER(HANDLE))
    iid = (ct.c_ubyte * 16).from_buffer_copy(IID_FACTORY1.bytes_le)
    factory = HANDLE()
    if create(iid, ct.byref(factory)) < 0:
        return {}

    adapters = {}
    with _release(factory):
        # Slots include inherited IUnknown and DXGI interface methods.
        enum_adapters = _com_method(factory, 12, HRESULT, DWORD, ct.POINTER(HANDLE))
        index = 0
        while True:
            adapter = HANDLE()
            result = enum_adapters(factory, index, ct.byref(adapter))
            if result & 0xFFFFFFFF == DXGI_ERROR_NOT_FOUND:
                break
            if result < 0:
                break
            with _release(adapter):
                get_desc = _com_method(adapter, 10, HRESULT, ct.POINTER(AdapterDescription))
                desc = AdapterDescription()
                if (get_desc(adapter, ct.byref(desc)) >= 0
                        and desc.vendor_id == INTEL_VENDOR_ID
                        and not desc.flags & DXGI_ADAPTER_FLAG_SOFTWARE):
                    adapters[(desc.luid_high, desc.luid_low)] = (f"dxgi{index}", desc.description)
            index += 1
    return adapters


def _busiest_engines(rows, adapters):
    engines = defaultdict(lambda: defaultdict(float))
    for name, value in rows:
        match = ENGINE_INSTANCE.fullmatch(name)
        if match is None or not 0 <= value <= 100:
            continue
        high, low, physical, engine = match.groups()
        luid = (int(high, 16), int(low, 16))
        if luid in adapters:
            engines[luid][(int(physical), int(engine))] += value
    return {luid: round(min(100, max(values.values())), 2)
            for luid, values in engines.items()}


class EngineQuery:
    """Wrap a local PDH query. Rate counters need two successive samples."""

    def __init__(self, path=GPU_ENGINE_PATH):
        pdh = ct.WinDLL("pdh.dll")
        open_query = _bind(pdh, "PdhOpenQueryW", DWORD, ct.c_wchar_p,
                           ct.c_size_t, ct.POINTER(HANDLE))
        add_counter = _bind(pdh, "PdhAddEnglishCounterW", DWORD, HANDLE,
                            ct.c_wchar_p, ct.c_size_t, ct.POINTER(HANDLE))
        self._collect = _bind(pdh, "PdhCollectQueryData", DWORD, HANDLE)
        self._close = _bind(pdh, "PdhCloseQuery", DWORD, HANDLE)
        self._array = _bind(pdh, "PdhGetFormattedCounterArrayW", DWORD, HANDLE, DWORD,
                            ct.POINTER(DWORD), ct.POINTER(DWORD), ct.c_void_p)
        self.query = HANDLE()
        self.counter = HANDLE()
        if open_query(None, 0, ct.byref(self.query)):
            self.query = HANDLE()
        elif add_counter(self.query, path, 0, ct.byref(self.counter)):
            # A local English counter can still be readable if the separate
            # Perflib English name table cannot be loaded.
            add_local = _bind(pdh, "PdhAddCounterW", DWORD, HANDLE,
                              ct.c_wchar_p, ct.c_size_t, ct.POINTER(HANDLE))
            if add_local(self.query, path, 0, ct.byref(self.counter)):
                self.close()

    def prime(self):
        if self.query:
            self._collect(self.query)

    def read(self):
        if not self.query or self._collect(self.query):
            return []
        # Process instances can come and go between calls. Repeat sizing once
        # if the buffer grew, and cap the allocation for an untrusted provider.
        for _ in range(2):
            size, count = DWORD(), DWORD()
            if self._array(self.counter, PDH_FMT_DOUBLE, ct.byref(size),
                           ct.byref(count), None) != PDH_MORE_DATA:
                return []
            if not 0 < size.value <= 16 * 1024 * 1024:
                return []
            buffer = ct.create_string_buffer(size.value)
            result = self._array(self.counter, PDH_FMT_DOUBLE, ct.byref(size),
                                 ct.byref(count), buffer)
            if result == PDH_MORE_DATA:
                continue
            if result or count.value * ct.sizeof(CounterItem) > len(buffer):
                return []
            items = (CounterItem * count.value).from_buffer(buffer)
            return [(item.name, item.formatted.value.double) for item in items
                    if item.name and item.formatted.status in (0, 1)]
        return []

    def close(self):
        if self.query:
            self._close(self.query)
            self.query = HANDLE()


class WindowsGpu:
    def __init__(self):
        self.adapters = _intel_adapters()
        self.query = EngineQuery() if self.adapters else None
        if self.query is not None:
            self.query.prime()

    def read(self):
        rows = self.query.read() if self.query is not None else []
        busy = _busiest_engines(rows, self.adapters)
        return [
            {"device": device, "name": name, "frequency_mhz": None,
             "utilization_percent": busy.get(luid)}
            for luid, (device, name) in self.adapters.items()
        ] or None

    def close(self):
        if self.query is not None:
            self.query.close()
