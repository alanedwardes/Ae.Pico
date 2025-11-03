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
        asyncio.create_task(self.update())
    
    async def start(self):
        await self.hass.subscribe([self.entity_id], self.entity_updated)
        await asyncio.Event().wait()

    def activate(self, new_active):
        self.is_active = new_active
        if self.is_active:
            asyncio.create_task(self.update())
            self.story_index = (self.story_index + 1) % len(self.get_stories()) if len(self.get_stories()) > 0 else 0
    
    def get_stories(self):
        return self.hass.entities.get(self.entity_id, {}).get('a', {}).get('stories', [])

    async def update(self):
        if self.is_active == False:
            return
        start_update_ms = utime.ticks_ms()
        
        stories = self.get_stories()
            
        y_offset = 70
        
        self.display.rect(0, y_offset, self.display_width, self.display_height - y_offset, 0x0000, True)
        
        try:
            story = stories[self.story_index]
        except IndexError:
            story = dict(t='?', p='?')

        label_height = 24

        self.display.rect(0, y_offset, self.display_width, label_height, 0xb000, True)
        textbox.draw_textbox(self.display, "%i/%i %s" % (self.story_index + 1, len(stories), story['p']), 
                            0, y_offset, self.display_width, label_height, color=0xFFFF, font='small')
        
        y_offset += label_height
        
        textbox.draw_textbox(self.display, story['t'], 0, y_offset, self.display_width, self.display_height - y_offset, color=0xFFFF, font='regular', wrap=True)
        await self.display.update()
        update_time_ms = utime.ticks_diff(utime.ticks_ms(), start_update_ms)
        print(f"NewsDisplay: {update_time_ms}ms")