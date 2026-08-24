class Pin:
    OUT = 0
    IN = 1

    def __init__(self, *a, **kw):
        self._value = kw.get('value', 0)

    def value(self, v=None):
        if v is None:
            return self._value
        self._value = v

    def __call__(self, v=None):
        return self.value(v)


class PWM:
    def __init__(self, pin):
        self._pin = pin

    def freq(self, *a):
        pass

    def duty_u16(self, *a):
        pass


class SPI:
    def __init__(self, *a, **kw):
        self.write_count = 0
        self.bytes_written = 0

    def write(self, buf):
        self.write_count += 1
        self.bytes_written += len(buf)

    def __repr__(self):
        return 'SPI(0, ...)'


def mem32(*a, **kw):
    return 0