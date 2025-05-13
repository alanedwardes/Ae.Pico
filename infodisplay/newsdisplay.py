import utime
import asyncio

class NewsDisplay:
    def __init__(self, display, source, entity_id, title_attribute, hass):
        self.display = display
        self.source = source
        self.entity_id = entity_id
        self.title_attribute = title_attribute
        self.hass = hass
        self.is_active = True
        
        self.white = 0
        self.display.update_pen(self.white, 255, 255, 255)

        self.black = 2
        self.display.update_pen(self.black, 0, 0, 0)
       
        self.grey = 1
        self.display.update_pen(self.grey, 128, 128, 128)
       
        self.red = 5
        self.display.update_pen(self.red, 242, 106, 48)
        
        self.yellow = 8
        self.display.update_pen(self.yellow, 254, 219, 0)
        
        self.orange = 6
        self.display.update_pen(self.orange, 250, 163, 26)

        self.display_width, self.display_height = self.display.get_bounds()
        
        self.title = '?'
        self.last_updated = utime.localtime()
   
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['news']
        return NewsDisplay(provider['display'], config['source'], config['entity_id'], config['title_attribute'], provider['hassws.HassWs'])
    
    def entity_updated(self, entity_id, entity):
        self.title = entity['a'].get(self.title_attribute, [])
        self.last_updated = utime.localtime()
        self.update()
    
    async def start(self):
        await self.hass.subscribe([self.entity_id], self.entity_updated)
        await asyncio.Event().wait()

    def activate(self, new_active):
        self.is_active = new_active
        if self.is_active:
            self.update()

    def update(self):
        if self.is_active == False:
            return
        
        self.display.set_font("bitmap8")
        self.display.set_pen(self.black)
        self.display.rectangle(0, 80, self.display_width, self.display_height - 80)
        
        y_offset = 80
            
        self.display.set_pen(self.grey)
        self.display.text("%s UPDATED %02i:%02i:%02i" % (self.source, self.last_updated[3], self.last_updated[4], self.last_updated[5]), 0, y_offset)
        
        y_offset += 25
        
        self.display.set_pen(self.white)
        self.display.text(NewsDisplay.__word_wrap(self.title, 20), 0, y_offset, scale=3)
        self.display.update()
        
    def __word_wrap(text, width):
        words = text.split()  # Split the text into words
        wrapped_lines = []
        current_line = ""

        for word in words:
            # Check if adding the word would exceed the width
            if len(current_line) + len(word) + (1 if current_line else 0) <= width:
                # If the current line is not empty, add a space before the word
                if current_line:
                    current_line += " "
                current_line += word
            else:
                # If the current line is full, add it to the wrapped lines and start a new line
                wrapped_lines.append(current_line)
                current_line = word

        # Add the last line if it exists
        if current_line:
            wrapped_lines.append(current_line)

        return "\n".join(wrapped_lines)
