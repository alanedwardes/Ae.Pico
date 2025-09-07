import math
import random

def draw_textbox_outline(display, x, y, w, h):
    """DEBUG: Draw outline with random color around textbox"""
    debug_color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    display.set_pen(display.create_pen(*debug_color))
    # Draw outline (border only) - top, bottom, left, right lines
    display.rectangle(int(x), int(y), int(w), 1)  # top
    display.rectangle(int(x), int(y + h - 1), int(w), 1)  # bottom
    display.rectangle(int(x), int(y), 1, int(h))  # left
    display.rectangle(int(x + w - 1), int(y), 1, int(h))  # right

def draw_textbox(display, text, x, y, w, h, *, font='sans', scale=1, auto_thickness=False, align='center'):
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
        auto_thickness: If True, calculate thickness from scale (for serif fonts). If False, use 0 (for bitmap fonts)
        align: Text alignment - 'left', 'center', or 'right' (default: 'center')
    """
    # Set font
    display.set_font(font)
    
    # Calculate text height based on font
    if font == 'bitmap8':
        text_height = 8 * scale
    else:  # sans font
        text_height = 12 * scale  # Approximate height for sans font
    
    if auto_thickness:
        thickness = scale * 3
    else:
        thickness = 0
    
    # Set clipping bounds to the textbox area
    display.set_clip(int(x), int(y), int(w), int(h))
    
    display.set_thickness(math.floor(thickness))
    
    text_width = display.measure_text(text, scale) + thickness
    
    # Calculate text position based on alignment
    if align == 'left':
        text_x = thickness * 0.5
    elif align == 'right':
        text_x = w - text_width - (thickness * 0.5)
    else:  # center (default)
        text_x = w * 0.5 - text_width * 0.5
    
    # Calculate vertical position based on font rendering behavior
    if font == 'bitmap8':
        # Bitmap font: top starts at Y, so center it vertically in the textbox
        text_y = y + (h - text_height) * 0.5
    else:  # sans font
        # Sans font: center renders at Y, so move it down to center in textbox
        text_y = y + h * 0.5
    
    display.text(text, 
                math.floor(text_x + x + (thickness * 0.5)), 
                math.floor(text_y), 
                scale=scale)
    
    # DEBUG: Draw outline
    #draw_textbox_outline(display, x, y, w, h)
    
    # Remove clipping bounds
    display.remove_clip()
