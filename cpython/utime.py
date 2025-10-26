import time as _time
import datetime as _dt


MICROPY_PY_UTIME_TICKS_PERIOD = 2**30

_PASSTHRU = ("time", "sleep", "localtime")

for f in _PASSTHRU:
    globals()[f] = getattr(_time, f)

clock = _time.process_time()

def gmtime(t):
    return _time.gmtime(t)

def mktime(t):
    # Interpret the provided tuple as UTC and return seconds since Unix epoch.
    # Accept an 8-tuple like MicroPython (ignore weekday/yearday fields if present).
    y, mo, d, hh, mm, ss = t[0], t[1], t[2], t[3], t[4], t[5]
    return int(_dt.datetime(y, mo, d, hh, mm, ss, tzinfo=_dt.timezone.utc).timestamp())

def sleep_ms(t):
    _time.sleep(t / 1000)

def sleep_us(t):
    _time.sleep(t / 1000000)

def ticks_ms():
    return int(_time.time() * 1000) & (MICROPY_PY_UTIME_TICKS_PERIOD - 1)

def ticks_us():
    return int(_time.time() * 1000000) & (MICROPY_PY_UTIME_TICKS_PERIOD - 1)

ticks_cpu = ticks_us

def ticks_add(t, delta):
    return (t + delta) & (MICROPY_PY_UTIME_TICKS_PERIOD - 1)

def ticks_diff(a, b):
    return ((a - b + MICROPY_PY_UTIME_TICKS_PERIOD // 2) & (MICROPY_PY_UTIME_TICKS_PERIOD - 1)) - MICROPY_PY_UTIME_TICKS_PERIOD // 2

del f
