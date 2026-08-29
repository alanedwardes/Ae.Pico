import sys
import os
import array
import unittest
from unittest.mock import MagicMock, patch

class MockMicropython:
    @staticmethod
    def viper(f): return f
    @staticmethod
    def native(f): return f
    @staticmethod
    def const(x): return x

sys.modules['micropython'] = MockMicropython
sys.modules['uctypes'] = MagicMock()
sys.modules['rp2'] = MagicMock()
sys.modules['machine'] = MagicMock()

import builtins
builtins.ptr8 = lambda x: x
builtins.ptr16 = lambda x: x
builtins.ptr32 = lambda x: x

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../infodisplay')))

import vga


class TestVgaSuspendResume(unittest.TestCase):
    def _make_display(self):
        display = vga.VGA.__new__(vga.VGA)
        display._started = True
        display._suspended = False
        display._core1_state = array.array('i', list(vga._CORE1_STATE_INITIAL))
        display.V_IDLE = 507
        display._reset_line_idx = 42
        display._pool_addrs = [0x20000000, 0x20000100]
        display._words_per_line = 160
        display._table_addr = 0x20001000
        display._ch_pixel_al3_trig_addr = 0x5000003C
        display._ctrl_pixel = 0xAA
        display._ctrl_ctrl = 0xBB

        call_order = MagicMock()
        display._hsync_sm = call_order.hsync_sm
        display._color_sm = call_order.color_sm
        display._vsync_sm = call_order.vsync_sm
        display._ch_ctrl = call_order.ch_ctrl
        display._ch_pixel = call_order.ch_pixel
        return display, call_order

    def test_resume_never_touches_the_sync_state_machines(self):
        display, call_order = self._make_display()
        display._suspended = True

        display.resume()

        self.assertEqual(call_order.hsync_sm.mock_calls, [])
        self.assertEqual(call_order.color_sm.mock_calls, [])
        self.assertEqual(call_order.vsync_sm.mock_calls, [])
        self.assertFalse(display._suspended)

    def test_resume_rearms_dma_from_start_of_table_and_pool(self):
        display, call_order = self._make_display()
        display._suspended = True

        display.resume()

        call_order.ch_pixel.config.assert_called_once_with(
            read=display._pool_addrs[0], write=call_order.color_sm,
            count=display._words_per_line + vga.COLOR_PROG_LINE_COUNT_WORDS,
            ctrl=display._ctrl_pixel, trigger=False)
        call_order.ch_ctrl.config.assert_called_once_with(
            read=display._table_addr, write=display._ch_pixel_al3_trig_addr,
            count=1, ctrl=display._ctrl_ctrl, trigger=False)
        call_order.ch_ctrl.active.assert_called_once_with(1)

    def test_resume_resets_vsync_line_tracking_shared_state(self):
        display, call_order = self._make_display()
        display._suspended = True
        vga._vsync_reset_shared[vga._VSR_LINE_IDX] = 123
        vga._vsync_reset_shared[vga._VSR_LAST_VSYNC_ASSERTED] = 1
        vga._vsync_reset_shared[vga._VSR_RESET_DONE_THIS_FRAME] = 1

        display.resume()

        self.assertEqual(vga._vsync_reset_shared[vga._VSR_LINE_IDX], -1)
        self.assertEqual(vga._vsync_reset_shared[vga._VSR_LAST_VSYNC_ASSERTED], 0)
        self.assertEqual(vga._vsync_reset_shared[vga._VSR_RESET_DONE_THIS_FRAME], 0)
        self.assertEqual(vga._vsync_reset_shared[vga._VSR_RESET_LINE_IDX], display._reset_line_idx)

    def test_suspend_disables_only_the_pixel_feed_dma_and_marks_state(self):
        display, call_order = self._make_display()

        display.suspend()

        call_order.ch_ctrl.active.assert_called_once_with(0)
        call_order.ch_pixel.active.assert_called_once_with(0)
        self.assertEqual(call_order.hsync_sm.mock_calls, [])
        self.assertEqual(call_order.color_sm.mock_calls, [])
        self.assertEqual(call_order.vsync_sm.mock_calls, [])
        self.assertTrue(display._suspended)
        self.assertEqual(display._core1_state[vga._CS_ENABLED], 0)

    def test_suspend_is_noop_when_not_started(self):
        display, call_order = self._make_display()
        display._started = False

        display.suspend()

        self.assertEqual(call_order.mock_calls, [])

    def test_suspend_is_noop_when_already_suspended(self):
        display, call_order = self._make_display()
        display._suspended = True

        display.suspend()

        self.assertEqual(call_order.mock_calls, [])

    def test_resume_is_noop_when_already_running(self):
        display, call_order = self._make_display()
        display._suspended = False

        display.resume()

        self.assertEqual(call_order.mock_calls, [])

    def test_resume_calls_start_instead_of_touching_hardware_directly_when_never_started(self):
        display, call_order = self._make_display()
        display._started = False
        display.start = MagicMock()

        display.resume()

        display.start.assert_called_once_with()
        self.assertEqual(call_order.mock_calls, [])

    def test_suspend_resume_cycle_allocates_nothing_and_spawns_no_threads(self):
        display, _call_order = self._make_display()

        with patch('_thread.start_new_thread') as mock_thread, \
             patch('array.array') as mock_array:
            for _ in range(5):
                display.suspend()
                display.resume()

            mock_thread.assert_not_called()
            mock_array.assert_not_called()


if __name__ == '__main__':
    unittest.main()
