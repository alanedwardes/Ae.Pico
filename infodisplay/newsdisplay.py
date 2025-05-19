import utime
import asyncio

class NewsDisplay:
    def __init__(self, display, entity_id, hass):
        self.display = display
        self.entity_id = entity_id
        self.hass = hass
        self.is_active = True
        
        self.white = 0
        self.black = 1        
        self.grey = 3

        self.display_width, self.display_height = self.display.get_bounds()
        
        self.last_updated = utime.localtime()
        self.stories = []
        self.story_index = 0
   
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['news']
        return NewsDisplay(provider['display'], config['entity_id'], provider['hassws.HassWs'])
    
    def entity_updated(self, entity_id, entity):
        self.stories = entity['a'].get('stories', [])
        self.last_updated = utime.localtime()
        self.update()
    
    async def start(self):
        await self.hass.subscribe([self.entity_id], self.entity_updated)
        await asyncio.Event().wait()

    def activate(self, new_active):
        self.is_active = new_active
        if self.is_active:
            self.update()
            self.story_index = (self.story_index + 1) % len(self.stories)

    def update(self):
        if self.is_active == False:
            return
        
        self.display.update_pen(self.white, 255, 255, 255)
        self.display.update_pen(self.black, 0, 0, 0)
        self.display.update_pen(self.grey, 128, 128, 128)
        
        y_offset = 70
        
        self.display.set_font("bitmap8")
        self.display.set_pen(self.black)
        self.display.rectangle(0, y_offset, self.display_width, self.display_height - y_offset)
        
        try:
            story = self.stories[self.story_index]
        except IndexError:
            story = dict(t='?', p='?')
            
        self.display.set_pen(self.grey)
        self.display.text("%i/%i %s" % (self.story_index + 1, len(self.stories), story['p']), 0, y_offset + 5, scale=2)
        
        y_offset += 30
        
        self.display.set_pen(self.white)
        self.display.text(self.__word_wrap(story['t'], self.display_width, 3), 0, y_offset, scale=3)
        self.display.update()
        
    def __word_wrap(self, text, max_width, scale):
        words = text.split()  # Split the text into words
        wrapped_lines = []
        current_line = ""

        for word in words:
            # Measure the width of the current line with the new word added
            test_line = f"{current_line} {word}".strip()
            line_width = self.display.measure_text(test_line, scale)

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