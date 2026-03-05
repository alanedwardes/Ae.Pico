import asyncio

class TouchCalibrationDisplay:
    """
    Guides the user through a 4-point touch sequence to calculate raw bounds and orientation.
    """
    def __init__(self, display_provider, touch_hardware):
        self.display = display_provider
        self.touch_hardware = touch_hardware
        
        self.state = 0
        if self.display:
            self.width, self.height = self.display.get_bounds()
        else:
            self.width, self.height = 320, 240
            
        self.margin = 20
        
        # 0: top-left, 1: bottom-right, 2: top-right, 3: bottom-left
        self.points_to_click = [
            (self.margin, self.margin, "Top Left"),
            (self.width - self.margin, self.height - self.margin, "Bottom Right"),
            (self.width - self.margin, self.margin, "Top Right"),
            (self.margin, self.height - self.margin, "Bottom Left")
        ]
        self.raw_clicks = []
        self.is_waiting_release = False
        
        self.bg_color = 0x000000
        self.fg_color = 0xFFFFFF
        self.cross_color = 0xFF0000

    CREATION_PRIORITY = 4

    def create(provider):
        display = provider.get('display')
        touch_hardware = provider.get('touch_hardware')
        touch = provider.get('touch')
        
        if not display or not touch_hardware:
            print("Warning: TouchCalibrationDisplay requires 'display' and 'touch_hardware'.")
            return None
            
        instance = TouchCalibrationDisplay(display, touch_hardware)
        if touch:
            touch.subscribe(instance.handle_touch)
            
        return instance

    def handle_touch(self, point):
        # Point is None when released
        if point is None:
            self.is_waiting_release = False
            return
            
        if self.is_waiting_release or self.state >= len(self.points_to_click):
            return
            
        if self.touch_hardware and hasattr(self.touch_hardware, 'last_raw'):
            raw = self.touch_hardware.last_raw
            if raw is not None:
                self.raw_clicks.append(raw)
                self.state += 1
                self.is_waiting_release = True
                self.draw_ui()

    def draw_crosshair(self, x, y):
        d = self.display
        if not d: return
        length = 10
        d.hline(x - length, y, length * 2 + 1, self.cross_color)
        d.vline(x, y - length, length * 2 + 1, self.cross_color)

    def draw_ui(self):
        d = self.display
        if not d: return
        
        d.fill(self.bg_color)
        
        if self.state < len(self.points_to_click):
            pt = self.points_to_click[self.state]
            d.text(f"Tap: {pt[2]}", 20, self.height // 2, self.fg_color)
            self.draw_crosshair(pt[0], pt[1])
        else:
            d.text("Calibration Complete!", 20, 20, self.fg_color)
            d.text("Check serial console.", 20, 40, self.fg_color)
            self.calculate_calibration()
            
        d.update()

    def calculate_calibration(self):
        if len(self.raw_clicks) < 4:
            return
            
        pt_tl, pt_br, pt_tr, pt_bl = self.raw_clicks
        
        # Determine orientation mapping
        x_diff_noswap = abs(pt_tr[0] - pt_tl[0]) + abs(pt_br[0] - pt_bl[0])
        x_diff_swap = abs(pt_tr[1] - pt_tl[1]) + abs(pt_br[1] - pt_bl[1])
        
        x_y_swap = x_diff_swap > x_diff_noswap
        
        if x_y_swap:
            # Display X correlates with raw Y
            disp_x_raw_min = (pt_tl[1] + pt_bl[1]) / 2  # Left points
            disp_x_raw_max = (pt_tr[1] + pt_br[1]) / 2  # Right points
            
            # Display Y correlates with raw X
            disp_y_raw_min = (pt_tl[0] + pt_tr[0]) / 2  # Top points
            disp_y_raw_max = (pt_bl[0] + pt_br[0]) / 2  # Bottom points
            
            x_inv = disp_x_raw_min > disp_x_raw_max
            y_inv = disp_y_raw_min > disp_y_raw_max
            
            # Extrapolate to actual screen edges
            span_x = max(1, self.width - 2 * self.margin)
            raw_per_px_x = (disp_x_raw_max - disp_x_raw_min) / span_x
            true_disp_x_raw_min = disp_x_raw_min - raw_per_px_x * self.margin
            true_disp_x_raw_max = disp_x_raw_max + raw_per_px_x * self.margin
            
            span_y = max(1, self.height - 2 * self.margin)
            raw_per_px_y = (disp_y_raw_max - disp_y_raw_min) / span_y
            true_disp_y_raw_min = disp_y_raw_min - raw_per_px_y * self.margin
            true_disp_y_raw_max = disp_y_raw_max + raw_per_px_y * self.margin
            
            x_raw_min = min(true_disp_y_raw_min, true_disp_y_raw_max)
            x_raw_max = max(true_disp_y_raw_min, true_disp_y_raw_max)
            y_raw_min = min(true_disp_x_raw_min, true_disp_x_raw_max)
            y_raw_max = max(true_disp_x_raw_min, true_disp_x_raw_max)
        else:
            # Display X correlates with raw X
            disp_x_raw_min = (pt_tl[0] + pt_bl[0]) / 2  # Left points
            disp_x_raw_max = (pt_tr[0] + pt_br[0]) / 2  # Right points
            
            # Display Y correlates with raw Y
            disp_y_raw_min = (pt_tl[1] + pt_tr[1]) / 2  # Top points
            disp_y_raw_max = (pt_bl[1] + pt_br[1]) / 2  # Bottom points
            
            x_inv = disp_x_raw_min > disp_x_raw_max
            y_inv = disp_y_raw_min > disp_y_raw_max
            
            # Extrapolate to actual screen edges
            span_x = max(1, self.width - 2 * self.margin)
            raw_per_px_x = (disp_x_raw_max - disp_x_raw_min) / span_x
            true_disp_x_raw_min = disp_x_raw_min - raw_per_px_x * self.margin
            true_disp_x_raw_max = disp_x_raw_max + raw_per_px_x * self.margin
            
            span_y = max(1, self.height - 2 * self.margin)
            raw_per_px_y = (disp_y_raw_max - disp_y_raw_min) / span_y
            true_disp_y_raw_min = disp_y_raw_min - raw_per_px_y * self.margin
            true_disp_y_raw_max = disp_y_raw_max + raw_per_px_y * self.margin
            
            x_raw_min = min(true_disp_x_raw_min, true_disp_x_raw_max)
            x_raw_max = max(true_disp_x_raw_min, true_disp_x_raw_max)
            y_raw_min = min(true_disp_y_raw_min, true_disp_y_raw_max)
            y_raw_max = max(true_disp_y_raw_min, true_disp_y_raw_max)

        print("\\n--- Touch Calibration Recommended Values ---")
        print("Update your configuration with:")
        print("touch = {")
        print(f"    'x_min': {int(x_raw_min)},")
        print(f"    'x_max': {int(x_raw_max)},")
        print(f"    'y_min': {int(y_raw_min)},")
        print(f"    'y_max': {int(y_raw_max)},")
        print(f"    'x_inv': {x_inv},")
        print(f"    'y_inv': {y_inv},")
        print(f"    'x_y_swap': {x_y_swap}")
        print("}")
        print("------------------------------------------\\n")
        
    async def start(self):
        # Allow system to boot, then draw first UI state
        await asyncio.sleep(1)
        self.draw_ui()
        while True:
            await asyncio.Event().wait()
