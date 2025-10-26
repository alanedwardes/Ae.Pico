import sys
sys.path.insert(1, '../shims')
sys.path.insert(1, '../libraries')
sys.path.insert(1, '../cpython')

import datetime
import utime
import unittest
import remotetime

class TestRemoteTime(unittest.IsolatedAsyncioTestCase):

    async def test_get_time(self):
        rt = remotetime.RemoteTime('ntp://pool.ntp.org/', 300_000, None)
        ts = await rt.acquire_time()
        self.assertEqual(300_000, rt.update_time_ms)
        self.assertEqual(2, len(ts))

        seconds, milliseconds = ts

        expected_now = utime.time()
        actual_now = seconds + milliseconds / 1000.0

        self.assertAlmostEqual(expected_now, actual_now, delta=1)

    def test_last_sunday_known_dates(self):
        # March
        self.assertEqual(26, remotetime.last_sunday(2023, 3))
        self.assertEqual(31, remotetime.last_sunday(2024, 3))
        self.assertEqual(30, remotetime.last_sunday(2025, 3))

        # October
        self.assertEqual(29, remotetime.last_sunday(2023, 10))
        self.assertEqual(27, remotetime.last_sunday(2024, 10))
        self.assertEqual(26, remotetime.last_sunday(2025, 10))

        # Other months sanity checks (including leap year February)
        self.assertEqual(29, remotetime.last_sunday(2023, 1))   # 2023-01-29
        self.assertEqual(25, remotetime.last_sunday(2024, 2))   # 2024-02-25 (leap year)

    def test_eu_uk_daylight_savings_offset_seconds_boundaries(self):
        for year in (2023, 2024, 2025):
            start_day = remotetime.last_sunday(year, 3)
            start_utc = utime.mktime((year, 3, start_day, 1, 0, 0, 0, 0))
            end_day = remotetime.last_sunday(year, 10)
            end_utc = utime.mktime((year, 10, end_day, 1, 0, 0, 0, 0))

            # Just before start => no DST
            self.assertEqual(0, remotetime.eu_uk_daylight_savings_offset_seconds(start_utc - 1))
            # At start instant => DST
            self.assertEqual(3600, remotetime.eu_uk_daylight_savings_offset_seconds(start_utc))
            # Mid-summer => DST
            mid_summer = utime.mktime((year, 7, 1, 12, 0, 0, 0, 0))
            self.assertEqual(3600, remotetime.eu_uk_daylight_savings_offset_seconds(mid_summer))
            # Just before end => DST
            self.assertEqual(3600, remotetime.eu_uk_daylight_savings_offset_seconds(end_utc - 1))
            # At end instant => no DST (end is exclusive)
            self.assertEqual(0, remotetime.eu_uk_daylight_savings_offset_seconds(end_utc))
            # After end => no DST
            self.assertEqual(0, remotetime.eu_uk_daylight_savings_offset_seconds(end_utc + 1))
            # Mid-winter => no DST
            mid_winter = utime.mktime((year, 1, 15, 12, 0, 0, 0, 0))
            self.assertEqual(0, remotetime.eu_uk_daylight_savings_offset_seconds(mid_winter))

if __name__ == '__main__':
    unittest.main()