import sys
sys.path.insert(1, '../libraries')
sys.path.insert(1, '../cpython')

import asyncio
import unittest
from eventbus import EventBus


class TestEventBus(unittest.IsolatedAsyncioTestCase):

    async def test_sync_callback_receives_event(self):
        bus = EventBus()
        received = []
        bus.subscribe('foo', lambda ev: received.append(ev))
        bus.publish('foo', {'x': 1})
        await asyncio.wait_for(self._until(lambda: received), 1)
        self.assertEqual(received[0].name, 'foo')
        self.assertEqual(received[0].data, {'x': 1})

    async def test_async_callback_receives_event(self):
        bus = EventBus()
        received = []
        async def cb(ev):
            await asyncio.sleep(0)
            received.append(ev)
        bus.subscribe('foo', cb)
        bus.publish('foo')
        await asyncio.wait_for(self._until(lambda: received), 1)
        self.assertEqual(received[0].name, 'foo')

    async def test_multiple_subscribers_all_receive(self):
        bus = EventBus()
        a, b = [], []
        bus.subscribe('foo', lambda ev: a.append(ev))
        bus.subscribe('foo', lambda ev: b.append(ev))
        bus.publish('foo')
        await asyncio.wait_for(self._until(lambda: a and b), 1)
        self.assertEqual(len(a), 1)
        self.assertEqual(len(b), 1)

    async def test_events_delivered_in_order(self):
        bus = EventBus()
        received = []
        bus.subscribe('foo', lambda ev: received.append(ev.data))
        for i in range(5):
            bus.publish('foo', i)
        await asyncio.wait_for(self._until(lambda: len(received) == 5), 1)
        self.assertEqual(received, [0, 1, 2, 3, 4])

    async def test_callback_exception_does_not_stop_further_delivery(self):
        bus = EventBus()
        received = []
        def bad_cb(ev):
            raise ValueError("boom")
        bus.subscribe('foo', bad_cb)
        bus.subscribe('foo', lambda ev: received.append(ev))
        bus.publish('foo')
        bus.publish('foo')
        await asyncio.wait_for(self._until(lambda: len(received) == 2), 1)
        self.assertEqual(len(received), 2)

    async def test_unsubscribe_stops_delivery(self):
        bus = EventBus()
        received = []
        token = bus.subscribe('foo', lambda ev: received.append(ev))
        bus.unsubscribe(token)
        bus.publish('foo')
        await asyncio.sleep(0.05)
        self.assertEqual(received, [])

    async def test_other_events_not_delivered(self):
        bus = EventBus()
        received = []
        bus.subscribe('foo', lambda ev: received.append(ev))
        bus.publish('bar')
        await asyncio.sleep(0.05)
        self.assertEqual(received, [])

    async def _until(self, predicate):
        while not predicate():
            await asyncio.sleep(0)


if __name__ == '__main__':
    unittest.main()
