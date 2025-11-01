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
            
        self.white = 0xFFFF
        self.black = 0x0000
        self.highlight = 0xF346
        self.grey = 0x8410
        
        y_offset = 70
        
        self.display.rect(0, y_offset, self.display_width, self.display_height - y_offset, self.black, True)
        
        try:
            story = stories[self.story_index]
        except IndexError:
            story = dict(t='?', p='?')

        label_height = 25
            
        textbox.draw_textbox(self.display, "%i/%i %s" % (self.story_index + 1, len(stories), story['p']), 
                            0, y_offset, self.display_width, label_height, color=self.grey, font='small', align='center')
        
        y_offset += label_height
        # Red divider between metadata and story
        divider_height = 4
        self.display.rect(0, y_offset, self.display_width, divider_height, 0xb000, True)
        y_offset += divider_height
        
        textbox.draw_textbox(self.display, story['t'], 0, y_offset, self.display_width, self.display_height - y_offset, color=self.white, font='regular', wrap=True, valign='top')
        self.display.update()