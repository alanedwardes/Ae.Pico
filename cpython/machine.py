class I2C:
    def __init__(self, id, **kwargs):
        from smbus2 import SMBus
        self.bus = SMBus(id)

    def readfrom_mem(self, addr, memaddr, nbytes):
        b = self.bus.read_i2c_block_data(addr, memaddr, nbytes)
        return bytes(b)

    def writeto_mem(self, addr, memaddr, buf):
        self.bus.write_i2c_block_data(addr, memaddr, buf)

    def readfrom_mem_into(self, addr, memaddr, buf):
        b = self.bus.read_i2c_block_data(addr, memaddr, len(buf))
        buf[:] = b

class PWM:
    def __init__(self, dest, *, freq=None, duty_u16=None, duty_ns=None, invert=False):
        self.__freq = 0
        self.__duty_u16 = 0

        from pigpio import pi
        self.pi = pi()
        self.dest = dest
        self.init(freq=freq, duty_u16=duty_u16, duty_ns=duty_ns, invert=invert)

    def init(self, *, freq=None, duty_u16=None, duty_ns=None, invert=False):
        if freq:
            self.__freq = freq
        if duty_u16:
            self.__duty_u16 = duty_u16
        if duty_ns:
            raise NotImplementedError('Support for setting duty_ns is not yet implemented')
        if invert:
            raise NotImplementedError('Support for signal inversion is not yet implemented')

        duty = int(self.__duty_u16 / 65_535 * 1_000_000)
        self.pi.hardware_PWM(self.dest, self.__freq, duty)

    def deinit(self):
        self.pi.hardware_PWM(self.dest, 0, 0)

    def freq(self, value=None):
        return self.init(freq=value) if value else self.__freq

    def duty_u16(self, value=None):
        return self.init(duty_u16=value) if value else self.__duty_u16

    def duty_ns(self, value=None):
        period_s = 1 / self.__freq
        period_ns = period_s * 1e9
        duty_cycle_ns = (self.__duty_u16 / 65_535) * period_ns
        return self.init(duty_ns=value) if value else int(duty_cycle_ns)
