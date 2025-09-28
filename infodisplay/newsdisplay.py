import utime
import asyncio
import textbox

class NewsDisplay:
    def __init__(self, display, entity_id, hass):
        self.display = display
        self.entity_id = entity_id
        self.hass = hass
        self.is_active = True

        self.display_width, self.display_height = self.display.get_bounds()
        
        self.last_updated = utime.localtime()
        self.story_index = 0
   
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['news']
        return NewsDisplay(provider['display'], config['entity_id'], provider['hassws.HassWs'])
    
    def entity_updated(self, entity_id, entity):
        self.last_updated = utime.localtime()
        self.update()
    
    async def start(self):
        await self.hass.subscribe([self.entity_id], self.entity_updated)
        await asyncio.Event().wait()

    def activate(self, new_active):
        self.is_active = new_active
        if self.is_active:
            self.update()
            self.story_index = (self.story_index + 1) % len(self.get_stories()) if len(self.get_stories()) > 0 else 0
    
    def get_stories(self):
        return self.hass.entities.get(self.entity_id, {}).get('a', {}).get('stories', [])

    def update(self):
        if self.is_active == False:
            return
        
        stories = self.get_stories()
               
        self.white = self.display.create_pen(255, 255, 255)
        self.black = self.display.create_pen(0, 0, 0)
        self.highlight = self.display.create_pen(242, 106, 48)
        self.grey = self.display.create_pen(128, 128, 128)
        
        y_offset = 70
        
        self.display.set_font("bitmap8")
        self.display.set_pen(self.black)
        self.display.rectangle(0, y_offset, self.display_width, self.display_height - y_offset)
        
        try:
            story = stories[self.story_index]
        except IndexError:
            story = dict(t='?', p='?')

        label_height = 25
            
        self.display.set_pen(self.grey)
        textbox.draw_textbox(self.display, "%i/%i %s" % (self.story_index + 1, len(stories), story['p']), 
                            0, y_offset, self.display_width, label_height, font='bitmap8', scale=2, align='left')
        
        y_offset += label_height
        
        self.display.set_pen(self.white)
        textbox.draw_textbox(self.display, story['t'], 0, y_offset, self.display_width, self.display_height - y_offset, font='bitmap8', scale=3, align='left', wrap=True, valign='top')
        self.display.update()