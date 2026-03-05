import asyncio
import time
import random

class TouchDebugDisplay:
    def __init__(self, display_provider):
        self.display = display_provider
        self.points = []
        self.max_points = 100
        self.point_radius = 8
        self.fade_duration_ms = 2000

    CREATION_PRIORITY = 4  # Needs to run after display and touch

    def create(provider):
        display = provider.get('display')
        if not display:
            print("Warning: TouchDebugDisplay requires a 'display' provider.")
            return None
            
        instance = TouchDebugDisplay(display)
        
        touch = provider.get('touch')
        if touch:
            touch.subscribe(instance.handle_touch)
        else:
            print("Warning: TouchDebugDisplay could not find 'touch'.")
            
        return instance

    def handle_touch(self, point):
        """Called by the Touch abstraction when touched."""
        if point is not None:
            color = random.randint(0, 0xFFFFFF)
            birth_time = time.ticks_ms()
            self.points.append((point[0], point[1], color, birth_time))
            if len(self.points) > self.max_points:
                self.points.pop(0)

    async def start(self):
        while True:
            if self.display and self.points:
                try:
                    current_time = time.ticks_ms()
                    active_points = []
                    
                    for p in self.points:
                        x, y, orig_color, birth_time = p
                        age = time.ticks_diff(current_time, birth_time)
                        
                        if age < self.fade_duration_ms:
                            active_points.append(p)
                            
                            ratio = max(0.0, 1.0 - (age / self.fade_duration_ms))
                            r = int(((orig_color >> 16) & 0xFF) * ratio)
                            g = int(((orig_color >> 8) & 0xFF) * ratio)
                            b = int((orig_color & 0xFF) * ratio)
                            faded_color = (r << 16) | (g << 8) | b
                            
                            radius = self.point_radius
                            self.display.ellipse(x, y, radius, radius, faded_color, fill=True)
                            d = radius * 2 + 2
                            self.display.update((max(0, int(x-radius-1)), max(0, int(y-radius-1)), int(d), int(d)))
                        else:
                            radius = self.point_radius
                            self.display.ellipse(x, y, radius, radius, 0x000000, fill=True)
                            d = radius * 2 + 2
                            self.display.update((max(0, int(x-radius-1)), max(0, int(y-radius-1)), int(d), int(d)))
                            
                    self.points = active_points
                except AttributeError:
                    pass
            await asyncio.sleep_ms(50)
