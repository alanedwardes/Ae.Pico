import time

class XPT2046:
    """
    XPT2046 Touch Screen Controller class for MicroPython.
    Provides raw point retrieval with standard deviation smoothing and
    scaled/calibrated coordinate mapping.
    """

    # Command constants
    GET_X = 0b11010000  # X position
    GET_Y = 0b10010000  # Y position
    GET_Z1 = 0b10110000  # Z1 position
    GET_Z2 = 0b11000000  # Z2 position
    GET_TEMP0 = 0b10000000  # Temperature 0
    GET_TEMP1 = 0b11110000  # Temperature 1
    GET_BATTERY = 0b10100000  # Battery monitor
    GET_AUX = 0b11100000  # Auxiliary input to ADC

    def __init__(
        self,
        spi,
        cs,
        irq=None,
        width=320,
        height=480,
        x_min=430,
        x_max=3700,
        y_min=430,
        y_max=3700,
        x_inv=False,
        y_inv=True,
        x_y_swap=True,
    ):
        """
        Initializes the XPT2046 touch controller.

        Args:
            spi: Initialized SPI bus object. Note that XPT2046 typically operates
                 at a lower SPI baudrate (e.g. 4 MHz) compared to LCDs.
            cs: Chip select Pin.
            irq: Interrupt Pin (IRQ) for touch detection.
            width: Screen width in pixels.
            height: Screen height in pixels.
            x_min: Raw coordinate min for X axis.
            x_max: Raw coordinate max for X axis.
            y_min: Raw coordinate min for Y axis.
            y_max: Raw coordinate max for Y axis.
            x_inv: Invert the X coordinate.
            y_inv: Invert the Y coordinate.
            x_y_swap: Swap the X and Y coordinates.
        """
        self.spi = spi
        self.cs = cs
        if irq is None:
            raise ValueError("XPT2046 requires an IRQ pin to function efficiently.")
        self.irq = irq

        self.width = width
        self.height = height

        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max

        self.x_inv = x_inv
        self.y_inv = y_inv
        self.x_y_swap = x_y_swap

        self.cs.init(self.cs.OUT, value=1)
        self.irq.init(self.irq.IN)

        self.rx_buf = bytearray(3)  # Receive buffer
        self.tx_buf = bytearray(3)  # Transmit buffer

    def send_command(self, command):
        """
        Write command to XT2046.
        Args:
            command (byte): XT2046 command code.
        Returns:
            int: 12 bit response
        """
        self.tx_buf[0] = command
        self.tx_buf[1] = 0x00
        self.tx_buf[2] = 0x00

        self.cs(0)
        self.spi.write_readinto(self.tx_buf, self.rx_buf)
        self.cs(1)

        # The XPT2046 returns dummy bits during the command byte,
        # then the 12-bit ADC result in the next two bytes.
        return (self.rx_buf[1] << 4) | (self.rx_buf[2] >> 4)

    def raw_touch(self):
        """
        Read raw X,Y touch values.
        Returns:
            tuple(int, int): X, Y or None if out of bounds
        """
        if self.irq() != 0:
            return None

        x = self.send_command(self.GET_X)
        y = self.send_command(self.GET_Y)
        
        # Some displays drop coordinates near the extreme edge; 
        # a slightly more permissive bounds check than strict x_min/max
        # ensures we don't drop legitimate touches.
        if 0 < x < 4096 and 0 < y < 4096:
            return (x, y)
        else:
            return None

    async def get_raw(self):
        """
        Take a few quick samples and use a median filter to remove noise.
        This provides much better responsiveness than standard deviation arrays 
        while avoiding multi-millisecond blocking sleeps.
        Returns:
            tuple(int, int): Smoothed raw X, Y
        """
        if self.irq() != 0:
            return None

        # Take 5 readings as quickly as possible
        samples = []
        for _ in range(5):
            s = self.raw_touch()
            if s is not None:
                samples.append(s)
            
            # If the touch was released mid-read, or IRQ went high, abort early
            if self.irq() != 0:
                break

        if len(samples) < 3:
            return None
            
        # Median filter: Sort by X and Y independently to drop spikes
        xs = sorted([s[0] for s in samples])
        ys = sorted([s[1] for s in samples])
        
        mid = len(samples) // 2
        return xs[mid], ys[mid]

    async def get_touch(self):
        """Returns the scaled and optionally swapped/inverted X and Y values."""
        raw = await self.get_raw()
        self.last_raw = raw
        if raw is None:
            return None

        raw_x, raw_y = raw

        # Normalize raw_x to 0.0 - 1.0 using expected min/max bounds
        x_range = self.x_max - self.x_min
        norm_x = (raw_x - self.x_min) / x_range if x_range != 0 else 0

        # Normalize raw_y to 0.0 - 1.0 using expected min/max bounds
        y_range = self.y_max - self.y_min
        norm_y = (raw_y - self.y_min) / y_range if y_range != 0 else 0

        # Apply swap
        if self.x_y_swap:
            norm_x, norm_y = norm_y, norm_x

        # Scale to display dimensions
        x = int(norm_x * self.width)
        y = int(norm_y * self.height)

        # Invert if required
        if self.x_inv:
            x = self.width - x
        if self.y_inv:
            y = self.height - y

        # Clamp to screen bounds
        x = max(0, min(self.width, x))
        y = max(0, min(self.height, y))

        return x, y
