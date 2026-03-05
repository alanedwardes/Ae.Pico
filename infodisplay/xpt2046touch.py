import asyncio
from machine import SPI, Pin
from xpt2046 import XPT2046
from touch import Touch

class XPT2046Touch:
    CREATION_PRIORITY = 2

    def __init__(self, driver, touch_abstraction):
        self.driver = driver
        self.touch_abstraction = touch_abstraction

    def create(provider):
        config = provider['config'].get('touch', {})
            
        spi_id = config.get('spi_id', 1)
        baudrate = config.get('baudrate', 2_000_000)
        sck = config.get('sck', 10)
        mosi = config.get('mosi', 11)
        miso = config.get('miso', 12)
        
        # XPT2046 requires slower SPI than the display, but we might share the bus
        spi = SPI(spi_id, baudrate=baudrate, sck=Pin(sck), mosi=Pin(mosi), miso=Pin(miso))
        
        cs = Pin(config.get('cs', 16), Pin.OUT, value=1)
        irq_pin = config.get('irq', 17)
        irq = Pin(irq_pin, Pin.IN) if irq_pin is not None else None
        
        display = provider.get('display')
        if display:
            width, height = display.get_bounds()
        else:
            display_config = provider['config'].get('display', {})
            width = display_config.get('width', 320)
            height = display_config.get('height', 480)
        
        driver = XPT2046(
            spi=spi,
            cs=cs,
            irq=irq,
            width=width,
            height=height,
            x_min=config.get('x_min', 430),
            x_max=config.get('x_max', 3700),
            y_min=config.get('y_min', 430),
            y_max=config.get('y_max', 3700),
            x_inv=config.get('x_inv', False),
            y_inv=config.get('y_inv', True),
            x_y_swap=config.get('x_y_swap', True)
        )
        
        touch_abstraction = Touch()
        
        provider['touch'] = touch_abstraction
        provider['touch_hardware'] = driver
        return XPT2046Touch(driver, touch_abstraction)

    async def start(self):
        last_touch = None
        
        # If we have an IRQ pin we can hook it, but for reliability on RP2350
        # we will primarily rely on pure background polling.
        while True:
            # Poll the raw hardware driver
            touch_point = await self.driver.get_touch()
            
            if touch_point is not None:
                if touch_point != last_touch:
                    self.touch_abstraction.dispatch(touch_point)
                last_touch = touch_point
                # Poll very fast while dragging
                await asyncio.sleep_ms(15)
            else:
                if last_touch is not None:
                    # Touch released
                    self.touch_abstraction.dispatch(None)
                last_touch = None
                
                # When not touched, we can sleep slightly longer to save CPU,
                # but fast enough to ensure responsiveness (50ms = 20hz)
                await asyncio.sleep_ms(50)
