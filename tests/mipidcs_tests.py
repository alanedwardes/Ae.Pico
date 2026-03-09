import sys
import unittest
import os
from unittest.mock import MagicMock, patch

# Mock machine module
class MockPWM:
    def __init__(self, pin): self.p = pin
    def freq(self, f): self.f = f
    def duty_u16(self, d): self.d = d

sys.modules['machine'] = MagicMock()
sys.modules['machine'].PWM = MockPWM

# Mock micropython module
class MockMicropython:
    @staticmethod
    def viper(f): return f
    @staticmethod
    def native(f): return f

sys.modules['micropython'] = MockMicropython

# Mock pointers for viper
import builtins
builtins.ptr8 = lambda x: x
builtins.ptr16 = lambda x: x
builtins.ptr32 = lambda x: [x] if isinstance(x, int) else x

# Mock rp2 module
class MockDMA:
    def __init__(self): self._active = False
    def pack_ctrl(self, **kwargs): return 0x1234
    def active(self): return self._active
    def config(self, **kwargs): pass

sys.modules['rp2'] = MagicMock()
sys.modules['rp2'].DMA = MockDMA

# Mock os.uname before importing mipidcs
import os as real_os
real_os.uname = MagicMock(return_value=type('uname', (), {'machine': 'RP2350'}))

# Add the project root and infodisplay to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../infodisplay')))

import mipidcs

class TestMipiDcs(unittest.TestCase):

    def test_rgb(self):
        self.assertEqual(mipidcs.rgb(255, 255, 255), 0xFFFF)
        self.assertEqual(mipidcs.rgb(0, 0, 0), 0)

    def test_get_madctl(self):
        self.assertEqual(mipidcs.get_madctl(0, True, False), 0x60)
        self.assertEqual(mipidcs.get_madctl(0, False, False), 0x00)

    def test_get_window_coords_ili9488(self):
        ram_w, ram_h = 320, 480
        win_w, win_h = 480, 320
        # No rotation
        xs, xe, ys, ye = mipidcs.get_window_coords(ram_w, ram_h, win_w, win_h, 0, 0, 0x00, 10, 20, 100, 50)
        self.assertEqual((xs, xe, ys, ye), (10, 109, 20, 69))

    def test_backlight_manager(self):
        mock_pin = MagicMock()
        mgr = mipidcs.BacklightManager(mock_pin)
        
        # Test 0.0
        mgr.set(0.0)
        mock_pin.value.assert_called_with(0)
        
        # Test 1.0
        mgr.set(1.0)
        mock_pin.value.assert_called_with(1)
        
        # Test PWM
        mgr.set(0.5)
        self.assertIsInstance(mgr._pwm, MockPWM)
        self.assertEqual(mgr._pwm.d, 32767)

    def test_spi_controller(self):
        mock_spi = MagicMock()
        mock_dc = MagicMock()
        mock_cs = MagicMock()
        ctrl = mipidcs.SpiController(mock_spi, mock_dc, mock_cs)
        
        ctrl.write_cmd(b"\x01")
        mock_dc.assert_any_call(0)
        mock_spi.write.assert_called_with(b"\x01")
        
        ctrl.clear(10, 10, bytearray(10))
        mock_spi.write.assert_called()

    def test_dma_manager_setup(self):
        # Trigger the hardware detection logic again for the test
        mock_spi = MagicMock()
        mock_spi.__str__.return_value = "SPI(0, baudrate=...)"
        
        # Manually set the base addresses since they were detected at import time
        mipidcs._SPI0_BASE = 0x40080000 
        
        mgr = mipidcs.DmaManager(mock_spi, 480, spi_id=0)
        self.assertTrue(mgr.active)
        self.assertEqual(mgr._spi_dr, 0x40080000 + 0x08)

if __name__ == '__main__':
    unittest.main()
