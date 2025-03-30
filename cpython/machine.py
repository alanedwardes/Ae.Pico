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
    def __init__(self, dest, *, freq=None, duty_u16=None, duty_ns=None, invert=None):
        self.__freq = 0
        self.__duty_u16 = 0

        from pigpio import pi
        self.pi = pi()
        self.dest = dest
        self.freq(freq)
        self.duty_u16(duty_u16)
        self.init()

    def init(self, *, freq=None, duty_u16=None, duty_ns=None):
        self.freq(freq)
        self.duty_u16(duty_u16)
        print("dest=%i freq=%ihz duty=%i" % (self.dest, self.freq(), self.duty()))
        self.pi.hardware_PWM(self.dest, self.freq(), self.duty())

    def deinit(self):
        self.pi.hardware_PWM(self.dest, 0, 0)

    def freq(self, value=None):
        if value:
            self.__freq = value
        return self.__freq

    def duty(self):
        return int(self.duty_u16() / 65_535 * 1_000_000)

    def duty_u16(self, value=None):
        if value:
            self.__duty_u16 = value
        return self.__duty_u16

    def duty_ns(self, value=None):
        raise NotImplementedError('duty_ns is not yet supported')
