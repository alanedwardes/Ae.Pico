def blit_region_scaled(framebuffer, fb_width, fb_height, bytes_per_pixel, fh, header_bytes, src_row_bytes,
                       sx, sy, sw, sh, dx, dy, scale_up=1, scale_down=1):
    # Fast path: 1:1 copy, row-at-a-time
    if scale_up == 1 and scale_down == 1:
        _blit_fast(framebuffer, fb_width, fb_height, bytes_per_pixel, fh, header_bytes, src_row_bytes,
                   sx, sy, sw, sh, dx, dy)
        return

    # General path: integer up/down-scale without buffering
    # Downscale by N: keep every Nth src pixel/row
    # Upscale by M: replicate each kept src pixel/row M times
    if scale_up < 1 or scale_down < 1:
        return

    fb_row_bytes = fb_width * bytes_per_pixel

    # Clip vertically in destination space. Compute resulting dst bounds first.
    dst_h = (sh // scale_down) * scale_up
    if dst_h <= 0:
        return
    start_dst_row = 0
    if dy < 0:
        start_dst_row = -dy
    end_dst_row = dst_h
    max_y = fb_height - dy
    if end_dst_row > max_y:
        end_dst_row = max_y

    # Horizontal pre-computations
    dst_w = (sw // scale_down) * scale_up
    if dst_w <= 0:
        return

    # Iterate destination rows; map to source row
    for dst_row in range(start_dst_row, end_dst_row):
        fb_y = dy + dst_row
        if fb_y < 0 or fb_y >= fb_height:
            continue
        # Map this destination row to a kept source row index
        src_row_idx = (dst_row // scale_up) * scale_down
        if src_row_idx >= sh:
            break
        src_y = sy + src_row_idx
        # For each destination row, draw horizontal pixels
        # Compute starting framebuffer offset for this row with clipping on X
        # Left clip
        start_dst_x = 0
        if dx < 0:
            start_dst_x = -dx
        end_dst_x = dst_w
        max_x = fb_width - dx
        if end_dst_x > max_x:
            end_dst_x = max_x
        if start_dst_x >= end_dst_x:
            continue
        fb_offset = fb_y * fb_row_bytes + (dx + start_dst_x) * bytes_per_pixel

        # We'll iterate destination columns, mapping back to kept source columns
        # Use a tiny pixel buffer of size bpp
        px = bytearray(bytes_per_pixel)
        mv_fb = memoryview(framebuffer)

        # Prime file position to the first kept source pixel for this dst row
        first_src_col_idx = (start_dst_x // scale_up) * scale_down
        src_x = sx + first_src_col_idx
        file_pos = header_bytes + src_y * src_row_bytes + src_x * bytes_per_pixel
        fh.seek(file_pos)

        # Iterate kept source pixels and expand to destination, respecting start/end_dst_x
        dst_x = start_dst_x
        src_col_idx = first_src_col_idx
        while dst_x < end_dst_x and src_col_idx < sw:
            # Read one source pixel
            mv_px = memoryview(px)
            fh.readinto(mv_px)

            # Expand horizontally for upscaling
            reps = min(scale_up, end_dst_x - dst_x)
            for _ in range(reps):
                mv_fb[fb_offset:fb_offset + bytes_per_pixel] = mv_px
                fb_offset += bytes_per_pixel
            dst_x += reps

            # Advance to next kept source pixel: skip (scale_down-1) pixels in the file
            skip = (scale_down * bytes_per_pixel) - bytes_per_pixel
            if skip:
                fh.seek(skip, 1)
            src_col_idx += scale_down


def _blit_fast(framebuffer, fb_width, fb_height, bytes_per_pixel, fh, header_bytes, src_row_bytes,
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


