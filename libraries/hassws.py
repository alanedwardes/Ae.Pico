import ws
import json
import random
import time

try:
    from traceback import print_exception
except ImportError:
    from sys import print_exception

class HassWs:
    def __init__(self, url, token):
        self.url = url
        self.token = token
        
        self.entity_callbacks = {}
        self.subscribed_entities = []
        self.entities_updated = None
        self._reset()

    def is_active(self):
        return self.socket is not None and self.authenticated and self.message_id > 1
    
    def update(self):
        try:
            if self.socket is None:
                self.socket = ws.connect(self.url + '/api/websocket')
            self._process_message(self.socket.recv())
        except ws.NoDataException:
            if self.authenticated:
                self._pump_queue()
        except Exception as e:
            print_exception(e)
            self.close()
            time.sleep(1)

    def close(self):
        if self.socket is not None:
            try:
                self.socket.close()
            except:
                pass # The socket might be broken
        self._reset()
    
    def _pump_queue(self):
        while len(self.send_queue) > 0:
            message = self.send_queue.pop()
            self.message_id += 1
            print(message)
            self.socket.send(message % self.message_id)
    
    def _process_message(self, message):
        message = json.loads(message)
        message_type = message.get('type')
        
        if message_type == 'auth_required':
            self._authenticate()
        elif message_type == 'auth_invalid':
            raise Exception('Invalid authentication')
        elif message_type == 'auth_ok':
            self.authenticated = True
            self._subscribe(self.subscribed_entities)
        elif message_type == 'event':
            self.process_event(message['event'])
        elif message_type == 'result':
            print("Result: %s" % message)
        else:
            print("Unknown message: %s" % message)
    
    def _reset(self):
        self.socket = None
        self.authenticated = False
        self.message_id = 1
        self.send_queue = []
        self.entities = {}
    
    def _authenticate(self):
        self.socket.send('{"type":"auth","access_token":"%s"}' % self.token)
        
    def action(self, domain, service, data, entity_id):
        self.send_queue.append('{"id":%%i,"type":"call_service","domain":"%s","service":"%s","service_data":%s,"target":{"entity_id":"%s"}}' % (domain, service, json.dumps(data), entity_id))

    def subscribe(self, entity_id, callback = None):
        if entity_id is not None:
            if callback is not None:
                self.entity_callbacks[entity_id] = callback
            self.subscribed_entities.append(entity_id)
            self._subscribe([entity_id])
            
    def _subscribe(self, entity_ids):
        if entity_ids and self.authenticated:
            self.send_queue.append('{"id":%%i,"type":"subscribe_entities","entity_ids":["%s"]}' % ('","'.join(entity_ids)))
            
    def _execute_callback(self, callback, args):
        if callback is None or args is None:
            return
        
        try:
            callback(args)
        except Exception as e:
            print('Error executing callback', e)

    def process_event(self, event):
        if 'a' in event:
            for entity_id in event['a']:
                self.entities[entity_id] = event['a'][entity_id]
                self._execute_callback(self.entity_callbacks.get(entity_id, None), self.entities[entity_id])
        elif 'c' in event:
            for entity_id in event['c']:
                change = event['c'][entity_id]['+']
                if 's' in change:
                    self.entities[entity_id]['s'] = change['s']
                if 'a' in change:
                    self.entities[entity_id]['a'] |= change['a']
                self._execute_callback(self.entity_callbacks.get(entity_id, None), self.entities[entity_id])
        else:
            print('Unrecognised event structure: %s', event)
        self._execute_callback(self.entities_updated, self.entities)
