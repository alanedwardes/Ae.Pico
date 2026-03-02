import framebuf

def blit_region(framebuffer, fb_width, fb_height, bytes_per_pixel, fh, header_bytes, src_row_bytes,
                sx, sy, sw, sh, dx, dy, buffer=None, src_format=None):
    if sw <= 0 or sh <= 0:
        return
    if dx >= fb_width or dy >= fb_height:
        return
    if dx + sw <= 0 or dy + sh <= 0:
        return

    start_row = max(0, -dy)
    end_row = min(sh, fb_height - dy)

    left_clip = max(0, -dx)
    right_clip = max(0, dx + sw - fb_width)
    copy_width = sw - left_clip - right_clip
    if copy_width <= 0:
        return

    src_x = sx + left_clip
    fb_x = dx + left_clip
    
    needed_bytes = copy_width * bytes_per_pixel
    if buffer:
        linebuf = memoryview(buffer)[:needed_bytes]
    else:
        linebuf = bytearray(needed_bytes)
        
    if src_format is None:
        src_format = framebuf.RGB565 if bytes_per_pixel == 2 else 6 # 6 is framebuf.GS8 / RGB332
        
    for row in range(start_row, end_row):
        fb_y = dy + row
        src_y = sy + row
        src_offset = header_bytes + src_y * src_row_bytes + src_x * bytes_per_pixel
        fh.seek(src_offset)
        fh.readinto(linebuf)
        src_fb = framebuf.FrameBuffer(linebuf, copy_width, 1, src_format)
        framebuffer.blit(src_fb, fb_x, fb_y)