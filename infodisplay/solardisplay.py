import asyncio
import utime
import gc
import textbox

class SolarDisplay:
    def __init__(self, display, hass, entity_ids):
        self.display = display
        self.hass = hass
        self.entity_ids = entity_ids
        
        self.display_width, self.display_height = self.display.get_bounds()
        
        # Store entity values
        self.battery_soc = None
        self.current_grid = None
        self.current_solar = None
        self.current_load = None

        self.tsf = asyncio.ThreadSafeFlag()
    
    def format_power(self, value):
        try:
            v = float(value)
        except (ValueError, TypeError):
            return "?"
        sign = "-" if v < 0 else ""
        abs_v = abs(v)
        if abs_v >= 1000:
            return f"{sign}{abs_v / 1000:.2f}kW"
        else:
            return f"{sign}{abs_v:.0f}W"
    
    CREATION_PRIORITY = 1
    def create(provider):
        return SolarDisplay(provider['display'], provider['hassws.HassWs'], provider['config']['solar'])
    
    def entity_updated(self, entity_id, entity):
        # Update the appropriate entity value based on entity_id
        if entity_id == self.entity_ids.get('battery_soc'):
            self.battery_soc = entity.get('s')
        elif entity_id == self.entity_ids.get('current_grid'):
            self.current_grid = entity.get('s')
        elif entity_id == self.entity_ids.get('current_solar'):
            self.current_solar = entity.get('s')
        elif entity_id == self.entity_ids.get('current_load'):
            self.current_load = entity.get('s')
        
        self.tsf.set()
    
    async def start(self):
        # Subscribe to all solar entities
        entity_list = [self.entity_ids['battery_soc'], 
                    self.entity_ids['current_grid'], 
                    self.entity_ids['current_solar'],
                    self.entity_ids['current_load']]
        await self.hass.subscribe(entity_list, self.entity_updated)
        await asyncio.Event().wait()
    
    def should_activate(self):
        # Only show solar display if battery > 10% or solar generation > 1kW
        try:
            if self.battery_soc is not None:
                battery_value = float(self.battery_soc)
                if battery_value > 10:
                    return True
            
            if self.current_solar is not None:
                solar_value = float(self.current_solar)
                if solar_value > 1000:  # 1kW = 1000W
                    return True
        except (ValueError, TypeError):
            pass
        
        return False
    
    async def activate(self):
        while True:
            await self.update()
            await self.tsf.wait()
    
    async def update(self):
        await self.__update()
    
    async def __update(self):
        y_start = 70
        
        # Clear the display area below 70px
        self.display.rect(0, y_start, self.display_width, self.display_height - y_start, 0x0000, True)
        
        # Set up colors
        white = 0xFFFF
        green = 0x07E0
        yellow = 0xFFE0
        red = 0xF800
        blue = 0x04BF
        orange = 0xFD20
        
        # Layout: 2x2 grid
        item_width = self.display_width // 2
        item_height = (self.display_height - y_start) // 2
        
        # Top row
        y_top = y_start + 10
        y_bottom = y_start + item_height + 10
        
        # Left column
        x_left = 10
        x_right = item_width + 10
        
        # Battery SOC (top-left)
        if self.battery_soc is not None:
            try:
                soc_value = float(self.battery_soc)
                
                # Choose color based on SOC level
                if soc_value >= 50:
                    soc_color = green
                elif soc_value >= 20:
                    soc_color = yellow
                else:
                    soc_color = red
                
                soc_text = f"{soc_value:.0f}%"
                await textbox.draw_textbox(self.display, soc_text, x_left, y_top, item_width - 20, 40, color=soc_color, font='regular')
                
                await textbox.draw_textbox(self.display, "BAT", x_left, y_top + 35, item_width - 20, 25, color=white, font='small')
                
            except (ValueError, TypeError):
                await textbox.draw_textbox(self.display, "BAT: ?", x_left, y_top, item_width - 20, 30, color=white, font='regular')
        
        # Current Solar (top-right)
        if self.current_solar is not None:
            try:
                solar_value = float(self.current_solar)
                solar_text = self.format_power(solar_value)
                await textbox.draw_textbox(self.display, solar_text, x_right, y_top, item_width - 20, 40, color=orange, font='regular')
                
                await textbox.draw_textbox(self.display, "SOLAR", x_right, y_top + 35, item_width - 20, 25, color=white, font='small')
                
            except (ValueError, TypeError):
                await textbox.draw_textbox(self.display, "SOLAR: ?", x_right, y_top, item_width - 20, 30, color=white, font='regular')
        
        # Current Grid (bottom-left)
        if self.current_grid is not None:
            try:
                grid_value = float(self.current_grid)
                if grid_value > 0:
                    grid_color = green
                elif grid_value < 0:
                    grid_color = red
                else:
                    grid_color = white
                
                grid_text = self.format_power(grid_value)
                await textbox.draw_textbox(self.display, grid_text, x_left, y_bottom, item_width - 20, 40, color=grid_color, font='regular')
                
                if grid_value > 0:
                    await textbox.draw_textbox(self.display, "EXPORT", x_left, y_bottom + 35, item_width - 20, 25, color=white, font='small')
                else:
                    await textbox.draw_textbox(self.display, "IMPORT", x_left, y_bottom + 35, item_width - 20, 25, color=white, font='small')
                
            except (ValueError, TypeError):
                await textbox.draw_textbox(self.display, "GRID: ?", x_left, y_bottom, item_width - 20, 30, color=white, font='regular')
        
        # Current Load (bottom-right)
        if self.current_load is not None:
            try:
                load_value = float(self.current_load)
                load_text = self.format_power(load_value)
                await textbox.draw_textbox(self.display, load_text, x_right, y_bottom, item_width - 20, 40, color=blue, font='regular')
                
                await textbox.draw_textbox(self.display, "LOAD", x_right, y_bottom + 35, item_width - 20, 25, color=white, font='small')
                
            except (ValueError, TypeError):
                await textbox.draw_textbox(self.display, "LOAD: ?", x_right, y_bottom, item_width - 20, 30, color=white, font='regular')

        # Render only the solar display region (below the time/temperature displays)
        self.display.update((0, y_start, self.display_width, self.display_height - y_start))
