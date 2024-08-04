import sys
sys.path.insert(1, '../shims')
sys.path.insert(1, '../sensor')

import unittest
import utime
import geiger

class MockPin:
    MOCK_TRIGGER_TYPE = 42

    def __init__(self, case):
        self.case = case

    def irq(self, handler, trigger, hard):
        self.case.assertEqual(self.MOCK_TRIGGER_TYPE, trigger)
        self.case.assertTrue(hard)
        self.handler = handler

    def click(self, times):
        for _ in range(0, times):
            self.handler(self)

class TestGeiger(unittest.TestCase):

    def test_init(self):
        pin = MockPin(self)
        g = geiger.Geiger(153.8, pin, MockPin.MOCK_TRIGGER_TYPE)
        self.assertEqual(0, g.click_tracker.clicks)
        self.assertFalse(g.datapoint.get_needs_update())
        self.assertEqual(None, g.datapoint.get_value())
        self.assertAlmostEqual(0, g.get_ms_since_last_update(), 0)

    def test_clicks(self):
        pin = MockPin(self)
        g = geiger.Geiger(153.8, pin, MockPin.MOCK_TRIGGER_TYPE)
        pin.click(25)
        self.assertEqual(25, g.click_tracker.clicks)

    def test_clicks_60_seconds(self):
        pin = MockPin(self)
        g = geiger.Geiger(153.8, pin, MockPin.MOCK_TRIGGER_TYPE)
        pin.click(25)

        # Pretend we started 60s ago, update
        g.click_tracker.started_time = utime.ticks_ms() - 60_000
        g.update()
        self.assertAlmostEqual(0, g.get_ms_since_last_update(), 0)

        # See what the μSv/h value is
        self.assertAlmostEqual(0.16, g.datapoint.get_value(), 2)

    def test_clicks_10_seconds(self):
        pin = MockPin(self)
        g = geiger.Geiger(153.8, pin, MockPin.MOCK_TRIGGER_TYPE)        
        pin.click(4)
        self.assertEqual(4, g.click_tracker.clicks)

        # Pretend we started 10s ago, update
        g.click_tracker.started_time = utime.ticks_ms() - 10_000
        g.update()
        self.assertAlmostEqual(0, g.get_ms_since_last_update(), 0)

        # See what the μSv/h value is
        self.assertAlmostEqual(0.16, g.datapoint.get_value(), 2)

    def test_clicks_120_seconds(self):
        pin = MockPin(self)
        g = geiger.Geiger(153.8, pin, MockPin.MOCK_TRIGGER_TYPE)        
        pin.click(50)
        self.assertEqual(50, g.click_tracker.clicks)

        # Pretend we started 120s ago, update
        g.click_tracker.started_time = utime.ticks_ms() - 120_000
        g.update()

        # See what the μSv/h value is
        self.assertAlmostEqual(0.16, g.datapoint.get_value(), 2)

if __name__ == '__main__':
    unittest.main()