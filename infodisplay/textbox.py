import math

def draw_textbox(display, text, x, y, w, h, scale=1, thickness=None):
    """
    Draw text centered in a textbox with specified dimensions.
    
    Args:
        display: The display object to draw on
        text: The text string to render
        x: X position of the textbox
        y: Y position of the textbox  
        w: Width of the textbox
        h: Height of the textbox
        scale: Text scale factor (default: 1)
        thickness: Text thickness (optional, calculated from scale if not provided)
    """
    if thickness is None:
        thickness = scale * 3
    
    display.set_thickness(math.floor(thickness))
    
    text_width = display.measure_text(text, scale) + thickness
    
    text_x = w * 0.5 - text_width * 0.5
    half_height = h * 0.5
    
    display.text(text, 
                math.floor(text_x + x + (thickness * 0.5)), 
                math.floor(y + half_height + (thickness * 0.5)), 
                scale=scale)
