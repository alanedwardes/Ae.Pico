import asyncio

class DisplayFocus:
    def __init__(self, hass_ws, event_bus, entities, focus_duration_ms=5000):
        self.hass_ws = hass_ws
        self.event_bus = event_bus
        self.entities = entities
        self.focus_duration_ms = focus_duration_ms
        self.last_states = {entity_id: None for entity_id in entities.keys()}
        self.initial_update = True
        
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['displayfocus']
        return DisplayFocus(
            provider['hassws.HassWs'],
            provider['eventbus.EventBus'],
            config.get('entities', {}),
            config.get('focus_duration_ms', 5000)
        )
    
    async def start(self):
        await self.hass_ws.subscribe(list(self.entities.keys()), self._entity_changed)
        await asyncio.Event().wait()
    
    def _entity_changed(self, entity_id, entity):
        if entity_id not in self.entities:
            return
            
        current_state = entity.get('s')
        if current_state != self.last_states[entity_id]:
            self.last_states[entity_id] = current_state
            
            if self.initial_update:
                self.initial_update = False
                print(f"EntityFocus: {entity_id} initial state {current_state}")
            else:
                print(f"EntityFocus: {entity_id} changed to {current_state}")
                
                payload = self.entities[entity_id].copy()
                payload['hold_ms'] = self.focus_duration_ms
                
                self.event_bus.publish('focus.request', payload)
