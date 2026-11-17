"""Terminal refresh and optional slow sensor polling."""

import ctypes
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager


@contextmanager
def _ansi_output(stream):
    if not stream.isatty():
        yield False
        return
    if sys.platform != "win32":
        yield True
        return

    import msvcrt

    handle = ctypes.c_void_p(msvcrt.get_osfhandle(stream.fileno()))
    mode = ctypes.c_uint32()
    kernel = ctypes.windll.kernel32
    if not kernel.GetConsoleMode(handle, ctypes.byref(mode)):
        yield False
        return
    # ENABLE_PROCESSED_OUTPUT | ENABLE_VIRTUAL_TERMINAL_PROCESSING
    enabled = bool(kernel.SetConsoleMode(handle, mode.value | 0x0005))
    try:
        yield enabled
    finally:
        if enabled:
            kernel.SetConsoleMode(handle, mode)


@contextmanager
def temperature_sampler(read):
    if read is None:
        yield None
        return

    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = None
        last_reading = None
        next_poll = 0.0

        def sample():
            nonlocal pending, last_reading, next_poll
            now = time.monotonic()
            if pending is not None and pending.done():
                last_reading = pending.result()
                pending = None
            if pending is None and now >= next_poll:
                pending = executor.submit(read)
                next_poll = now + 10
            return last_reading

        yield sample


def watch(sample, render, interval, count, stream):
    with _ansi_output(stream) as redraw:
        if redraw:
            stream.write("\x1b[?1049h\x1b[?25l")
        try:
            displayed = 0
            while count is None or displayed < count:
                started = time.monotonic()
                lines = render(sample())
                if redraw:
                    columns, rows = shutil.get_terminal_size()
                    lines = [line[:max(1, columns - 1)] for line in lines[:max(1, rows - 1)]]
                    stream.write("\x1b[H\x1b[J")
                stream.write("\n".join(lines) + ("\n" if redraw else "\n\n"))
                stream.flush()
                displayed += 1
                if count is None or displayed < count:
                    time.sleep(max(0, interval - (time.monotonic() - started)))
        finally:
            if redraw:
                stream.write("\x1b[?25h\x1b[?1049l")
                stream.flush()
