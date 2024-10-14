import sys
sys.path.insert(1, '../shims')
sys.path.insert(1, '../libraries')

import unittest
import utime
import remotetime
import machine
import network

class TestRemoteTime(unittest.IsolatedAsyncioTestCase):

    ENDPOINT = 'http://time.alanedwardes.com/?tz=Europe/London&fmt=%Y,%m,%d,%w,%H,%M,%S,%f'
    nic = network.AbstractNIC

    async def test_get_time(self):
        rt = remotetime.RemoteTime(self.ENDPOINT, 300_000, self.nic)
        ts = await rt.get_time()
        self.assertEqual(300_000, rt.update_time_ms)
        self.assertEqual(8, len(ts))

if __name__ == '__main__':
    unittest.main()