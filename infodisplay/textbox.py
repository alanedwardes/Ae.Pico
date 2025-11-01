import math
import random

from bmfont import BMFont, draw_text, measure_text
from font8 import Font8

_BM_FONT_CACHE = {}

def _get_bmfont(font_name):
    if font_name not in _BM_FONT_CACHE:
        font_path = f"fonts/{font_name}.fnt"
        page_files = [open(f"fonts/{font_name}_0.bin", "rb")]
        _BM_FONT_CACHE[font_name] = (BMFont.load(font_path), page_files)
    return _BM_FONT_CACHE[font_name]

def _measure_bmfont(font_obj, text, scale):
    w, h, _min_x, _min_y = measure_text(font_obj, text)
    return w * scale, h * scale

def _word_wrap_bmfont(font_obj, text, max_width_pixels, scale):
    words = text.split()
    wrapped_lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip()
        line_width_pixels, _ = _measure_bmfont(font_obj, test_line, scale)
        if line_width_pixels <= max_width_pixels:
            current_line = test_line
        else:
            wrapped_lines.append(current_line)
            current_line = word
    if current_line:
        wrapped_lines.append(current_line)
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

    for word in words:
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
    debug_color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    # Draw outline (border only) - top, bottom, left, right lines
    r, g, b = debug_color
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    display.rect(int(x), int(y), int(width), 1, c, True)  # top
    display.rect(int(x), int(y + height - 1), int(width), 1, c, True)  # bottom
    display.rect(int(x), int(y), 1, int(height), c, True)  # left
    display.rect(int(x + width - 1), int(y), 1, int(height), c, True)  # right

def draw_textbox(display, text, x, y, width, height, *, color, font='bitmap8', scale=1, align='center', wrap=False, valign='center'):
    """
    Draw text in a textbox with specified dimensions.
    
    Args:
        display: The display object to draw on
        text: The text string to render
        x: X position of the textbox
        y: Y position of the textbox  
        width: Width of the textbox
        height: Height of the textbox
        font: Font to use - 'sans' or 'bitmap8' (default: 'sans')
        scale: Text scale factor (default: 1)
        align: Text alignment - 'left', 'center', or 'right' (default: 'center')
        wrap: Whether to wrap text to fit within the textbox width (default: False)
        valign: Vertical alignment - 'top', 'center', or 'bottom' (default: 'center')
    """
    is_bmfont = font != 'bitmap8'
    if is_bmfont:
        bmfont_obj, bm_pages = _get_bmfont(font)

    # Apply word wrapping if requested
    if wrap:
        if is_bmfont:
            text = _word_wrap_bmfont(bmfont_obj, text, width, scale)
        else:
            text = word_wrap_text(display, text, width, scale)
    
    # Calculate text dimensions based on font
    if not is_bmfont:
        # For wrapped text, calculate height based on number of lines
        if wrap:
            line_count = text.count('\n') + 1
            text_height_pixels = line_count * 8 * scale
        else:
            text_height_pixels = 8 * scale
        stroke_thickness = 0
    else:
        # We'll compute precise bounds below after scale factors are chosen
        stroke_thickness = 0

    if is_bmfont:
        # Use tight bounds that include glyph bearings
        bounds_w, bounds_h, min_x, min_y = measure_text(bmfont_obj, text)
        # Compute integer scale factors and scaled bounds now (needed for alignment)
        s = max(0.000001, float(scale))
        if s < 1.0:
            scale_up_i = 1
            scale_down_i = max(1, int(round(1.0 / s)))
        else:
            # Prefer nearest integer upscale
            scale_up_i = max(1, int(round(s)))
            scale_down_i = 1
        text_width_pixels = (bounds_w * scale_up_i) // scale_down_i
        text_height_pixels = (bounds_h * scale_up_i) // scale_down_i
    else:
        text_width_pixels = Font8.measure_text(text, scale)
    
    # Calculate horizontal text position based on alignment
    if align == 'left':
        text_x_position = x + stroke_thickness * 0.5
    elif align == 'right':
        text_x_position = x + width - text_width_pixels - (stroke_thickness * 0.5)
    else:  # center (default)
        text_x_position = x + width * 0.5 - text_width_pixels * 0.5
    
    # Calculate vertical text position; both fonts render from top-left
    if valign == 'top':
        text_y_position = y
    elif valign == 'bottom':
        text_y_position = y + height - text_height_pixels
    else:  # center (default)
        text_y_position = y + (height - text_height_pixels) * 0.5
    
    if is_bmfont:
        dw, dh = display.get_bounds()
        # Use previously computed integer scale factors and scaled bounds
        draw_text(
            display, dw, dh, bmfont_obj, bm_pages, text,
            # Shift origin by the tight-bounds min bearings so glyphs don't clip
            math.floor(text_x_position - (min_x * scale_up_i) // scale_down_i),
            math.floor(text_y_position - (min_y * scale_up_i) // scale_down_i),
            kerning=True, scale_up=scale_up_i, scale_down=scale_down_i, color=color
        )
    else:
        Font8.draw_text(display, text, math.floor(text_x_position), math.floor(text_y_position), color, scale=scale)
    
    # DEBUG: Draw outline
    draw_textbox_outline(display, x, y, width, height)
