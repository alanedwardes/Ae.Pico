import utime
import asyncio

class TrainDisplay:
    def __init__(self, display, entity_id, attribute, hass, rtc):
        self.display = display
        self.entity_id = entity_id
        self.attribute = attribute
        self.hass = hass
        self.rtc = rtc
        self.is_active = True
        
        self.white = 0
        self.display.update_pen(self.white, 255, 255, 255)

        self.grey = 1
        self.display.update_pen(self.grey, 128, 128, 128)

        self.black = 2
        self.display.update_pen(self.black, 0, 0, 0)
       
        self.red = 5
        self.display.update_pen(self.red, 242, 106, 48)
        
        self.yellow = 8
        self.display.update_pen(self.yellow, 254, 219, 0)
        
        self.orange = 6
        self.display.update_pen(self.orange, 250, 163, 26)

        self.display_width, self.display_height = self.display.get_bounds()
        
        self.departures = []
        self.last_update_time_ms = 0
        self.departures_last_updated = self.rtc.datetime()
   
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['trains']
        rtc = provider.get('remotetime.RemoteTime')
        if not rtc:
            print('Falling back to machine.RTC as remotetime.Remotetime unavailable')
            import machine
            rtc = machine.RTC()
        return TrainDisplay(provider['display'], config['entity_id'], config['attribute'], provider['hassws.HassWs'], rtc)
    
    def entity_updated(self, entity_id, entity):
        self.departures = entity['a'].get(self.attribute, [])[:5]
        self.departures_last_updated = self.rtc.datetime()
        self.update()
    
    async def start(self):
        await self.hass.subscribe([self.entity_id], self.entity_updated)
        
        while True:
            self.update()
            # Assume subseconds component of RTC means milliseconds
            await asyncio.sleep_ms(max(min(1000 - self.rtc.datetime()[7], 1000), 0))

    def should_activate(self):
        return len(self.departures) > 0

    def activate(self, new_active):
        self.is_active = new_active
        if self.is_active:
            self.update()

    def update(self):
        if self.is_active == False:
            return
        
        start_update_ms = utime.ticks_ms()
        self.__update()
        self.last_update_time_ms = utime.ticks_diff(utime.ticks_ms(), start_update_ms)
        
    def __draw_departure_row(self, departure, y_offset):
        destination = departure['dst']
        scheduled = departure['std']
        expected = departure['etd']
        platform = departure['plt']
        if departure['can']:
            self.display.set_pen(self.red)
        elif departure['del']:
            self.display.set_pen(self.yellow)
        else:
            self.display.set_pen(self.white)
        x_offset = 0
        self.display.text('{:.5}'.format(scheduled), x_offset, y_offset, scale=2)
        x_offset += 5 * 10
        self.display.text('{:.16}'.format(destination), x_offset, y_offset, scale=2)
        x_offset += 16 * 10
        self.display.text('{:.1}'.format(platform), x_offset, y_offset, scale=2)
        x_offset += 2 * 10
        self.display.text('{:.9}'.format(expected), x_offset, y_offset, scale=2)
        return 8 * 4

    def __update(self):
        self.display.set_font("bitmap8")
        self.display.set_pen(self.black)
        self.display.clear()
        self.display.set_pen(self.orange)
        
        y_offset = 8
        now = self.rtc.datetime()
        self.display.text("  %02i : %02i : %02i" % (now[4], now[5], now[6]), 0, y_offset, scale=5)
        
        y_offset += 8 * 7
        
        for row in range(0, len(self.departures)):
            y_offset += self.__draw_departure_row(self.departures[row], y_offset)
            
        self.display.set_pen(self.orange)
        self.display.text("Last updated: %02i:%02i:%02i" % (self.departures_last_updated[4], self.departures_last_updated[5], self.departures_last_updated[6]), 0, y_offset, scale=2)
        self.display.update()
