import math
import utime
import asyncio
import gc
import textbox

class AnalogueClockDisplay:
    def __init__(self, display, rtc):
        self.display = display
        self.rtc = rtc
        
        self.display_width, self.display_height = self.display.get_bounds()
        
        # Top 70 pixels are usually reserved for the global time/date display
        self.y_start = 70
        self.avail_height = self.display_height - self.y_start
        
        self.cx = self.display_width // 2
        self.cy = self.y_start + self.avail_height // 2
        
        # Base the radius on the smallest dimension available
        self.radius = min(self.display_width, self.avail_height) // 2 - 10
        
        self._last_hour = -1
        self._last_minute = -1
        self._last_second = -1

    CREATION_PRIORITY = 1
    
    def create(provider):
        rtc = provider.get('remotetime.RemoteTime')
        if not rtc:
            print('Falling back to machine.RTC as remotetime.RemoteTime unavailable')
            import machine
            rtc = machine.RTC()
        return AnalogueClockDisplay(provider['display'], rtc)

    async def start(self):
        await self.activate()
        
    def should_activate(self):
        # Always available as a screen
        return True
        
    async def activate(self):
        # Reset state so it redraws immediately when activated
        self._last_hour = -1
        self._last_minute = -1
        self._last_second = -1
        
        # Clear our section of the screen
        self.display.rect(0, self.y_start, self.display_width, self.avail_height, 0x000000, True)
        
        while True:
            await self.update()
            # Update often enough to feel responsive when the second turns
            await asyncio.sleep(0.1)

    async def update(self):
        now = self.rtc.datetime()
        # datetime tuple on MicroPython: (year, month, day, weekday, hour, minute, second, subsecond)
        hour = now[4]
        minute = now[5]
        second = now[6]
        
        if self._last_second == second and self._last_minute == minute and self._last_hour == hour:
            return

        self._last_hour = hour
        self._last_minute = minute
        self._last_second = second
        
        # Clear the display area allocated to this module
        self.display.rect(0, self.y_start, self.display_width, self.avail_height, 0x000000, True)
        
        # Draw clock face circle boundary
        try:
            # Thicken the clock frame by drawing multiple concentric ellipses
            for r_offset in range(-2, 3):
                self.display.ellipse(self.cx, self.cy, self.radius + r_offset, self.radius + r_offset, 0xFFFFFF, False)
        except AttributeError:
            pass
            
        # Draw hour marks and numbers
        for i in range(12):
            angle = i * math.pi / 6 - math.pi / 2
            
            # Make 12, 3, 6, 9 marks slightly longer/bolder
            mark_len = 15 if i % 3 == 0 else 8
            
            x1 = int(self.cx + math.cos(angle) * (self.radius - mark_len))
            y1 = int(self.cy + math.sin(angle) * (self.radius - mark_len))
            x2 = int(self.cx + math.cos(angle) * self.radius)
            y2 = int(self.cy + math.sin(angle) * self.radius)
            
            # Thicker hour marks
            for offset in range(-1, 2):
                ox = int(math.cos(angle + math.pi/2) * offset)
                oy = int(math.sin(angle + math.pi/2) * offset)
                self.display.line(x1 + ox, y1 + oy, x2 + ox, y2 + oy, 0xFFFFFF)
            
            # Draw number inside the mark
            number = 12 if i == 0 else i
            num_radius = self.radius - mark_len - 15  # pull in closer to center
            
            # The textbox module renders around the top-left of the given bounds
            # We want to center the text at the target point, so we create a small
            # bounding box centered on that point.
            num_x = int(self.cx + math.cos(angle) * num_radius)
            num_y = int(self.cy + math.sin(angle) * num_radius)
            
            # Create a 30x30 bounding box centered on num_x, num_y
            box_size = 30
            bx = num_x - (box_size // 2)
            by = num_y - (box_size // 2)
            
            await textbox.draw_textbox(self.display, str(number), bx, by, box_size, box_size, color=0xFFFFFF, font='small', align='center', valign='middle')

            
        # Draw hands
        # Helper to draw a thick line for hands
        def draw_thick_hand(angle, length, thickness, color):
            hx = int(self.cx + math.cos(angle) * length)
            hy = int(self.cy + math.sin(angle) * length)
            
            # Try to use poly for filled thick hand, fallback to multiple lines
            import array
            nx = math.cos(angle + math.pi/2) * (thickness / 2.0)
            ny = math.sin(angle + math.pi/2) * (thickness / 2.0)
            
            try:
                pts = array.array('h', [
                    int(self.cx - nx), int(self.cy - ny),
                    int(hx - nx), int(hy - ny),
                    int(hx + nx), int(hy + ny),
                    int(self.cx + nx), int(self.cy + ny)
                ])
                self.display.poly(0, 0, pts, color, True)
            except (AttributeError, TypeError, ValueError):
                # Fallback to drawing parallel lines
                for r in range(-thickness//2, thickness//2 + 1):
                    ox = int(math.cos(angle + math.pi/2) * r)
                    oy = int(math.sin(angle + math.pi/2) * r)
                    self.display.line(self.cx + ox, self.cy + oy, hx + ox, hy + oy, color)

        # Hour hand (short and very thick)
        hour_angle = (hour % 12 + minute / 60) * math.pi / 6 - math.pi / 2
        draw_thick_hand(hour_angle, self.radius * 0.5, 8, 0xFFFFFF)
        
        # Minute hand (longer and medium thick)
        min_angle = (minute + second / 60) * math.pi / 30 - math.pi / 2
        draw_thick_hand(min_angle, self.radius * 0.8, 4, 0xCCCCCC)
        
        # Second hand (longest and thin)
        sec_angle = second * math.pi / 30 - math.pi / 2
        draw_thick_hand(sec_angle, self.radius * 0.9, 2, 0xFF0000)
        
        # Draw center point
        try:
            self.display.ellipse(self.cx, self.cy, 6, 6, 0xFFFFFF, True)
            self.display.ellipse(self.cx, self.cy, 2, 2, 0x000000, True)
        except AttributeError:
            pass
            
        # Only update our region
        self.display.update((0, self.y_start, self.display_width, self.avail_height))
