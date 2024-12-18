import ws
import json
import utime
import asyncio

class HassWs:
    def __init__(self, url, token, nic):
        self.url = url
        self.token = token
        self.nic = nic
        
        self.entity_callbacks = {}
        self.subscribed_entities = []
        self.entities_updated = None
        self._reset()

    def is_active(self):
        return self.socket is not None and self.authenticated and self.message_id > 1
    
    async def start(self):
        while not self.nic.isconnected():
            await asyncio.sleep_ms(100)
        
        self.socket = await ws.connect(self.url + '/api/websocket')
        await asyncio.gather(self.__listen(), self.__keepalive())
    
    async def __listen(self):
        while True:
            await self._process_message()
            
    async def __keepalive(self):
        while True:
            await asyncio.sleep(30)
            self.message_id += 1
            await self.socket.send('{"id":%i,"type":"ping"}' % self.message_id)
            await asyncio.sleep(10)
            if utime.ticks_diff(utime.ticks_ms(), self.last_message_time) > 15_000:
                raise Exception('Timeout')
    
    async def stop(self):
        if self.socket is not None:
            try:
                await self.socket.close()
            except:
                pass # The socket might be broken
        self._reset()
    
    async def _process_message(self):
        message = await self.socket.recv()        
        if message is None:
            return
        
        message = json.loads(message)
        message_type = message.get('type')
        self.last_message_time = utime.ticks_ms()
        
        if message_type == 'auth_required':
            await self._authenticate()
        elif message_type == 'auth_invalid':
            raise Exception('Invalid authentication')
        elif message_type == 'auth_ok':
            self.authenticated = True
            await self._subscribe(self.subscribed_entities)
        elif message_type == 'event':
            self.process_event(message['event'])
        elif message_type == 'result':
            print("Result: %s" % message)
        elif message_type == 'pong':
            pass
        else:
            raise Exception("Unknown message: %s" % message)
    
    def _reset(self):
        self.socket = None
        self.authenticated = False
        self.message_id = 1
        self.entities = {}
    
    async def _authenticate(self):
        await self.socket.send('{"type":"auth","access_token":"%s"}' % self.token)
        
    async def action(self, domain, service, data, entity_id):
        self.message_id += 1
        await self.socket.send('{"id":%i,"type":"call_service","domain":"%s","service":"%s","service_data":%s,"target":{"entity_id":"%s"}}' % (self.message_id, domain, service, json.dumps(data), entity_id))

    def subscribe(self, entity_id, callback = None):
        if self.authenticated:
            raise Exception('Subscribe after authentication is not yet supported')
        
        if entity_id is None:
            return
        
        if entity_id in self.subscribed_entities:
            return
        
        if callback is not None:
            self.entity_callbacks[entity_id] = callback
        
        self.subscribed_entities.append(entity_id)
            
    async def _subscribe(self, entity_ids):
        if entity_ids and self.authenticated:
            self.message_id += 1
            await self.socket.send('{"id":%i,"type":"subscribe_entities","entity_ids":["%s"]}' % (self.message_id, '","'.join(entity_ids)))
            
    def _execute_callback(self, callback, *args):
        if callback is None or args is None:
            return
        
        try:
            callback(*args)
        except Exception as e:
            print('Error executing callback', e)

    def process_event(self, event):
        if 'a' in event:
            for entity_id in event['a']:
                self.entities[entity_id] = event['a'][entity_id]
                self._execute_callback(self.entity_callbacks.get(entity_id, None), entity_id, self.entities[entity_id])
        elif 'c' in event:
            for entity_id in event['c']:
                change = event['c'][entity_id]['+']
                if 's' in change:
                    self.entities[entity_id]['s'] = change['s']
                if 'a' in change:
                    self.entities[entity_id]['a'] |= change['a']
                self._execute_callback(self.entity_callbacks.get(entity_id, None), entity_id, self.entities[entity_id])
        else:
            print('Unrecognised event structure: %s', event)
        self._execute_callback(self.entities_updated, self.entities)
