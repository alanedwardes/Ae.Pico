import math
import utime
import asyncio

class TimeDisplay:
    MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
    DAYS = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
    
    def __init__(self, display, rtc):
        self.display = display
        self.rtc = rtc
        
        self.white = 0
        self.black = 1
        self.highlight = 2
        
        self.display.update_pen(self.white, 255, 255, 255)
        self.display.update_pen(self.black, 0, 0, 0)
        self.display.update_pen(self.highlight, 242, 106, 48)

        self.display_width, self.display_height = self.display.get_bounds()
        self.display_half_width = self.display_width * 0.5
        
        self.last_update_time_ms = 0
        
    def draw_text(self, text, scale, x, y, width, height):
        thickness = scale * 3
        
        self.display.set_thickness(math.floor(thickness))
        
        #text_height = (scale * 20) + thickness
        #half_height = text_height * 0.5

        #self.display.set_pen(self.highlight)
        #self.display.rectangle(math.floor(x), math.floor(y), math.ceil(width), math.ceil(height))

        text_width = self.display.measure_text(text, scale) + thickness
        text_x = width * 0.5 - text_width * 0.5
        
        half_height = height * 0.5
        
        #self.display.set_pen(self.white)
        self.display.text(text, math.floor(text_x + x + (thickness * 0.5)), math.floor(y + half_height + (thickness * 0.5)), scale=scale)
    
    CREATION_PRIORITY = 1
    def create(provider):
        rtc = provider.get('remotetime.RemoteTime')
        if not rtc:
            print('Falling back to machine.RTC as remotetime.Remotetime unavailable')
            import machine
            rtc = machine.RTC()
        return TimeDisplay(provider['display'], rtc)
    
    async def start(self):
        while True:
            self.update()
            # Assume subseconds component of RTC means milliseconds
            sleep_ms = max(min(1000 - self.rtc.datetime()[7], 1000), 0)
            await asyncio.sleep(sleep_ms / 1000)

    def update(self):      
        start_update_ms = utime.ticks_ms()
        self.__update()
        self.last_update_time_ms = utime.ticks_diff(utime.ticks_ms(), start_update_ms)

    def __update(self):
        height = 70
        
        self.display.set_font("sans")
        self.display.set_pen(self.black)
        self.display.rectangle(0, 0, self.display_width, height)

        now = self.rtc.datetime()
                
        section_width = self.display_width / 5
        section_height = height / 2
        
        time_width = self.display_width - section_width * 2
        
        self.display.set_pen(self.white)
        self.draw_text("%02i:%02i" % (now[4], now[5]), 2.25, 0, 0, time_width, height)
        
        self.draw_text(f"{self.DAYS[now[3]-1]}", 1, time_width, 0, section_width, section_height)
        self.draw_text("%02i" % now[6], 1.2, time_width, section_height, section_width, section_height)
        
        self.display.set_pen(self.highlight)
        self.display.rectangle(int(time_width + section_width), 0, int(section_width), int(section_height))

        self.display.set_pen(self.white)
        self.draw_text(f"{self.MONTHS[now[1]-1]}", 1, time_width + section_width, 0, section_width, section_height)
        
        self.display.rectangle(int(time_width + section_width), int(section_height), int(section_width), int(section_height))
        
        self.display.set_pen(self.black)
        self.draw_text("%02i" % now[2], 1.2, time_width + section_width, section_height, section_width, section_height)
        
        self.display.update()