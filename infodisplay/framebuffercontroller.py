import asyncio

class FramebufferController:
    def __init__(self, display):
        self.display = display

    CREATION_PRIORITY = 1
    def create(provider):
        display = provider.get('display')
        management = provider.get('management.ManagementServer')
        if display is None or management is None:
            return
        
        controller = FramebufferController(display)
        management.controllers.append(controller)

    async def start(self):
        # Component exists only to register the controller
        await asyncio.Event().wait()

    # Controller interface
    def route(self, method, path):
        return method == b'GET' and path == b'/framebuffer'

    def widget(self):
        return b'<p><img src="/framebuffer" alt="Framebuffer"/></p>'

    async def serve(self, method, path, headers, reader, writer):
        # Determine framebuffer geometry
        width, height = self.display.get_bounds()
        bytes_per_pixel = self.display.bytes_per_pixel

        row_bytes = width * bytes_per_pixel
        pad = (4 - (row_bytes & 3)) & 3
        image_size = (row_bytes + pad) * height
        file_header_size = 14
        dib_header_size = 40
        
        if bytes_per_pixel == 1:
            palette_size = 256 * 4
            off_bits = file_header_size + dib_header_size + palette_size
        else:
            mask_size = 12  # R/G/B masks (no alpha)
            off_bits = file_header_size + dib_header_size + mask_size
            
        file_size = off_bits + image_size

        # Build headers (little-endian)
        # BITMAPFILEHEADER
        bf = bytearray(14)
        bf[0] = 0x42  # 'B'
        bf[1] = 0x4D  # 'M'
        bs = file_size
        bf[2:6] = bytes((bs & 0xFF, (bs >> 8) & 0xFF, (bs >> 16) & 0xFF, (bs >> 24) & 0xFF))
        # bf[6:10] are reserved zero by default
        ob = off_bits
        bf[10:14] = bytes((ob & 0xFF, (ob >> 8) & 0xFF, (ob >> 16) & 0xFF, (ob >> 24) & 0xFF))

        # BITMAPINFOHEADER
        bi = bytearray(40)
        # biSize
        bi[0:4] = b'\x28\x00\x00\x00'  # 40
        # biWidth
        w = width & 0xFFFFFFFF
        bi[4:8] = bytes((w & 0xFF, (w >> 8) & 0xFF, (w >> 16) & 0xFF, (w >> 24) & 0xFF))
        # biHeight (negative for top-down so we can stream in natural order)
        h = (-height) & 0xFFFFFFFF
        bi[8:12] = bytes((h & 0xFF, (h >> 8) & 0xFF, (h >> 16) & 0xFF, (h >> 24) & 0xFF))
        # biPlanes
        bi[12:14] = b'\x01\x00'
        
        if bytes_per_pixel == 1:
            # biBitCount
            bi[14:16] = b'\x08\x00'  # 8 bpp
            # biCompression = BI_RGB (0)
            bi[16:20] = b'\x00\x00\x00\x00'
            # biClrUsed
            bi[32:36] = b'\x00\x01\x00\x00' # 256 colors
        else:
            # biBitCount
            bi[14:16] = b'\x10\x00'  # 16 bpp
            # biCompression = BI_BITFIELDS (3)
            bi[16:20] = b'\x03\x00\x00\x00'
            
        # biSizeImage
        isize = image_size
        bi[20:24] = bytes((isize & 0xFF, (isize >> 8) & 0xFF, (isize >> 16) & 0xFF, (isize >> 24) & 0xFF))
        # biXPelsPerMeter / biYPelsPerMeter (~72 DPI)
        bi[24:28] = b'\x13\x0B\x00\x00'
        bi[28:32] = b'\x13\x0B\x00\x00'
        # biClrUsed / biClrImportant = 0

        # HTTP response headers
        writer.write(b'HTTP/1.0 200 OK\r\n')
        writer.write(b'Content-Type: image/bmp\r\n')
        writer.write(b'Cache-Control: no-cache\r\n')
        writer.write(b'Connection: close\r\n')
        writer.write(b'Content-Length: ' + str(file_size).encode('ascii') + b'\r\n')
        writer.write(b'\r\n')

        # Write BMP headers
        writer.write(bf)
        writer.write(bi)
        
        if bytes_per_pixel == 1:
            # Build 256-color palette for RGB332
            palette = bytearray(1024)
            for i in range(256):
                r = (i >> 5) & 0x07
                g = (i >> 2) & 0x07
                b = i & 0x03
                
                # Expand to 8-bit
                r8 = (r * 255) // 7
                g8 = (g * 255) // 7
                b8 = (b * 255) // 3
                
                # BMP palette is B, G, R, 0
                idx = i * 4
                palette[idx] = b8
                palette[idx+1] = g8
                palette[idx+2] = r8
                palette[idx+3] = 0
            writer.write(palette)
        else:
            # Color masks: R=0xF800, G=0x07E0, B=0x001F (little-endian DWORDs)
            writer.write(b'\x00\xf8\x00\x00\xe0\x07\x00\x00\x1f\x00\x00\x00')
            
        await writer.drain()

        # Stream pixel rows top-down with row padding
        mv = self.display.framebuffer
        pad_bytes = b'\x00' * pad if pad else b''
        base = 0
        for _ in range(height):
            row_end = base + row_bytes
            writer.write(mv[base:row_end])
            if pad:
                writer.write(pad_bytes)
            base = row_end
            # Drain intermittently to avoid large buffers
            await writer.drain()

        await writer.drain()
        writer.close()
        await writer.wait_closed()

