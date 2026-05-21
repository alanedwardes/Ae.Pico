import asyncio

class ScrollClock:
    def __init__(self, graphics, scroll, time, hass, occupancy_entity_id):
        self.graphics = graphics
        self.scroll = scroll
        self.time = time
        self.occupancy_entity_id = occupancy_entity_id
        self.hass = hass
        self.occupancy = True
    
    CREATION_PRIORITY = 2
    def create(provider):
        config = provider['config']['display']
        return ScrollClock(provider['graphics'], provider['scroll'], provider['time'], provider['hassws.HassWs'], config['occupancy_entity_id'])
    
    async def start(self):
        await self.hass.subscribe([self.occupancy_entity_id], self.occupancy_updated)
        
        while True:
            now = self.update()
            await asyncio.sleep_ms(max(min(1000 - now[8], 1000), 0))
    
    def update(self):
        self.graphics.set_pen(0)
        self.graphics.clear()
        now = self.time.local_time()
        if self.occupancy:
            self.graphics.set_font("bitmap8")
            self.graphics.set_pen(32)
            text = "%02i%02i" % (now[3], now[4])
            for i in range(0, len(text)):
                x = i * 4
                if i >= 2:
                    x += 1
                self.graphics.text(text[i], x, 0, scale=1)
        self.scroll.update(self.graphics)
        return now

    def occupancy_updated(self, entity_id, entity):
        self.occupancy = entity['s'] == 'on'  
