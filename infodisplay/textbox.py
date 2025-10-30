import math
import random

from bmfont import BMFont, draw_text, measure_text

NOTO_SANS_FONT = BMFont.load("fonts/notosans.fnt")
NOTO_SANS_PAGE_FILES = ["fonts/notosans_0.bin"]

def _measure_bmfont(text, scale):
    w, h = measure_text(NOTO_SANS_FONT, text)
    return w * scale, h * scale

def _word_wrap_bmfont(text, max_width_pixels, scale):
    words = text.split()
    wrapped_lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip()
        line_width_pixels, _ = _measure_bmfont(test_line, scale)
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
        line_width_pixels = display.measure_text(test_line, scale)

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
    display.set_pen(display.create_pen(*debug_color))
    # Draw outline (border only) - top, bottom, left, right lines
    display.rectangle(int(x), int(y), int(width), 1)  # top
    display.rectangle(int(x), int(y + height - 1), int(width), 1)  # bottom
    display.rectangle(int(x), int(y), 1, int(height))  # left
    display.rectangle(int(x + width - 1), int(y), 1, int(height))  # right

def draw_textbox(display, text, x, y, width, height, *, font='sans', scale=1, align='center', wrap=False, valign='center'):
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
    # Set font for non-bmfont paths
    if font != 'notosans':
        display.set_font(font)

    # Apply word wrapping if requested
    if wrap:
        text = word_wrap_text(display, text, width, scale)

    # Set clipping bounds to the textbox area
    display.set_clip(int(x), int(y), int(width), int(height))
    
    # Calculate text dimensions based on font
    if font == 'bitmap8':
        # For wrapped text, calculate height based on number of lines
        if wrap:
            line_count = text.count('\n') + 1
            text_height_pixels = line_count * 8 * scale
        else:
            text_height_pixels = 8 * scale
        stroke_thickness = 0  # Bitmap fonts don't use thickness
    elif font == 'notosans':
        if wrap:
            text = _word_wrap_bmfont(text, width, scale)
        _, text_height_pixels = _measure_bmfont(text if wrap else "A", scale)
        stroke_thickness = 0
    else:  # sans font
        if wrap:
            text = word_wrap_text(display, text, width, scale)
        text_height_pixels = 12 * scale
        stroke_thickness = scale * 3
        display.set_thickness(math.floor(stroke_thickness))

    if font == 'notosans':
        text_width_pixels, _ = _measure_bmfont(text, scale)
    else:
        text_width_pixels = display.measure_text(text, scale) + stroke_thickness
    
    # Calculate horizontal text position based on alignment
    if align == 'left':
        text_x_position = x + stroke_thickness * 0.5
    elif align == 'right':
        text_x_position = x + width - text_width_pixels - (stroke_thickness * 0.5)
    else:  # center (default)
        text_x_position = x + width * 0.5 - text_width_pixels * 0.5
    
    # Calculate vertical text position based on font rendering behavior and valign
    if font == 'bitmap8' or font == 'notosans':
        # Bitmap font: render from top-left
        if valign == 'top':
            text_y_position = y
        elif valign == 'bottom':
            text_y_position = y + height - text_height_pixels
        else:  # center (default)
            text_y_position = y + (height - text_height_pixels) * 0.5
    else:  # sans font
        # Sans font: center renders at Y
        if valign == 'top':
            text_y_position = y + text_height_pixels * 0.5
        elif valign == 'bottom':
            text_y_position = y + height - text_height_pixels * 0.5
        else:  # center (default)
            text_y_position = y + height * 0.5
    
    if font == 'notosans':
        fb = memoryview(display)
        dw, dh = display.get_bounds()
        draw_text(fb, dw, dh, NOTO_SANS_FONT, NOTO_SANS_PAGE_FILES, text, math.floor(text_x_position), math.floor(text_y_position), kerning=True, scale_up=scale, scale_down=1)
    else:
        display.text(text, math.floor(text_x_position), math.floor(text_y_position), scale=scale)
    
    # DEBUG: Draw outline
    #draw_textbox_outline(display, x, y, width, height)
    
    # Remove clipping bounds
    display.remove_clip()
