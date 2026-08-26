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



# Mock os.uname before importing mipidcs
import os as real_os
real_os.uname = MagicMock(return_value=type('uname', (), {'machine': 'RP2350'}))

# Add the project root and infodisplay to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../infodisplay')))

import mipidcs

class TestMipiDcs(unittest.TestCase):
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

    def test_write_cd_chunked(self):
        # Chunked mode reuses one internal byte buffer; capture a copy at
        # call time to verify each write carried the right value
        written = []
        mock_spi = MagicMock()
        mock_spi.write.side_effect = lambda buf: written.append(bytes(buf))
        ctrl = mipidcs.SpiController(mock_spi, MagicMock(), MagicMock(), chunked_data=True)

        ctrl.write_cd(b"\x2a", b"\x00\x10\x01\x3f")
        self.assertEqual(written, [b"\x2a", b"\x00", b"\x10", b"\x01", b"\x3f"])

    def test_rgb332_lut_matches_bit_math(self):
        # The LUT-driven converter must reproduce the original per-pixel
        # bit-expansion formulas exactly, for every RGB332 code
        lut = mipidcs.build_rgb332_888_lut()
        src = bytearray(range(256))
        out = bytearray(256 * 3)
        mipidcs._rgb332_to_888_line(out, src, 0, 256, lut)
        for c in range(256):
            r = (c & 0xe0) | ((c & 0xe0) >> 3) | ((c & 0xe0) >> 6)
            g = ((c << 3) & 0xe0) | (c & 0x1c) | ((c >> 3) & 0x03)
            b = ((c << 6) & 0xc0) | ((c << 4) & 0x30) | ((c << 2) & 0x0c) | (c & 0x03)
            self.assertEqual((out[c * 3], out[c * 3 + 1], out[c * 3 + 2]), (r, g, b),
                             'code %d' % c)


if __name__ == '__main__':
    unittest.main()
