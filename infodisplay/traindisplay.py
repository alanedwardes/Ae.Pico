import utime
import asyncio

class TrainDisplay:
    def __init__(self, display, entity_id, attribute, hass):
        self.display = display
        self.entity_id = entity_id
        self.attribute = attribute
        self.hass = hass
        self.is_active = True
        
        self.white = 0
        self.black = 1
        self.red = 2
        
        self.yellow = 3
        self.orange = 4

        self.display_width, self.display_height = self.display.get_bounds()
        
        self.departures = []
        self.departures_last_updated = utime.localtime()
   
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['trains']
        return TrainDisplay(provider['display'], config['entity_id'], config['attribute'], provider['hassws.HassWs'])
    
    def entity_updated(self, entity_id, entity):
        self.departures = entity['a'].get(self.attribute, [])
        self.departures_last_updated = utime.localtime()
        self.update()
    
    async def start(self):
        await self.hass.subscribe([self.entity_id], self.entity_updated)
        await asyncio.Event().wait()

    def should_activate(self):
        return len(self.departures) > 0

    def activate(self, new_active):
        self.is_active = new_active
        if self.is_active:
            self.update()

    def update(self):
        if self.is_active == False:
            return
        
        self.__update()
        
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
        return 20

    def __update(self):
        self.display.update_pen(self.white, 255, 255, 255)
        self.display.update_pen(self.black, 0, 0, 0)
        self.display.update_pen(self.red, 242, 106, 48)
        self.display.update_pen(self.yellow, 254, 219, 0)
        self.display.update_pen(self.orange, 250, 163, 26)
        
        y_offset = 70
        
        self.display.set_font("bitmap8")
        self.display.set_pen(self.black)
        self.display.rectangle(0, y_offset, self.display_width, self.display_height - y_offset)
        self.display.set_pen(self.orange)
        
        for row in range(0, len(self.departures)):
            y_offset += self.__draw_departure_row(self.departures[row], y_offset)
            
        self.display.set_pen(self.orange)
        self.display.text("Last updated: %02i:%02i:%02i" % (self.departures_last_updated[3], self.departures_last_updated[4], self.departures_last_updated[5]), 0, y_offset, scale=2)
        self.display.update()
