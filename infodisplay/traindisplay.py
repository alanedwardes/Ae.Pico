import utime
import asyncio
import textbox

class TrainDisplay:
    def __init__(self, display, entity_id, hass):
        self.display = display
        self.entity_id = entity_id
        self.hass = hass
        self.is_active = True

        self.display_width, self.display_height = self.display.get_bounds()
        self.departures_last_updated = utime.ticks_ms()
   
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['trains']
        return TrainDisplay(provider['display'], config['entity_id'], provider['hassws.HassWs'])
    
    def entity_updated(self, entity_id, entity):
        self.departures_last_updated = utime.ticks_ms()
        self.update()
    
    async def start(self):
        await self.hass.subscribe([self.entity_id], self.entity_updated)
        await asyncio.Event().wait()

    def should_activate(self):
        return len(self.get_departures()) > 0 and utime.ticks_diff(utime.ticks_ms(), self.departures_last_updated) < 600_000

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
            self.display.set_pen(self.display.create_pen(242, 106, 48))
        elif departure['del']:
            self.display.set_pen(self.display.create_pen(254, 219, 0))
        else:
            self.display.set_pen(self.display.create_pen(255, 255, 255))
        
        # Define column widths and positions
        time_width = 50
        destination_width = 160
        platform_width = 20
        expected_width = 90
        
        # Draw each column using textbox
        textbox.draw_textbox(self.display, scheduled, 0, y_offset, time_width, 20, font='bitmap8', scale=2)
        textbox.draw_textbox(self.display, destination, time_width, y_offset, destination_width, 20, font='bitmap8', scale=2, align='left')
        textbox.draw_textbox(self.display, platform, time_width + destination_width, y_offset, platform_width, 20, font='bitmap8', scale=2)
        textbox.draw_textbox(self.display, expected, time_width + destination_width + platform_width, y_offset, expected_width, 20, font='bitmap8', scale=2)
        
        return 20
    
    def get_departures(self):
        return self.hass.entities.get(self.entity_id, {}).get('a', {}).get('services', [])

    def __update(self):
        departures = self.get_departures()
        
        y_offset = 70
        
        self.display.set_pen(self.display.create_pen(0, 0, 0))
        self.display.rectangle(0, y_offset, self.display_width, self.display_height - y_offset)
        
        y_offset += 8
        
        for row in range(0, len(departures)):
            y_offset += self.__draw_departure_row(departures[row], y_offset)
            
        self.display.update()