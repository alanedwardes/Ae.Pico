import asyncio
import utime
import gc
import textbox
import table

_WHITE = 0xFFFFFF
_GREEN = 0x00FC00
_YELLOW = 0xFFFF00
_RED = 0xF80000
_BLUE = 0x0096FF
_ORANGE = 0xFDA500

def format_power(value):
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

def _battery_cell_data(battery_soc):
    if battery_soc is None:
        return "-", _WHITE, "BAT"
    try:
        soc_value = float(battery_soc)
    except (ValueError, TypeError):
        return "?", _WHITE, "BAT"
    if soc_value >= 50:
        color = _GREEN
    elif soc_value >= 20:
        color = _YELLOW
    else:
        color = _RED
    return f"{soc_value:.0f}%", color, "BAT"

def _solar_cell_data(current_solar):
    if current_solar is None:
        return "-", _WHITE, "SOLAR"
    try:
        solar_value = float(current_solar)
    except (ValueError, TypeError):
        return "?", _WHITE, "SOLAR"
    return format_power(solar_value), _ORANGE, "SOLAR"

def _grid_cell_data(current_grid):
    if current_grid is None:
        return "-", _WHITE, "GRID"
    try:
        grid_value = float(current_grid)
    except (ValueError, TypeError):
        return "?", _WHITE, "GRID"
    if grid_value > 0:
        color, label = _GREEN, "EXPORT"
    elif grid_value < 0:
        color, label = _RED, "IMPORT"
    else:
        color, label = _WHITE, "IMPORT"
    return format_power(grid_value), color, label

def _load_cell_data(current_load):
    if current_load is None:
        return "-", _WHITE, "LOAD"
    try:
        load_value = float(current_load)
    except (ValueError, TypeError):
        return "?", _WHITE, "LOAD"
    return format_power(load_value), _BLUE, "LOAD"

async def _draw_cell(display, x, y, w, h, text, color, font_name, valign):
    await textbox.draw_textbox(display, text, x, y, w, h, color=color, background=0x000000, font=font_name, valign=valign)

class SolarDisplay:
    def __init__(self, display, hass, entity_ids, start_y):
        self.display = display
        self.hass = hass
        self.entity_ids = entity_ids
        self.start_y = start_y

        self.display_width, self.display_height = self.display.get_bounds()

        # Store entity values
        self.battery_soc = None
        self.current_grid = None
        self.current_solar = None
        self.current_load = None

        self.tsf = asyncio.ThreadSafeFlag()

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['solar']
        y_separator = provider['config']['display'].get('y_separator', 70)
        return SolarDisplay(provider['display'], provider['hassws.HassWs'], config, y_separator)

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
        y_start = self.start_y

        grid = table.grid_rects(0, y_start, self.display_width, self.display_height - y_start, 4, 2)
        value_row_top, label_row_top, value_row_bottom, label_row_bottom = grid[0:2], grid[2:4], grid[4:6], grid[6:8]

        slots = [
            (_battery_cell_data(self.battery_soc), value_row_top[0], label_row_top[0]),
            (_solar_cell_data(self.current_solar), value_row_top[1], label_row_top[1]),
            (_grid_cell_data(self.current_grid), value_row_bottom[0], label_row_bottom[0]),
            (_load_cell_data(self.current_load), value_row_bottom[1], label_row_bottom[1]),
        ]

        cells = []
        for (value_text, value_color, label_text), value_rect, label_rect in slots:
            vx, vy, vw, vh = value_rect
            lx, ly, lw, lh = label_rect
            cells.append((vx, vy, vw, vh, _draw_cell, (value_text, value_color, 'regular', 'bottom')))
            cells.append((lx, ly, lw, lh, _draw_cell, (label_text, _WHITE, 'small', 'top')))

        await table.draw_cells(self.display, cells, shuffle=True)
