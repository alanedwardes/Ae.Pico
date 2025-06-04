import asyncio
import bitmap

class UvDisplay:
    def __init__(self, display, hass, entity_id):
        self.display = display
        self.hass = hass
        self.is_active = True
        self.entity_id = entity_id
        self.uv = 0
    
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['uv']
        return UvDisplay(provider['display'], provider['hassws.HassWs'], config['entity_id'])
    
    def entity_updated(self, entity_id, entity):
        self.uv = int(entity['s'])
        self.update()
    
    async def start(self):
        await self.hass.subscribe([self.entity_id], self.entity_updated)
        # For testing
        #while True:
        #    self.uv = (self.uv + 1) % 11
        #    self.update()
        #    await asyncio.sleep(1)
        await asyncio.Event().wait()
        
    def sun_cream(self):
        return self.uv > 2
        
    def should_activate(self):
        return self.sun_cream()

    def activate(self, new_active):
        self.is_active = new_active
        if self.is_active:
            self.update()

    def update(self):
        if self.is_active == False:
            return
        
        y_start = 70
        
        display_width, display_height = self.display.get_bounds()
            
        palette = []
        self.set_pen_color((255, 255, 255), palette)
        self.set_pen_color((0, 0, 0), palette)
        self.display.rectangle(0, y_start, display_width, display_height - y_start)        
        self.set_pen_color((242, 106, 48), palette)
        
        width = 256 if self.sun_cream() else display_width
        
        if self.sun_cream():
            with open('suncream.bmp', 'rb') as f:
                for y, row in enumerate(bitmap.read_bitmap(f)):
                    for x, color in enumerate(row):
                        self.set_pen_color(color, palette)
                        scale = 1
                        self.display.rectangle(width + x * scale, y_start + 32 + y * scale, scale, scale)
            
        self.display.set_font("bitmap8")
        
        if self.uv < 1:
            label = 'NO'
            color = (96, 96, 96)
        elif self.uv < 3:
            label = 'LOW'
            color = (113, 180, 102)
        elif self.uv < 6:
            label = 'MODERATE'
            color = (248, 231, 28)
        elif self.uv < 8:
            label = 'HIGH'
            color = (255, 149, 12)
        elif self.uv < 11:
            label = 'VERY HIGH'
            color = (215, 41, 33)
        else:
            label = 'EXTREME'
            color = (102, 0, 224)
            
        self.set_pen_color((255, 255, 255), palette)
        
        title = f"{label} UV"
        title_width = self.display.measure_text(title, 4)
        centre = int(width / 2)
        self.display.text(title, centre - int(title_width / 2), y_start + 32, scale=4)
        self.set_pen_color((0, 0, 0), palette)
            
        self.set_pen_color(color, palette)
        
        self.display.rectangle(centre - 64, y_start + 80, 128, 64)
        self.set_pen_color((0, 0, 0), palette)
        
        subtitle = f"{self.uv}"
        uv_width = self.display.measure_text(subtitle, scale=6)
        self.display.text(subtitle, centre - int(uv_width / 2), y_start + 90, scale=6)
            
        self.display.update()

    def set_pen_color(self, color, palette):
        if color in palette:
            pen_index = palette.index(color)
        else:
            palette.append(color)
            pen_index = len(palette) - 1
            self.display.update_pen(pen_index, color[0], color[1], color[2])
            
        self.display.set_pen(pen_index)