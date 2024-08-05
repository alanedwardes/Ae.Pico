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
        g = geiger.Geiger(153.8, pin, MockPin.MOCK_TRIGGER_TYPE, 60_000)
        self.assertEqual(0, g.click_tracker.clicks)
        self.assertFalse(g.datapoint.get_needs_update())
        self.assertEqual(None, g.datapoint.get_value())
        self.assertAlmostEqual(0, g.click_tracker.get_ms_since_start(), 0)

    def test_clicks(self):
        pin = MockPin(self)
        g = geiger.Geiger(153.8, pin, MockPin.MOCK_TRIGGER_TYPE, 0)
        pin.click(25)
        self.assertEqual(25, g.click_tracker.clicks)

    def test_min_time_between_updates(self):
        pin = MockPin(self)
        g = geiger.Geiger(153.8, pin, MockPin.MOCK_TRIGGER_TYPE, 60_000)
        pin.click(25)
        self.assertEqual(25, g.click_tracker.clicks)

        # Within the 60s time, so an update will not take effect
        self.assertIsNone(g.update())
        self.assertEqual(25, g.click_tracker.clicks)
        self.assertFalse(g.datapoint.get_needs_update())

        # Pretend we started 70s ago, to force an update
        g.click_tracker.started_time = utime.ticks_ms() - 70_000
        previous_click_tracker = g.update()
        self.assertIsNotNone(previous_click_tracker)
        self.assertEqual(0, g.click_tracker.clicks)
        self.assertTrue(g.datapoint.get_needs_update())

        # Check the old click tracker
        self.assertEqual(25, previous_click_tracker.clicks)

    def test_clicks_60_seconds(self):
        pin = MockPin(self)
        g = geiger.Geiger(153.8, pin, MockPin.MOCK_TRIGGER_TYPE, 0)
        pin.click(25)

        # Pretend we started 60s ago, update
        g.click_tracker.started_time = utime.ticks_ms() - 60_000
        previous_click_tracker = g.update()
        self.assertIsNotNone(previous_click_tracker)
        self.assertEqual(0, g.click_tracker.clicks)
        self.assertAlmostEqual(0, g.click_tracker.get_ms_since_start(), 0)

        # Check the old click tracker
        self.assertEqual(25, previous_click_tracker.clicks)

        # See what the μSv/h value is
        self.assertAlmostEqual(0.16, g.datapoint.get_value(), 2)

    def test_clicks_10_seconds(self):
        pin = MockPin(self)
        g = geiger.Geiger(153.8, pin, MockPin.MOCK_TRIGGER_TYPE, 0)        
        pin.click(4)
        self.assertEqual(4, g.click_tracker.clicks)

        # Pretend we started 10s ago, update
        g.click_tracker.started_time = utime.ticks_ms() - 10_000
        previous_click_tracker = g.update()
        self.assertIsNotNone(previous_click_tracker)
        self.assertEqual(0, g.click_tracker.clicks)
        self.assertAlmostEqual(0, g.click_tracker.get_ms_since_start(), 0)

        # Check the old click tracker
        self.assertEqual(4, previous_click_tracker.clicks)

        # See what the μSv/h value is
        self.assertAlmostEqual(0.16, g.datapoint.get_value(), 2)

    def test_clicks_120_seconds(self):
        pin = MockPin(self)
        g = geiger.Geiger(153.8, pin, MockPin.MOCK_TRIGGER_TYPE, 0)        
        pin.click(50)
        self.assertEqual(50, g.click_tracker.clicks)

        # Pretend we started 120s ago, update
        g.click_tracker.started_time = utime.ticks_ms() - 120_000
        previous_click_tracker = g.update()
        self.assertIsNotNone(previous_click_tracker)
        self.assertEqual(0, g.click_tracker.clicks)
        self.assertAlmostEqual(0, g.click_tracker.get_ms_since_start(), 0)

        # Check the old click tracker
        self.assertEqual(50, previous_click_tracker.clicks)

        # See what the μSv/h value is
        self.assertAlmostEqual(0.16, g.datapoint.get_value(), 2)

if __name__ == '__main__':
    unittest.main()