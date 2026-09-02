import sys
sys.path.insert(1, '../libraries')
sys.path.insert(1, '../cpython')

import unittest
from hassws import HassWs


def make_hassws():
    return HassWs('ws://hass.example', 'token', {})


class TestHassWsEntityCache(unittest.IsolatedAsyncioTestCase):

    async def test_entities_survive_reset(self):
        h = make_hassws()
        h.process_event({'a': {'climate.x': {'s': 'heat', 'a': {'temperature': 21.0}}}})
        self.assertIn('climate.x', h.entities)
        await h.stop()
        self.assertIn('climate.x', h.entities)
        self.assertEqual(h.entities['climate.x']['s'], 'heat')

    async def test_resubscribe_reuses_existing_dict_identity(self):
        h = make_hassws()
        h.process_event({'a': {'climate.x': {'s': 'heat', 'a': {'temperature': 21.0}}}})
        existing = h.entities['climate.x']
        await h.stop()
        h.process_event({'a': {'climate.x': {'s': 'off', 'a': {'temperature': 18.0}}}})
        self.assertIs(h.entities['climate.x'], existing)
        self.assertEqual(h.entities['climate.x']['s'], 'off')
        self.assertEqual(h.entities['climate.x']['a']['temperature'], 18.0)

    async def test_steady_state_change_updates_in_place(self):
        h = make_hassws()
        h.process_event({'a': {'climate.x': {'s': 'heat', 'a': {'temperature': 21.0}}}})
        existing = h.entities['climate.x']
        h.process_event({'c': {'climate.x': {'+': {'a': {'temperature': 22.0}}}}})
        self.assertIs(h.entities['climate.x'], existing)
        self.assertEqual(h.entities['climate.x']['a']['temperature'], 22.0)

    async def test_entity_callback_fires_on_add_and_change(self):
        h = make_hassws()
        received = []
        h.entity_callbacks['climate.x'] = {lambda eid, ent: received.append((eid, dict(ent)))}
        h.process_event({'a': {'climate.x': {'s': 'heat', 'a': {'temperature': 21.0}}}})
        h.process_event({'c': {'climate.x': {'+': {'s': 'off'}}}})
        self.assertEqual(len(received), 2)
        self.assertEqual(received[1][1]['s'], 'off')


if __name__ == '__main__':
    unittest.main()
