"""Terminal refresh and optional slow sensor polling."""

import ctypes
import shutil
import sys
import time
from contextlib import contextmanager
from itertools import islice
from queue import Empty, SimpleQueue
from threading import Thread


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

    results = SimpleQueue()
    pending = None
    last_reading = None
    next_poll = 0.0
    closed = False

    def poll():
        try:
            reading = read()
        except Exception:
            reading = None
        results.put(reading)

    def sample():
        nonlocal pending, last_reading, next_poll
        if closed:
            return None
        now = time.monotonic()
        if pending is not None and not pending.is_alive():
            try:
                last_reading = results.get_nowait()
            except Empty:
                last_reading = None
            pending = None
        if pending is None and now >= next_poll:
            # A blocked provider cannot be cancelled safely. Keep one daemon
            # poll in flight and leave it alone when the dashboard exits.
            pending = Thread(target=poll, daemon=True)
            pending.start()
            next_poll = now + 10
        return last_reading

    try:
        yield sample
    finally:
        closed = True


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
                    width = max(1, columns - 1)
                    height = max(1, rows - 1)
                    lines = (line[:width] for line in islice(lines, height))
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
