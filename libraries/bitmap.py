def read_bitmap(data):
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
    # Manually interpret sign (BMP height is 4 bytes, two's complement)
    if raw_height & 0x80000000:
        height = -((~raw_height + 1) & 0xFFFFFFFF)
    else:
        height = raw_height
    planes = int.from_bytes(dib_header[12:14], 'little')
    bpp = int.from_bytes(dib_header[14:16], 'little')
    compression = int.from_bytes(dib_header[16:20], 'little')

    if planes != 1 or bpp != 24 or compression != 0:
        raise ValueError("Only uncompressed 24-bit BMP files are supported")

    # Move to pixel data
    data.seek(pixel_offset)

    # Each row is padded to a multiple of 4 bytes
    row_padded = (width * 3 + 3) & ~3

    for _ in range(abs(height)):
        row_data = data.read(row_padded)
        row = []
        for x in range(width):
            i = x * 3
            b, g, r = row_data[i], row_data[i+1], row_data[i+2]
            row.append((r, g, b))
        yield row
