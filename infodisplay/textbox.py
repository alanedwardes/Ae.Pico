import math
import random
from array import array

from bmfont import BMFont, draw_text, measure_text, measure_extend
from font8 import Font8

_BM_FONT_CACHE = {}
_LAYOUT_OUT = array('i', [0, 0, 0, 0])

def _get_bmfont(font_name):
    if font_name not in _BM_FONT_CACHE:
        font_path = f"fonts/{font_name}.fnt"
        # Keep page files open for fast rendering, but ensure they're properly managed
        # Note: Files will remain open for the life of the program since fonts are cached
        page_file = open(f"fonts/{font_name}_0.bin", "rb")
        _BM_FONT_CACHE[font_name] = (BMFont.load(font_path), [page_file])
    return _BM_FONT_CACHE[font_name]

def get_font(font_name):
    """Return the cached (BMFont, page_files) pair for a font name."""
    return _get_bmfont(font_name)

def clear_font_cache():
    """Clear font cache and close all open font files"""
    global _BM_FONT_CACHE
    for font_name, (font_obj, page_files) in _BM_FONT_CACHE.items():
        for page_file in page_files:
            try:
                page_file.close()
            except:
                pass
    _BM_FONT_CACHE.clear()

def _measure_bmfont(font_obj, text, scale):
    w, h, _min_x, _min_y = measure_text(font_obj, text.encode())
    return w * scale, h * scale

def _word_wrap_bmfont(font_obj, text, max_width_pixels, scale):
    words = text.split()
    wrapped_lines = []
    current_words = []
    cx, prev_id, min_left, max_right = 0, None, None, None

    sp_off = font_obj.chars.get(0x20)
    if sp_off is None:
        sp_xadvance = 0
        sp_xoffset = 0
        sp_width = 0
        sp_code = None
    else:
        gd = font_obj._glyph_data
        sp_width = gd[sp_off+4] | (gd[sp_off+5] << 8)
        sp_xoffset = gd[sp_off+8] | (gd[sp_off+9] << 8)
        if sp_xoffset > 32767:
            sp_xoffset -= 65536
        sp_xadvance = gd[sp_off+12] | (gd[sp_off+13] << 8)
        if sp_xadvance > 32767:
            sp_xadvance -= 65536
        sp_code = 0x20

    for i, word in enumerate(words):
        line_started_empty = not current_words
        if line_started_empty:
            t_cx, t_prev, t_min, t_max = measure_extend(font_obj, word.encode(), 0, None, None, None)
        else:
            sl = cx + sp_xoffset
            if min_left is None or sl < min_left:
                min_left = sl
            sr = sl + sp_width
            if max_right is None or sr > max_right:
                max_right = sr
            t_cx, t_prev, t_min, t_max = measure_extend(
                font_obj, word.encode(), cx + sp_xadvance, sp_code, min_left, max_right)
        line_width_pixels = 0 if t_min is None else (t_max - t_min) * scale
        if line_width_pixels <= max_width_pixels:
            current_words.append(word)
            cx, prev_id, min_left, max_right = t_cx, t_prev, t_min, t_max
        else:
            wrapped_lines.append(" ".join(current_words))
            current_words = [word]
            if line_started_empty:
                cx, prev_id, min_left, max_right = t_cx, t_prev, t_min, t_max
            else:
                cx, prev_id, min_left, max_right = measure_extend(font_obj, word.encode(), 0, None, None, None)
    if current_words:
        wrapped_lines.append(" ".join(current_words))
    return "\n".join(wrapped_lines)

def word_wrap_text(display, text, max_width_pixels, scale):
    """
    Wrap text to fit within a specified width.

    Args:
        display: The display object to measure text with
        text: The text string to wrap
        max_width_pixels: Maximum width in pixels
        scale: Text scale factor

    Returns:
        String with newlines inserted for word wrapping
    """
    words = text.split()  # Split the text into words
    wrapped_lines = []
    current_line = ""

    for i, word in enumerate(words):
        # Measure the width of the current line with the new word added
        test_line = f"{current_line} {word}".strip()
        line_width_pixels = Font8.measure_text(test_line, scale)

        if line_width_pixels <= max_width_pixels:
            # If the line width is within the limit, add the word to the current line
            current_line = test_line
        else:
            # If the line width exceeds the limit, finalize the current line and start a new one
            wrapped_lines.append(current_line)
            current_line = word

    # Add the last line if it exists
    if current_line:
        wrapped_lines.append(current_line)

    return "\n".join(wrapped_lines)

