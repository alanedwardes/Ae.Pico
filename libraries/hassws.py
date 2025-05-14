import ws
import json
import utime
import asyncio

class HassWs:
    def __init__(self, url, token):
        self.url = url
        self.token = token
        
        self.entity_callbacks = {}
        self.subscribed_entities = set()
        self.entities_updated = set()
        self._reset()

    def is_active(self):
        return self.socket is not None and self.authenticated and self.message_id > 1
    
    def create(provider):
        config = provider['config']['hass']
        return HassWs(config['ws'], config['token'])
    
    async def start(self):
        try:
            self.socket = await ws.connect(self.url + '/api/websocket')
            await asyncio.gather(self.__listen(), self.__keepalive())
        finally:
            await self.stop()
    
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
        if not self.authenticated:
            raise Exception("Not authenticated")
        
        self.message_id += 1
        await self.socket.send('{"id":%i,"type":"call_service","domain":"%s","service":"%s","service_data":%s,"target":{"entity_id":"%s"}}' % (self.message_id, domain, service, json.dumps(data), entity_id))

    async def subscribe(self, entity_ids, callback = None):
        if not entity_ids:
            return
        
        if callback:
            for entity_id in entity_ids:
                if entity_id in self.entity_callbacks:
                    self.entity_callbacks[entity_id].add(callback)
                else:
                    self.entity_callbacks[entity_id] = {callback}
                    
        entity_ids_to_subscribe = set(entity_ids) - self.subscribed_entities
        if not entity_ids_to_subscribe:
            return
        
        if self.authenticated:
            await self._subscribe(entity_ids_to_subscribe)
        
        self.subscribed_entities.update(entity_ids_to_subscribe)
    
    async def _subscribe(self, entity_ids):
        if entity_ids and self.authenticated:
            self.message_id += 1
            await self.socket.send('{"id":%i,"type":"subscribe_entities","entity_ids":["%s"]}' % (self.message_id, '","'.join(entity_ids)))
            
    def _execute_callback(self, callbacks, *args):
        if not callbacks or not args:
            return
        
        for callback in callbacks:
            try:
                callback(*args)
            except Exception as e:
                print('Error executing callback', e)

    def process_event(self, event):
        # Event types: https://github.com/home-assistant/core/blob/9428127021325b9f7500e03a9627929840bfa2e4/homeassistant/components/websocket_api/messages.py#L43-L45
        # Change types: https://github.com/home-assistant/core/blob/9428127021325b9f7500e03a9627929840bfa2e4/homeassistant/components/websocket_api/messages.py#L11-L17
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
        elif 'r' in event:
            for entity_id in event['r']:
                print(f'Removing {entity_id}')
                self.entities.pop(entity_id, None)
        else:
            print('Unrecognised event structure: %s', event)
        self._execute_callback(self.entities_updated, self.entities)
