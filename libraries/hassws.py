import ws
import json
import random

class HassWs:
    def __init__(self, url, token):
        self.url = url
        self.token = token
        
        self.socket = None
        self.subscribed_entities = []
        self.entities_updated = None
        self.authenticated = False
        self.entities = {}
    
    def update(self):
        try:
            if self.socket is None:
                self.socket = ws.connect(self.url + '/api/websocket')
            self._process_message(self.socket.recv())
        except ws.NoDataException:
            return
        except Exception as e:
            print(e)
            self._reset()
            
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
    
    def _authenticate(self):
        self.socket.send('{"type":"auth","access_token":"%s"}' % self.token)
            
    def subscribe(self, entity_id):
        self.subscribed_entities.append(entity_id)
        self._subscribe([entity_id])
        
    def _subscribe(self, entity_ids):
        if entity_ids and self.authenticated:
            self.socket.send('{"id": %i,"type":"subscribe_entities","entity_ids":["%s"]}' % (random.getrandbits(4), '","'.join(entity_ids)))

    def process_event(self, event):
        if 'a' in event:
            for entity_id in event['a']:
                self.entities[entity_id] = event['a'][entity_id]
        elif 'c' in event:
            for entity_id in event['c']:
                change = event['c'][entity_id]['+']
                if 's' in change:
                    self.entities[entity_id]['s'] = change['s']
                self.entities[entity_id]['a'] |= change['a']
        else:
            print('Unrecognised event structure: %s', event)
        if self.entities_updated is not None:
            self.entities_updated(self.entities)