def draw_textbox_outline(display, x, y, width, height):
    """DEBUG: Draw outline with random color around textbox"""
    debug_color = (random.randint(0, 255) << 16) | (random.randint(0, 255) << 8) | random.randint(0, 255)
    # Draw outline (border only) - top, bottom, left, right lines
    c = debug_color
    display.rect(int(x), int(y), int(width), 1, c, True)  # top
    display.rect(int(x), int(y + height - 1), int(width), 1, c, True)  # bottom
    display.rect(int(x), int(y), 1, int(height), c, True)  # left
    display.rect(int(x + width - 1), int(y), 1, int(height), c, True)  # right

def _layout_textbox(text, x, y, width, height, scale, align, valign, is_bmfont, bmfont_obj, wrap, out):
    if not is_bmfont:
        if wrap:
            line_count = text.count('\n') + 1
            text_height_pixels = line_count * 8 * scale
        else:
            text_height_pixels = 8 * scale

    if is_bmfont:
        bounds_w, bounds_h, min_x, min_y = measure_text(bmfont_obj, text.encode())
        if isinstance(scale, int) and scale >= 1:
            scale_up_i = scale
            scale_down_i = 1
        else:
            s = max(0.000001, float(scale))
            if s < 1.0:
                scale_up_i = 1
                scale_down_i = max(1, int(round(1.0 / s)))
            else:
                scale_up_i = max(1, int(round(s)))
                scale_down_i = 1

        line_count = text.count('\n') + 1
        text_height_pixels = (bmfont_obj.line_height * line_count * scale_up_i) // scale_down_i
        text_width_pixels = (bounds_w * scale_up_i) // scale_down_i
    else:
        text_width_pixels = Font8.measure_text(text, scale)
        scale_up_i = 1
        scale_down_i = 1
        min_x = 0

    if align == 'left':
        text_x_position = x
    elif align == 'right':
        text_x_position = x + width - text_width_pixels
    elif isinstance(x, int) and isinstance(width, int):
        text_x_position = x + (width - text_width_pixels) // 2
    else:
        text_x_position = x + width * 0.5 - text_width_pixels * 0.5

    if valign == 'top':
        text_y_position = y
    elif valign == 'bottom':
        text_y_position = y + height - text_height_pixels
    elif isinstance(y, int) and isinstance(height, int):
        text_y_position = y + (height - text_height_pixels) // 2
    else:
        text_y_position = y + height * 0.5 - text_height_pixels * 0.5

    if is_bmfont:
        out[0] = math.floor(text_x_position - (min_x * scale_up_i) // scale_down_i)
        out[1] = math.floor(text_y_position)
    else:
        out[0] = math.floor(text_x_position)
        out[1] = math.floor(text_y_position)
    out[2] = scale_up_i
    out[3] = scale_down_i


def draw_textbox(display, text, x, y, width, height, *, color, font='bitmap8', scale=1, align='center', wrap=False, valign='center', background=None):
    if background is not None and not text:
        display.rect(int(x), int(y), int(width), int(height), background, True)
        return

    is_bmfont = font != 'bitmap8'
    if is_bmfont:
        bmfont_obj, bm_pages = _get_bmfont(font)

    if wrap:
        if is_bmfont:
            text = _word_wrap_bmfont(bmfont_obj, text, width, scale)
        else:
            text = word_wrap_text(display, text, width, scale)

    _layout_textbox(text, x, y, width, height, scale, align, valign, is_bmfont,
                     bmfont_obj if is_bmfont else None, wrap, _LAYOUT_OUT)
    origin_x = _LAYOUT_OUT[0]
    origin_y = _LAYOUT_OUT[1]
    scale_up_i = _LAYOUT_OUT[2]
    scale_down_i = _LAYOUT_OUT[3]

    clip = (int(x), int(y), int(width), int(height))
    current_y = origin_y
    lines = text.split('\n')

    if is_bmfont:
        dw, dh = display.get_bounds()
        linebuf = display.get_scratch_buffer(bmfont_obj.scale_w)
        line_h_pixels = bmfont_obj.line_height

        for i, line in enumerate(lines):
            if current_y + line_h_pixels < y or current_y > y + height:
                if i > 0:
                     current_y += line_h_pixels
                continue

            if i > 0:
                current_y += line_h_pixels

            draw_text(
                display, dw, dh, bmfont_obj, bm_pages, line,
                origin_x,
                current_y,
                kerning=True, scale_up=scale_up_i, scale_down=scale_down_i, color=color,
                linebuf=linebuf, clip=clip, background=background,
                top_edge=(i == 0), bottom_edge=(i == len(lines) - 1)
            )
    else:
        line_h_pixels = Font8.height * scale

        for i, line in enumerate(lines):
            if current_y + line_h_pixels < y or current_y > y + height:
                 if i > 0:
                    current_y += line_h_pixels
                 continue

            if i > 0:
                current_y += line_h_pixels

            Font8.draw_text(display, line, origin_x, math.floor(current_y), color, scale=scale, clip=clip)

    # DEBUG: Draw outline
    #draw_textbox_outline(display, x, y, width, height)
