import math
import utime
import asyncio
import textbox

class TimeDisplay:
    MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
    DAYS = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
    
    def __init__(self, display, rtc):
        self.display = display
        self.rtc = rtc
        
        self.display_width, self.display_height = self.display.get_bounds()
        self.display_half_width = self.display_width * 0.5
        
        self.last_update_time_ms = 0
        
    
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
        width = self.display_width - 64
        
        self.display.rect(0, 0, width, height, self.display.create_pen(0, 0, 0), True)

        now = self.rtc.datetime()
                
        section_height = height / 2
        
        time_width = 200
        textbox.draw_textbox(self.display, '%02i:%02i' % (now[4], now[5]), 0, 0, time_width, height, color=self.display.create_pen(255, 255, 255), font='numbers64', scale=1)

        date_seconds_width = self.display_width - time_width - 64 # the temp display is 64px        
        textbox.draw_textbox(self.display, f'{self.DAYS[now[3]-1]}', time_width, 0, date_seconds_width, section_height, color=self.display.create_pen(255, 255, 255), font='notosans32', scale=1)
        textbox.draw_textbox(self.display, '%02i' % now[6], time_width, section_height, date_seconds_width, section_height, color=self.display.create_pen(255, 255, 255), font='notosans32', scale=1)
        
        self.display.update()