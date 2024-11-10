import sys
sys.path.insert(1, '../shims')
sys.path.insert(1, '../libraries')

import datetime
import unittest
import remotetime
import network

class TestRemoteTime(unittest.IsolatedAsyncioTestCase):

    nic = network.AbstractNIC

    async def test_get_time_https(self):
        rt = remotetime.RemoteTime('https://time.alanedwardes.com/', 300_000, self.nic)
        ts = await rt.get_time()
        self.assertEqual(300_000, rt.update_time_ms)
        self.assertEqual(8, len(ts))

        now = datetime.datetime.now()

        self.assertEqual(now.year, ts[0])
        self.assertEqual(now.month, ts[1])
        self.assertEqual(now.day, ts[2])
        self.assertEqual(now.isoweekday(), ts[3])
        self.assertEqual(now.hour, ts[4])
        self.assertEqual(now.minute, ts[5])
        self.assertEqual(now.second, ts[6])

    async def test_get_time_http(self):
        rt = remotetime.RemoteTime('http://time.alanedwardes.com/', 300_000, self.nic)
        ts = await rt.get_time()
        self.assertEqual(300_000, rt.update_time_ms)
        self.assertEqual(8, len(ts))

        now = datetime.datetime.now()

        self.assertEqual(now.year, ts[0])
        self.assertEqual(now.month, ts[1])
        self.assertEqual(now.day, ts[2])
        self.assertEqual(now.isoweekday(), ts[3])
        self.assertEqual(now.hour, ts[4])
        self.assertEqual(now.minute, ts[5])
        self.assertEqual(now.second, ts[6])

    async def test_get_time_ntp(self):
        rt = remotetime.RemoteTime('ntp://pool.ntp.org/', 300_000, self.nic)
        ts = await rt.get_time()
        self.assertEqual(300_000, rt.update_time_ms)
        self.assertEqual(8, len(ts))

        now = datetime.datetime.now()

        self.assertEqual(now.year, ts[0])
        self.assertEqual(now.month, ts[1])
        self.assertEqual(now.day, ts[2])
        self.assertEqual(now.isoweekday(), ts[3])
        self.assertEqual(now.hour, ts[4])
        self.assertEqual(now.minute, ts[5])
        self.assertEqual(now.second, ts[6])

    async def test_get_time_http_missing_header(self):
        rt = remotetime.RemoteTime('https://alanedwardes.com/', 300_000, self.nic)
        with self.assertRaises(Exception):
            await rt.get_time()

if __name__ == '__main__':
    unittest.main()