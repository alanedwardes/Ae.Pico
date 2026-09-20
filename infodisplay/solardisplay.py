import asyncio
import utime
import gc
import math
from array import array
import battery
import textbox

_WHITE = 0xFFFFFF
_GREEN = 0x00FC00
_RED = 0xF80000
_ORANGE = 0xFDA500
_BLUE = 0x0096FF

def _format_power(value):
    sign = "-" if value < 0 else ""
    abs_v = abs(value)
    if abs_v >= 1000:
        return f"{sign}{abs_v / 1000:.0f}kW"
    return f"{sign}{abs_v:.0f}W"

_BOLT_POINTS = (
    (0.62, 0.00), (0.22, 0.55), (0.42, 0.55),
    (0.28, 1.00), (0.78, 0.40), (0.55, 0.40),
)

def _draw_grid_icon(display, x, y, s, color):
    coords = array('h', [])
    for fx, fy in _BOLT_POINTS:
        coords.append(int(fx * s))
        coords.append(int(fy * s))
    display.poly(int(x), int(y), coords, color, True)

def _draw_solar_icon(display, x, y, s, color):
    cx = x + s // 2
    cy = y + s // 2
    r = s * 3 // 10
    ray_inner = s * 4 // 10
    ray_outer = s // 2
    display.ellipse(int(cx), int(cy), r, r, color, True)
    for i in range(8):
        angle = i * (2 * math.pi / 8)
        c = math.cos(angle)
        sn = math.sin(angle)
        x0 = cx + c * ray_inner
        y0 = cy + sn * ray_inner
        x1 = cx + c * ray_outer
        y1 = cy + sn * ray_outer
        display.line(int(x0), int(y0), int(x1), int(y1), color)

_HOUSE_POINTS = (
    (0.50, 0.00), (1.00, 0.45), (1.00, 1.00),
    (0.00, 1.00), (0.00, 0.45),
)

def _draw_load_icon(display, x, y, s, color):
    coords = array('h', [])
    for fx, fy in _HOUSE_POINTS:
        coords.append(int(fx * s))
        coords.append(int(fy * s))
    display.poly(int(x), int(y), coords, color, True)

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
            self.update()
            await self.tsf.wait()

    def update(self):
        self.__update()

    def _draw_metric(self, x, y, w, h, icon_fn, icon_color, label_text):
        margin = h // 8
        bounds = h - 2 * margin
        icon_s = (bounds * 3) // 4
        icon_x = x + margin + (bounds - icon_s) // 2
        icon_y = y + margin + (bounds - icon_s) // 2
        icon_fn(self.display, icon_x, icon_y, icon_s, icon_color)

        label_x = x + margin + bounds + margin
        label_w = x + w - label_x - margin
        if label_w > 0:
            font_scale = max(1, h // 90)
            textbox.draw_textbox(self.display, label_text, label_x, y, label_w, h,
                                  color=_WHITE, font='regular', scale=font_scale, align='left')

    def __update(self):
        y_start = self.start_y
        region_h = self.display_height - y_start

        try:
            battery_pct = float(self.battery_soc) if self.battery_soc is not None else None
        except (ValueError, TypeError):
            battery_pct = None

        try:
            grid_value = float(self.current_grid) if self.current_grid is not None else None
        except (ValueError, TypeError):
            grid_value = None

        try:
            solar_value = float(self.current_solar) if self.current_solar is not None else None
        except (ValueError, TypeError):
            solar_value = None

        try:
            load_value = float(self.current_load) if self.current_load is not None else None
        except (ValueError, TypeError):
            load_value = None

        self.display.rect(0, y_start, self.display_width, region_h, 0x000000, True)

        battery_col_w = self.display_width // 2
        battery_area_h = region_h // 2
        label_area_h = region_h - battery_area_h

        margin = battery_area_h // 8
        icon_w = battery_col_w - 2 * margin
        icon_h = min(battery_area_h - 2 * margin, icon_w // 2)
        if icon_w < 1:
            icon_w = 1
        if icon_h < 1:
            icon_h = 1
        icon_x = margin
        icon_y = y_start + margin + (battery_area_h - 2 * margin - icon_h) // 2
        battery.draw_battery(self.display, (icon_x, icon_y), (icon_w, icon_h), battery_pct, orientation='right')

        battery_label = f"{battery_pct:.0f}%" if battery_pct is not None else "-"
        textbox.draw_textbox(self.display, battery_label, 0, y_start + battery_area_h, battery_col_w, label_area_h,
                              color=_WHITE, font='regular', scale=1, align='center')

        rows_x0 = battery_col_w
        rows_w = self.display_width - rows_x0
        row_h = region_h // 3

        grid_color = _WHITE
        if grid_value is not None and grid_value > 0:
            grid_color = _GREEN
        elif grid_value is not None and grid_value < 0:
            grid_color = _RED
        grid_label = _format_power(grid_value) if grid_value is not None else "-"
        self._draw_metric(rows_x0, y_start, rows_w, row_h, _draw_grid_icon, grid_color, grid_label)

        solar_label = _format_power(solar_value) if solar_value is not None else "-"
        self._draw_metric(rows_x0, y_start + row_h, rows_w, row_h, _draw_solar_icon, _ORANGE, solar_label)

        load_label = _format_power(load_value) if load_value is not None else "-"
        self._draw_metric(rows_x0, y_start + 2 * row_h, rows_w, region_h - 2 * row_h, _draw_load_icon, _BLUE, load_label)
