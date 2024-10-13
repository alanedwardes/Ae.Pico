import sys
sys.path.insert(1, '../shims')
sys.path.insert(1, '../libraries')

import unittest
import ws

class TestWebSockets(unittest.IsolatedAsyncioTestCase):

    ENDPOINT = 'wss://c4x3tpp039.execute-api.eu-west-1.amazonaws.com/default'

    async def test_connect(self):
        async with await ws.connect(self.ENDPOINT) as socket:
            await socket.send('{"type":"ping"}')
            response = await socket.recv()            
            self.assertEqual('{"type":"pong"}', response)

    async def test_disconnected(self):
        async with await ws.connect(self.ENDPOINT) as socket:
            await socket.send('{"type":"disconnect"}')
            with self.assertRaises(ws.ConnectionClosed):
                await socket.recv()
        

if __name__ == '__main__':
    unittest.main()
