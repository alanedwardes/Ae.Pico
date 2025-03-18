from smbus2 import SMBus

class I2C:
    def __init__(self, id, **kwargs):
        self.bus = SMBus(id)

    def readfrom_mem(self, addr, memaddr, nbytes):
        b = self.bus.read_i2c_block_data(addr, memaddr, nbytes)
        return bytes(b)

    def writeto_mem(self, addr, memaddr, buf):
        self.bus.write_i2c_block_data(addr, memaddr, buf)

    def readfrom_mem_into(self, addr, memaddr, buf):
        b = self.bus.read_i2c_block_data(addr, memaddr, len(buf))
        buf[:] = b
