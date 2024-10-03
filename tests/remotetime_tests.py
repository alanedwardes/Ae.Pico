import sys
sys.path.insert(1, '../shims')
sys.path.insert(1, '../libraries')

import unittest
import utime
import remotetime
import machine

class TestRemoteTime(unittest.TestCase):

    ENDPOINT = 'http://time.alanedwardes.com/?tz=Europe/London&fmt=%Y,%m,%d,%w,%H,%M,%S,%f'

    def test_get_time(self):
        rt = remotetime.RemoteTime(self.ENDPOINT, 300_000)
        ts = rt.get_time()
        self.assertEqual(self.ENDPOINT, rt.endpoint)
        self.assertEqual(300_000, rt.update_time_ms)
        self.assertEqual(8, len(ts))

    def test_update(self):
        machine.RTC.ts = None
        rt = remotetime.RemoteTime(self.ENDPOINT, 300_000)
        self.assertIsNone(machine.RTC.ts)
        rt.update()
        self.assertEqual(8, len(machine.RTC.ts))

    def test_subsequent_update(self):
        machine.RTC.ts = None
        # Initial update
        rt = remotetime.RemoteTime(self.ENDPOINT, 300_000)
        rt.update()
        self.assertIsNotNone(machine.RTC.ts)
        
        machine.RTC.ts = None
        # Immediate next update - do nothing
        rt.update()
        self.assertIsNone(machine.RTC.ts)

        machine.RTC.ts = None
        # Update because enough time has passed
        rt.last_updated_time = utime.ticks_add(rt.last_updated_time, -400_000)
        rt.update()
        self.assertIsNotNone(machine.RTC.ts)

if __name__ == '__main__':
    unittest.main()