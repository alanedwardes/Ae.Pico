import sys
sys.path.insert(1, '../shims')
sys.path.insert(1, '../sensor')

import unittest
import utime
import datapoint

class TestDatapoint(unittest.TestCase):

    def test_init(self):
        dp = datapoint.DataPoint()

        # Check that out of the box, no update required
        self.assertIsNone(dp.get_value())
        self.assertFalse(dp.get_needs_update())

        # Check that None values don't break things
        dp.set_value(None)
        self.assertIsNone(dp.get_value())
        self.assertFalse(dp.get_needs_update())

    def test_float(self):
        dp = datapoint.DataPoint(0.1)

        # Set a value, and ensure it triggers the first update
        dp.last_updated_time = None
        dp.set_value(0.01)
        self.assertEqual(0.01, dp.get_value())
        self.assertTrue(dp.get_needs_update())
        dp.set_value_updated()
        self.assertFalse(dp.get_needs_update())

        # Pretend the last value update was over 5 minutes ago and that an update is needed
        dp.last_updated_time = utime.ticks_add(utime.ticks_ms(), -400_000)
        self.assertTrue(dp.get_needs_update())
        dp.set_value_updated()
        self.assertFalse(dp.get_needs_update())

        # Set a change too small to transmit
        dp.set_value(0.02)
        self.assertFalse(dp.get_needs_update())

        # Set a larger change to transmit
        dp.last_updated_time = utime.ticks_add(utime.ticks_ms(), -20_000)
        dp.set_value(0.2)
        self.assertTrue(dp.get_needs_update())
        dp.set_value_updated()
        self.assertFalse(dp.get_needs_update())

    def test_integer(self):
        dp = datapoint.DataPoint(1)

        # Set a value, and ensure it triggers the first update
        dp.last_updated_time = None
        dp.set_value(-66)
        self.assertEqual(-66, dp.get_value())
        self.assertTrue(dp.get_needs_update())
        dp.set_value_updated()
        self.assertFalse(dp.get_needs_update())

        # Pretend the last value update was over 5 minutes ago and that an update is needed
        dp.last_updated_time = utime.ticks_add(utime.ticks_ms(), -400_000)
        self.assertTrue(dp.get_needs_update())
        dp.set_value_updated()
        self.assertFalse(dp.get_needs_update())

        # Set a change too small to transmit
        dp.set_value(-66)
        self.assertFalse(dp.get_needs_update())

        # Set a larger change to transmit
        dp.last_updated_time = utime.ticks_add(utime.ticks_ms(), -20_000)
        dp.set_value(-65)
        self.assertTrue(dp.get_needs_update())
        dp.set_value_updated()
        self.assertFalse(dp.get_needs_update())

    def test_bool(self):
        dp = datapoint.DataPoint()

        # Set a value, and ensure it triggers the first update
        dp.last_updated_time = None
        dp.set_value(True)
        self.assertEqual(True, dp.get_value())
        self.assertTrue(dp.get_needs_update())
        dp.set_value_updated()
        self.assertFalse(dp.get_needs_update())

        # Flip it, ensure we transmit
        dp.last_updated_time = utime.ticks_add(utime.ticks_ms(), -20_000)
        dp.set_value(False)
        self.assertTrue(dp.get_needs_update())
        dp.set_value_updated()
        self.assertFalse(dp.get_needs_update())

        

if __name__ == '__main__':
    unittest.main()