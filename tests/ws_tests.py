import sys
sys.path.insert(1, '../shims')
sys.path.insert(1, '../libraries')

import unittest
import ws

class TestWebSockets(unittest.TestCase):

    ENDPOINT = 'wss://c4x3tpp039.execute-api.eu-west-1.amazonaws.com/default'

    def test_connect(self):
        with ws.connect(self.ENDPOINT) as socket:
            self.assertRaises(ws.NoDataException, socket.recv)
            
            socket.send('{"type":"ping"}')

            response = None

            while True:
                try:
                    response = socket.recv()
                    break
                except ws.NoDataException:
                    pass
            
            self.assertEqual('{"type":"pong"}', response)

    def test_disconnected(self):
        with ws.connect(self.ENDPOINT) as socket:
            self.assertRaises(ws.NoDataException, socket.recv)
            
            socket.send('{"type":"disconnect"}')

            while True:
                try:
                    socket.recv()
                except ws.NoDataException:
                    pass
                except ws.ConnectionClosed:
                    break
        

if __name__ == '__main__':
    unittest.main()