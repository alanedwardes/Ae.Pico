def blit_region(framebuffer, fb_width, fb_height, bytes_per_pixel, fh, header_bytes, src_row_bytes,
               sx, sy, sw, sh, dx, dy):
    if sw <= 0 or sh <= 0:
        return
    if dx >= fb_width or dy >= fb_height:
        return
    if dx + sw <= 0 or dy + sh <= 0:
        return

    fb_row_bytes = fb_width * bytes_per_pixel

    start_row = 0
    if dy < 0:
        start_row = -dy
    end_row = sh
    max_y = fb_height - dy
    if end_row > max_y:
        end_row = max_y

    left_clip = 0
    if dx < 0:
        left_clip = -dx
    right_clip = 0
    over_right = dx + sw - fb_width
    if over_right > 0:
        right_clip = over_right
    copy_width = sw - left_clip - right_clip
    if copy_width <= 0:
        return

    for row in range(start_row, end_row):
        fb_y = dy + row
        if fb_y < 0 or fb_y >= fb_height:
            continue
        src_x = sx + left_clip
        src_y = sy + row
        fb_x = dx + left_clip
        src_offset = header_bytes + src_y * src_row_bytes + src_x * bytes_per_pixel
        fb_offset = fb_y * fb_row_bytes + fb_x * bytes_per_pixel
        mv = memoryview(framebuffer)[fb_offset : fb_offset + copy_width * bytes_per_pixel]
        fh.seek(src_offset)
        fh.readinto(mv)
