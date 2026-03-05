import asyncio

class TouchDebugDisplay:
    def __init__(self, display_provider):
        self.display = display_provider
        self.points = []
        self.max_points = 20
        self.point_radius = 2
        self.point_color = 0x00FF00  # GREEN

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
            self.points.append(point)
            if len(self.points) > self.max_points:
                self.points.pop(0)

    async def start(self):
        while True:
            if self.display and self.points:
                try:
                    # Draw the latest touch points
                    for p in self.points:
                        radius = self.point_radius
                        self.display.ellipse(p[0], p[1], radius, radius, self.point_color, fill=True)
                        d = radius * 2 + 2
                        self.display.update((max(0, p[0]-radius-1), max(0, p[1]-radius-1), d, d))
                except AttributeError:
                    pass
            await asyncio.sleep_ms(50)
