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
        
        # Cache last-rendered strings to avoid unnecessary redraws
        self._last_time_text = None   # HH:MM
        self._last_day_text = None    # Day-of-week
        self._last_sec_text = None    # SS
        
    
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
        print(f"TimeDisplay: {self.last_update_time_ms}ms")

    def __update(self):
        # Layout constants
        height = 70
        section_height = height // 2
        time_width = 200
        date_seconds_width = self.display_width - time_width - 64  # the temp display is 64px

        now = self.rtc.datetime()

        # Compute current texts
        time_text = '%02i:%02i' % (now[4], now[5])
        day_text = f'{self.DAYS[now[3]-1]}'
        sec_text = '%02i' % now[6]

        # Redraw HH:MM only when it changes
        if time_text != self._last_time_text:
            # Clear time area then draw
            self.display.rect(0, 0, time_width, height, 0x0000, True)
            textbox.draw_textbox(self.display, time_text, 0, 0, time_width, height, color=0xFFFF, font='headline', scale=1)
            self._last_time_text = time_text
            # Render only the time region
            self.display.update((0, 0, time_width, height))

        # Redraw day-of-week only when it changes
        if day_text != self._last_day_text:
            self.display.rect(time_width, 0, date_seconds_width, section_height, 0x0000, True)
            textbox.draw_textbox(self.display, day_text, time_width, 0, date_seconds_width, section_height, color=0xFFFF, font='regular', scale=1)
            self._last_day_text = day_text
            # Render only the day region
            self.display.update((time_width, 0, date_seconds_width, section_height))

        # Redraw seconds each time they change
        if sec_text != self._last_sec_text:
            self.display.rect(time_width, section_height, date_seconds_width, section_height, 0x0000, True)
            textbox.draw_textbox(self.display, sec_text, time_width, section_height, date_seconds_width, section_height, color=0xFFFF, font='regular', scale=1)
            self._last_sec_text = sec_text
            # Render only the seconds region
            self.display.update((time_width, section_height, date_seconds_width, section_height))