import utime
import asyncio

class TimeDisplay:
    MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
    DAYS = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
    
    def __init__(self, display, rtc):
        self.display = display
        self.rtc = rtc
        
        self.white = 0
        self.display.update_pen(self.white, 255, 255, 255)

        self.black = 2
        self.display.update_pen(self.black, 0, 0, 0)
        
        self.red = 5
        self.display.update_pen(self.red, 242, 106, 48)

        self.display_width, self.display_height = self.display.get_bounds()
        self.display_half_width = self.display_width * 0.5
        
        self.last_update_time_ms = 0
        
    def draw_text(self, text, scale, x, y, width):
        text_width = self.display.measure_text(text, scale)
        text_height = scale * 20
        self.display.set_thickness(int(scale * 3))

        text_x = int(width * 0.5 - text_width * 0.5)
        
        half_height = text_height * 0.5
        
        self.display.text(text, int(text_x + x), int(y + half_height), scale=scale)
        
        return int(text_height)
    
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
        self.display.set_font("sans")
        self.display.set_pen(self.black)
        self.display.rectangle(0, 0, self.display_width, 80)

        now = self.rtc.datetime()
        
        spacer = 16
        
        y = spacer
        
        self.display.set_pen(self.white)
        
        screen_width_third = self.display_width / 5
        
        seconds_width = screen_width_third * 1
        time_width = screen_width_third * 3
        
        # Hours and minutes
        y += self.draw_text("%02i:%02i" % (now[4], now[5]), 2.25, 4, y, time_width)
        
        # Seconds and day
        self.draw_text("%s" % self.DAYS[now[3]-1], 1, time_width, 10, seconds_width)
        self.draw_text("%02i" % now[6], 1.2, time_width, 40, seconds_width)
        
        calendar_outline_x = int(time_width + seconds_width)
        calendar_outline_y = 0
        calendar_outline_w = int(seconds_width)
        calendar_outline_h = y + spacer
        
        # Calendar outline
        self.display.set_pen(self.red)
        self.display.rectangle(calendar_outline_x, calendar_outline_y, calendar_outline_w, calendar_outline_h)
        
        date_outline_x = calendar_outline_x
        date_outline_y = 36
        date_outline_w = calendar_outline_w
        date_outline_h = 36
        
        # Date outline
        self.display.set_pen(self.white)
        self.display.rectangle(date_outline_x, date_outline_y, date_outline_w, date_outline_h)
        
        # Date and month
        self.draw_text("%s" % self.MONTHS[now[1]-1], 1, time_width + seconds_width, 10, seconds_width)
        self.display.set_pen(self.black)
        self.draw_text("%02i" % now[2], 1.2, date_outline_x, date_outline_y + 8, date_outline_w)
        
        self.display.update()
