import asyncio

class ScrollClock:
    def __init__(self, graphics, scroll, rtc, hass, occupancy_entity_id):
        self.graphics = graphics
        self.scroll = scroll
        self.rtc = rtc
        self.occupancy_entity_id = occupancy_entity_id
        self.hass = hass
        self.occupancy = True
    
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['display']
        rtc = provider.get('remotetime.RemoteTime')
        if not rtc:
            print('Falling back to machine.RTC as remotetime.Remotetime unavailable')
            import machine
            rtc = machine.RTC()
        return ScrollClock(provider['graphics'], provider['scroll'], rtc, provider['hassws.HassWs'], config['occupancy_entity_id'])
    
    async def start(self):
        await self.hass.subscribe([self.occupancy_entity_id], self.occupancy_updated)
        
        while True:
            self.update()
            # Assume subseconds component of RTC means milliseconds
            await asyncio.sleep_ms(max(min(1000 - self.rtc.datetime()[7], 1000), 0))
    
    def update(self):
        self.graphics.set_pen(0)
        self.graphics.clear()
        if self.occupancy:
            self.graphics.set_font("bitmap8")
            self.graphics.set_pen(32)
            now = self.rtc.datetime()
            text = "%02i%02i" % (now[4], now[5])
            for i in range(0, len(text)):
                x = i * 4
                if i >= 2:
                    x += 1
                self.graphics.text(text[i], x, 0, scale=1)
        self.scroll.update(self.graphics)

    def occupancy_updated(self, entity_id, entity):
        self.occupancy = entity['s'] == 'on'  
