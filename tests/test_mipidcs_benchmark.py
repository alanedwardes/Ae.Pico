import sys
import os
import tracemalloc

# Setup paths to ensure we can import the module correctly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'infodisplay')))

# Mock micropython types built-ins for CPython environment
import builtins
builtins.ptr8 = object
builtins.ptr16 = object
builtins.ptr32 = object

class MockMicropython:
    @staticmethod
    def viper(func):
        return func
sys.modules['micropython'] = MockMicropython()

class MockMachine:
    class PWM:
        def __init__(self, pin): pass
        def freq(self, v): pass
        def duty_u16(self, v): pass
sys.modules['machine'] = MockMachine()

from mipidcs import MipiDisplay

class MockSPI:
    def write(self, data):
        pass

class MockPin:
    def __init__(self, val=0):
        self.val = val
    def __call__(self, val):
        self.val = val
    def value(self, val):
        self.val = val

class TestDisplay(MipiDisplay):
    def __init__(self, **kwargs):
        super().__init__(
            spi=MockSPI(),
            cs=MockPin(),
            dc=MockPin(),
            backlight=None,
            width=240,
            height=240,
            scale=1,
            color_mode='RGB565',
            bpp=2,
            chunked_command_data=False
        )
        self._lut = bytearray(512)
    
    def _get_line_conv(self, scale):
        def dummy_conv(*args):
            pass
        return dummy_conv
    
    def _set_region_window(self, x, y, rw, rh):
        pass

def test_mpi_render_performance(benchmark):
    """
    Proper pytest benchmark using pytest-benchmark fixture.
    To run: pytest tests/test_mipidcs_benchmark.py
    """
    display = TestDisplay()
    fb = bytearray(240 * 240 * 2)
    fb_view = memoryview(fb)
    
    # The benchmark fixture automatically handles warmup, 
    # iterations, variance, and statistics formatting.
    benchmark(display.render, fb_view, 240, 240, (0, 0, 240, 240))


def test_mpi_render_memory_allocation():
    """
    Test that ensures no regressions in the inner loop memory allocation
    occur over multiple frames of rendering.
    """
    display = TestDisplay()
    fb = bytearray(240 * 240 * 2)
    fb_view = memoryview(fb)
    
    # Warmup
    display.render(fb_view, 240, 240, (0, 0, 240, 240))
    
    tracemalloc.start()
    
    # Render several frames to ensure no compound allocation
    for _ in range(50):
        display.render(fb_view, 240, 240, (0, 0, 240, 240))
        
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    # Expect zero or very minimal allocations. 
    # (CPython might have extremely tiny background overhead, but it shouldn't scale with row count).
    assert peak < 1000, f"Memory leak detected! Peak allocation inside the run loop was {peak} bytes."
