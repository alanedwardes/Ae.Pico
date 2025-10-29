from machine import SPI, Pin
from st7789 import ST7789, LANDSCAPE
from font8 import Font8
from array import array

#print('got here')
#from hershey import HersheyFronts
#print('hershey')

WIDTH = 320
HEIGHT = 240

class ST7789Display:
    def create(provider):
        config = provider['config'].get('display', {})
        
        spi = SPI(0, baudrate=40000000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(19))
        dc = Pin(16, Pin.OUT, value=0)
        cs = Pin(17, Pin.OUT, value=1)
        rst = Pin(12, Pin.OUT, value=1)
        backlight = Pin(20, Pin.OUT, value=1)
        
        #serif = HersheyFonts.HersheyFonts()
        #serif.load_default_font()
        
        display = ST7789(
            spi,
            cs=cs,
            dc=dc,
            rst=rst,
            height=HEIGHT,
            width=WIDTH,
            disp_mode=LANDSCAPE,
            display=(0, 0, 1, 0, True),
        )
        
        def get_bounds():
            return (display.width, display.height)
        display.get_bounds = get_bounds
        
        def set_pen(pen):
            display.pen = pen
        display.set_pen = set_pen
        
        def create_pen(r, g, b):
            return ST7789.rgb(r, g, b)
        display.create_pen = create_pen
        
        def set_font(font):
            display.font = font
        display.set_font = set_font
        
        def __get_serif_lines(self, text, scale):
            return [((x1 * scale, y1 * scale), (x2 * scale, y2 * scale)) for (x1, y1), (x2, y2) in serif.lines_for_text(text)]
        
        def set_clip(*args):
            pass
        display.set_clip = set_clip
        
        def remove_clip(*args):
            pass
        display.remove_clip = remove_clip
        
        def rectangle(x, y, w, h):
            display.rect(x, y, w, h, display.pen, True)
        display.rectangle = rectangle
            
        def circle(x, y, radius):
            display.ellipse(x, y, radius, radius, display.pen, True)
        display.circle = circle
        
        def polygon(points):
            display.poly(0, 0, array('h', [point for sublist in points for point in sublist]), display.pen, True)
        display.polygon = polygon
        
        def set_backlight(brightness):
            pass
        display.set_backlight = set_backlight
        
        def set_thickness(thickness):
            display.thickness = thickness
        display.set_thickness = set_thickness
        
        def measure_text(text, scale = 1, spacing = 1, fixed_width = False):
            if display.font == 'bitmap8':
                return Font8.measure_text(text, scale, spacing)
            elif display.font == 'sans':
                return Font8.measure_text(text, scale * 3, spacing)
                lines = __get_serif_lines(text, scale)
                min_x = min(x1 for (x1, y1), (x2, y2) in lines)
                max_x = max([x2 for (x1, y1), (x2, y2) in lines])
                return max_x - min_x
            else:
                raise NotImplementedError(f"Font '{display.font}' not supported for measure_text")
        display.measure_text = measure_text
        
        def text(text, x, y, scale = 1):
            if display.font == 'bitmap8':
                Font8.draw_text(display, text, x, y, display.pen, 1, scale)
            elif display.font == 'sans':
                Font8.draw_text(display, text, x, y, display.pen, 1, scale * 3)
                return
                lines = __get_serif_lines(text, scale)
                min_x = min(x1 for (x1, y1), (x2, y2) in lines)

                for (x1, y1), (x2, y2) in lines:
                    display.line(x + x1 - min_x, y + y1, x + x2 - min_x, y + y2, display.pen)
            else:
                raise NotImplementedError(f"Font '{display.font}' not supported for text")
        display.text = text

        provider['display'] = display
              
    async def start(self):
        raise NotImplementedError

