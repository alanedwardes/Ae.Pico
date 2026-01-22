import pygame
import asyncio
import sys
import random
from array import array
from drawing import Drawing

class PygameDisplay:
    def __init__(self, display_width, display_height, scale=1, debug_regions=False):
        pygame.init()
        self.screen = pygame.display.set_mode((display_width, display_height), pygame.HWSURFACE | pygame.DOUBLEBUF, depth=32)
        self._display_width = display_width
        self._display_height = display_height
        self._scale = scale
        self._debug_regions = debug_regions
        # Persistent RGBA buffer and surface at display resolution (avoid per-frame allocations)
        self._rgba = bytearray(display_width * display_height * 4)
        self._rgba_view32 = memoryview(self._rgba).cast('I')
        self._surf = pygame.image.frombuffer(self._rgba, (display_width, display_height), 'RGBA')
        # Precompute 16-bit RGB565 -> 32-bit RGBA8888 lookup table
        lut = array('I', [0]) * 65536
        for val in range(65536):
            r5 = (val >> 11) & 0x1F
            g6 = (val >> 5) & 0x3F
            b5 = val & 0x1F
            r = (r5 << 3) | (r5 >> 2)
            g = (g6 << 2) | (g6 >> 4)
            b = (b5 << 3) | (b5 >> 2)
            lut[val] = (255 << 24) | (b << 16) | (g << 8) | r  # little-endian RGBA bytes
        self._lut565_rgba = lut

    def create(provider):
        config = provider['config']['display']

        # Get configurable dimensions and scale
        display_width = config['width']
        display_height = config['height']
        scale = config.get('scale', 1)

        # Framebuffer dimensions are display dimensions divided by scale
        fb_width = display_width // scale
        fb_height = display_height // scale

        driver = PygameDisplay(display_width, display_height, scale=scale, debug_regions=False)
        drawing = Drawing(fb_width, fb_height)
        drawing.set_driver(driver)

        provider['display'] = drawing
        return driver
              
    async def start(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    sys.exit()
            await asyncio.sleep(0.1)

    def set_backlight(self, brightness):
        pass  # No backlight on pygame

    def _rgb565_to_rgba(self, color):
        """Convert scalar RGB565 to RGBA tuple."""
        # Using the LUT is efficient for bulk, but for single pixels we can compute
        r5 = (color >> 11) & 0x1F
        g6 = (color >> 5) & 0x3F
        b5 = color & 0x1F
        r = (r5 << 3) | (r5 >> 2)
        g = (g6 << 2) | (g6 >> 4)
        b = (b5 << 3) | (b5 >> 2)
        return (r, g, b, 255)

    def fill_rect(self, x, y, w, h, color):
        if x < 0: w += x; x = 0
        if y < 0: h += y; y = 0
        if w <= 0 or h <= 0: return
        
        # Scale coords
        sx = x * self._scale
        sy = y * self._scale
        sw = w * self._scale
        sh = h * self._scale
        
        rgba = self._rgb565_to_rgba(color)
        self.screen.fill(rgba, (sx, sy, sw, sh))
        
        if self._debug_regions:
             pygame.draw.rect(self.screen, (255, 0, 0), (sx, sy, sw, sh), 1)

        pygame.display.update((sx, sy, sw, sh))

    def fill(self, color):
        rgba = self._rgb565_to_rgba(color)
        self.screen.fill(rgba)
        pygame.display.flip()

    def pixel(self, x, y, color):
        if x < 0 or x >= self._display_width or y < 0 or y >= self._display_height:
            return
        
        sx = x * self._scale
        sy = y * self._scale
        rgba = self._rgb565_to_rgba(color)
        
        if self._scale == 1:
            self.screen.set_at((sx, sy), rgba)
            pygame.display.update((sx, sy, 1, 1))
        else:
            self.screen.fill(rgba, (sx, sy, self._scale, self._scale))
            pygame.display.update((sx, sy, self._scale, self._scale))

    def line(self, x1, y1, x2, y2, color):
        rgba = self._rgb565_to_rgba(color)
        # Pygame line uses full resolution coords
        p1 = (x1 * self._scale, y1 * self._scale)
        p2 = (x2 * self._scale, y2 * self._scale)
        # Note: Pygame line width might not match Bresenham exactly with scaling
        # But good enough for emulation
        pygame.draw.line(self.screen, rgba, p1, p2, self._scale)
        # Update full screen for simplicity on lines (calculating dirty rect is tedious)
        pygame.display.flip() 

    def hline(self, x, y, w, color):
        self.fill_rect(x, y, w, 1, color)

    def vline(self, x, y, h, color):
        self.fill_rect(x, y, 1, h, color)

    def ellipse(self, x, y, xr, yr, color, fill=False, m=15):
        rgba = self._rgb565_to_rgba(color)
        sx = x * self._scale
        sy = y * self._scale
        rx = xr * self._scale
        ry = yr * self._scale
        
        # Pygame draw.ellipse takes a bounding rect
        # Center is (sx, sy), radius rx, ry
        # Bounding rect: left = sx - rx, top = sy - ry, w = 2*rx, h = 2*ry
        # Note: framebuf ellipse mask is hard to replicate exactly with simple pygame primitives without arc
        # If mask is 15 (full), use ellipse.
        # Otherwise, we might need arcs.
        # Simplification: Support full ellipse for now.
        
        rect = (sx - rx, sy - ry, rx * 2, ry * 2)
        width = 0 if fill else self._scale
        pygame.draw.ellipse(self.screen, rgba, rect, width)
        pygame.display.update(rect)

    def poly(self, x, y, coords, color, fill=False):
        rgba = self._rgb565_to_rgba(color)
        scale = self._scale
        
        # Offset and scale points
        points = []
        for i in range(0, len(coords), 2):
            px = (x + coords[i]) * scale
            py = (y + coords[i+1]) * scale
            points.append((px, py))
            
        if len(points) < 2: return
        
        width = 0 if fill else scale
        pygame.draw.polygon(self.screen, rgba, points, width)
        pygame.display.flip()

    def text(self, s, x, y, color=0xFFFF):
        # Basic text support using pygame font for debug
        rgba = self._rgb565_to_rgba(color)
        font = pygame.font.SysFont('Arial', 12 * self._scale)
        surf = font.render(s, True, rgba)
        sx = x * self._scale
        sy = y * self._scale
        self.screen.blit(surf, (sx, sy))
        pygame.display.update((sx, sy, surf.get_width(), surf.get_height()))

    def rect(self, x, y, w, h, color, fill=False):
        if fill:
            self.fill_rect(x, y, w, h, color)
        else:
            rgba = self._rgb565_to_rgba(color)
            sx = x * self._scale
            sy = y * self._scale
            sw = w * self._scale
            sh = h * self._scale
            pygame.draw.rect(self.screen, rgba, (sx, sy, sw, sh), self._scale)
            pygame.display.update((sx, sy, sw, sh))

    def blit(self, source, x, y, key=0, palette=None):
        try:
            source_buf, w, h, fmt = source
        except:
            return

        # Simple clipping at top-left
        if x < 0:
            # We don't support clipping natively here easily in slow emulation
            # Just panic or return? return for now.
            return 
            
        sx = x * self._scale
        sy = y * self._scale
        
        # We need to construct a surface from source
        # If palette is provided (GS8), we need to convert to RGB888
        if palette:
             pal_bytes = palette[0]
             # Parse palette into simple lookup list of (r,g,b)
             cols = []
             for i in range(0, len(pal_bytes), 2):
                 # Palette is native LE bytes (low, high) in bmfont usually?
                 # No, standard is (val & 0xFF, val >> 8). So Little Endian.
                 lo = pal_bytes[i]
                 hi = pal_bytes[i+1]
                 val = (hi << 8) | lo
                 cols.append(self._rgb565_to_rgba(val))
             
             # Convert source buffer using palette
             # Ideally use pygame.image.fromstring with 'P' format and set_palette?
             # But 'P' is 8-bit. Yes!
             # source_buf might be memoryview.
             buf_bytes = bytes(source_buf)
             surf = pygame.image.fromstring(buf_bytes, (w, h), 'P')
             
             # Pygame palette expects list of (r,g,b)
             # Should be 256 entries.
             pg_pal = [c[:3] for c in cols] # strip alpha
             while len(pg_pal) < 256:
                 pg_pal.append((0,0,0))
             surf.set_palette(pg_pal)
             surf.set_colorkey(key) # Handle key if needed
             
        else:
             # Assume RGB565. Pygame doesn't support RGB565 loading easily?
             # We might need to convert to RGB888.
             # This is slow emulation, so we can iterate.
             # Or construct 32-bit buffer via LUT.
             
             # Reuse our LUT
             src16 = memoryview(source_buf).cast('H') if isinstance(source_buf, (bytearray, memoryview)) else array('H', source_buf)
             # But if source_buf is bytes, cast might need read-write?
             # Let's assume bytes.
             if isinstance(source_buf, (bytes, bytearray, memoryview)):
                  # copy to array or use struct unpack loop?
                  # easiest:
                  import struct
                  iter_16 = struct.iter_unpack('<H', source_buf)
                  pixels_rgba = bytearray(w * h * 4)
                  # This is very slow for large blits but emulates correctly
                  mv = memoryview(pixels_rgba).cast('I')
                  lut = self._lut565_rgba
                  for i, val in enumerate(iter_16):
                      mv[i] = lut[val[0]]
                      
                  surf = pygame.image.frombuffer(pixels_rgba, (w, h), 'RGBA')
             else:
                  return

        # Scale if needed
        if self._scale != 1:
            surf = pygame.transform.scale(surf, (w * self._scale, h * self._scale))
            
        self.screen.blit(surf, (sx, sy))
        pygame.display.update((sx, sy, w * self._scale, h * self._scale))

    async def load_stream(self, reader, x, y, w, h):
         # Read stream into buffer and blit
         # For emulation, we buffer it all or read chunks.
         # reader is CPython asyncio.StreamReader -> uses read(n)
         
         sz = w * h * 2
         buf = bytearray(sz)
         view = memoryview(buf)
         remaining = sz
         
         while remaining > 0:
             # CPython reader.read
             chunk = await reader.read(remaining)
             if not chunk:
                 break
             n = len(chunk)
             view[sz-remaining:sz-remaining+n] = chunk
             remaining -= n
             
         # Now blit the buffer
         # It is RGB565. We can reuse blit logic.
         self.blit((buf, w, h, 1), x, y) # 1=RGB565? st7789 assumes tuple
         # Wait, my blit impl in pygamedisplay uses `palette=None` to distinguish.
         # So format 1 is ignored but we pass it for tuple unpacking.


