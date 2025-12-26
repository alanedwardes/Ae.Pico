import asyncio
import _thread
import time
from machine import SPI, Pin
from st7789 import ST7789, LANDSCAPE
from drawing import Drawing

WIDTH = 320
HEIGHT = 240

class ThreadedDriver:
    def __init__(self, driver):
        self.driver = driver
        self.args = None
        self.running = True
        # Lock to coordinate access to the framebuffer
        self.lock = _thread.allocate_lock()
        # Start the background rendering loop on the second core
        _thread.start_new_thread(self._loop, ())

    def _loop(self):
        while self.running:
            if self.args:
                # Try to acquire the lock. If drawing is happening, this blocks
                # until drawing is done.
                with self.lock:
                    # Perform the blocking render on the second core
                    self.driver.render(*self.args)
            else:
                # Sleep briefly to avoid hogging the core when idle (waiting for first frame)
                time.sleep_ms(100)

    def set_framebuffer(self, framebuffer, width, height, region):
        self.args = (framebuffer, width, height, region)

    def render(self, framebuffer, width, height, region):
        pass
    
    def set_backlight(self, brightness):
        # Pass backlight control directly through
        self.driver.set_backlight(brightness)
    
    def stop(self):
        self.running = False

class ThreadedST7789Display:
    def __init__(self, st, drawing, driver_wrapper):
        self.st = st
        self.drawing = drawing
        self.driver_wrapper = driver_wrapper

    def context(self):
        """
        Returns a context manager that pauses rendering while active.
        Usage:
            with display.context():
                # rendering is paused here
                display.drawing.fill(0)
                display.drawing.text(...)
            # rendering resumes here
        """
        return self.driver_wrapper.lock

    @staticmethod
    def create(provider):
        config = provider['config'].get('display', {})

        # Same hardware initialization as standard display
        spi = SPI(0, baudrate=40000000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(19))
        dc = Pin(16, Pin.OUT, value=0)
        cs = Pin(17, Pin.OUT, value=1)
        rst = Pin(12, Pin.OUT, value=1)
        backlight = Pin(20, Pin.OUT, value=1)

        st = ST7789(
            spi,
            cs=cs,
            dc=dc,
            rst=rst,
            backlight=backlight,
            height=HEIGHT,
            width=WIDTH,
            disp_mode=LANDSCAPE,
            display=(0, 0, 1, 0, True),
        )

        # Optional rotation from config
        rotation = config.get('rotate', 0)  # degrees: 0/90/180/270
        st.set_rotation_degrees(int(rotation))

        drawing = Drawing(WIDTH, HEIGHT)

        # Wrap the hardware driver with our threaded driver
        threaded_st = ThreadedDriver(st)
        
        # Pass the threaded driver to Drawing; Drawing will call threaded_st.render()
        drawing.set_driver(threaded_st)
        threaded_st.set_framebuffer(drawing._buf, WIDTH, HEIGHT, (0, 0, WIDTH, HEIGHT))

        provider['display'] = drawing
        return ThreadedST7789Display(st, drawing, threaded_st)

    async def start(self):
        await asyncio.Event().wait()
