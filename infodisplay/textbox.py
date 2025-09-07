import math
import random

def word_wrap_text(display, text, max_width, scale):
    """
    Wrap text to fit within a specified width.
    
    Args:
        display: The display object to measure text with
        text: The text string to wrap
        max_width: Maximum width in pixels
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
        line_width = display.measure_text(test_line, scale)

        if line_width <= max_width:
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

def draw_textbox_outline(display, x, y, w, h):
    """DEBUG: Draw outline with random color around textbox"""
    debug_color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    display.set_pen(display.create_pen(*debug_color))
    # Draw outline (border only) - top, bottom, left, right lines
    display.rectangle(int(x), int(y), int(w), 1)  # top
    display.rectangle(int(x), int(y + h - 1), int(w), 1)  # bottom
    display.rectangle(int(x), int(y), 1, int(h))  # left
    display.rectangle(int(x + w - 1), int(y), 1, int(h))  # right

def draw_textbox(display, text, x, y, w, h, *, font='sans', scale=1, align='center', wrap=False):
    """
    Draw text in a textbox with specified dimensions.
    
    Args:
        display: The display object to draw on
        text: The text string to render
        x: X position of the textbox
        y: Y position of the textbox  
        w: Width of the textbox
        h: Height of the textbox
        font: Font to use - 'sans' or 'bitmap8' (default: 'sans')
        scale: Text scale factor (default: 1)
        align: Text alignment - 'left', 'center', or 'right' (default: 'center')
        wrap: Whether to wrap text to fit within the textbox width (default: False)
    """
    # Set font
    display.set_font(font)

    # Apply word wrapping if requested
    if wrap:
        text = word_wrap_text(display, text, w, scale)

    # Set clipping bounds to the textbox area
    display.set_clip(int(x), int(y), int(w), int(h))
    
    # Calculate text height based on font
    if font == 'bitmap8':
        # For wrapped text, calculate height based on number of lines
        if wrap:
            line_count = text.count('\n') + 1
            text_height = line_count * 8 * scale
        else:
            text_height = 8 * scale
        thickness = 0  # Bitmap fonts don't use thickness
    else:  # sans font
        text_height = 12 * scale  # Approximate height for sans font
        thickness = scale * 3  # Automatically enable thickness for serif fonts
        display.set_thickness(math.floor(thickness))
    
    text_width = display.measure_text(text, scale) + thickness
    
    # Calculate text position based on alignment
    if align == 'left':
        text_x = x + thickness * 0.5
    elif align == 'right':
        text_x = x + w - text_width - (thickness * 0.5)
    else:  # center (default)
        text_x = x + w * 0.5 - text_width * 0.5
    
    # Calculate vertical position based on font rendering behavior
    if font == 'bitmap8':
        # Bitmap font: render from top-left, center it vertically in the textbox
        text_y = y + (h - text_height) * 0.5
    else:  # sans font
        # Sans font: center renders at Y, so move it down to center in textbox
        text_y = y + h * 0.5
    
    display.text(text, math.floor(text_x), math.floor(text_y), scale=scale)
    
    # DEBUG: Draw outline
    #draw_textbox_outline(display, x, y, w, h)
    
    # Remove clipping bounds
    display.remove_clip()
