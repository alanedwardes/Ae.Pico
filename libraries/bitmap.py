def read_bitmap(data, start_row=0):
    return read_pixels(read_header(data), data, start_row)

def read_header(data):
    # Read BMP Header
    header = data.read(14)
    if header[0:2] != b'BM':
        raise ValueError("Not a BMP file")
    file_size = int.from_bytes(header[2:6], 'little')
    pixel_offset = int.from_bytes(header[10:14], 'little')

    # Read DIB Header
    dib_header = data.read(40)
    width = int.from_bytes(dib_header[4:8], 'little')
    raw_height = int.from_bytes(dib_header[8:12], 'little')
    if raw_height & 0x80000000:
        height = -((~raw_height + 1) & 0xFFFFFFFF)
    else:
        height = raw_height
    planes = int.from_bytes(dib_header[12:14], 'little')
    bpp = int.from_bytes(dib_header[14:16], 'little')
    compression = int.from_bytes(dib_header[16:20], 'little')

    # Read palette if present
    palette = []
    if bpp <= 8:
        num_colors = int.from_bytes(dib_header[32:36], 'little')
        if num_colors == 0:
            num_colors = 1 << bpp
        for _ in range(num_colors):
            entry = data.read(4)
            b, g, r, _ = entry
            palette.append((r, g, b))
    elif bpp == 16:
        # 16-bit BMPs are usually 5-5-5 or 5-6-5, but we assume 5-5-5 here
        pass  # No palette

    return {
        "file_size": file_size,
        "pixel_offset": pixel_offset,
        "width": width,
        "height": height,
        "planes": planes,
        "bpp": bpp,
        "compression": compression,
        "palette": palette
    }

def read_pixels(data, header, start_row=0):
    file_size = header["file_size"]
    pixel_offset = header["pixel_offset"]
    width = header["width"]
    height = header["height"]
    planes = header["planes"]
    bpp = header["bpp"]
    compression = header["compression"]
    palette = header["palette"]

    if planes != 1 or compression != 0:
        raise ValueError("Only uncompressed BMP files with 1 plane are supported")

    # Move to pixel data
    data.seek(pixel_offset)

    # Each row is padded to a multiple of 4 bytes
    def row_size(bits, width):
        return ((width * bits + 31) // 32) * 4

    row_padded = row_size(bpp, width)
    data.seek(row_padded * start_row, 1)

    for _ in range(abs(height) - start_row):
        row_data = data.read(row_padded)
        row = []
        if bpp == 1:
            for x in range(width):
                byte = row_data[x // 8]
                bit = 7 - (x % 8)
                idx = (byte >> bit) & 1
                row.append(palette[idx])
        elif bpp == 2:
            for x in range(width):
                byte = row_data[x // 4]
                shift = 6 - 2 * (x % 4)
                idx = (byte >> shift) & 0b11
                row.append(palette[idx])
        elif bpp == 4:
            for x in range(width):
                byte = row_data[x // 2]
                if x % 2 == 0:
                    idx = (byte >> 4) & 0xF
                else:
                    idx = byte & 0xF
                row.append(palette[idx])
        elif bpp == 8:
            for x in range(width):
                idx = row_data[x]
                row.append(palette[idx])
        elif bpp == 16:
            for x in range(width):
                i = x * 2
                pix = int.from_bytes(row_data[i:i+2], 'little')
                # Assume 5-5-5 (RGB555)
                r = ((pix >> 10) & 0x1F) << 3
                g = ((pix >> 5) & 0x1F) << 3
                b = (pix & 0x1F) << 3
                row.append((r, g, b))
        elif bpp == 24:
            for x in range(width):
                i = x * 3
                b, g, r = row_data[i], row_data[i+1], row_data[i+2]
                row.append((r, g, b))
        else:
            raise ValueError(f"Unsupported bpp: {bpp}")
        yield row
