import utime
import asyncio
import gc
import textbox
import random
from httpstream import HttpRequest
from flatjson import parse_flat_json_array

class NewsDisplay:
    def __init__(self, display, url):
        self.display = display
        self.url = url
        self.stories = []
        self.display_width, self.display_height = self.display.get_bounds()
        self.story_index = 0

        # Pre-allocate HTTP request helper
        self._http_request = HttpRequest(url)

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['news']
        return NewsDisplay(provider['display'], config['url'])
    
    async def start(self):
        await asyncio.sleep(random.randint(5, 10))
        while True:
            await self.fetch_news_data()
            await asyncio.sleep(300) # Fetch every 5 minutes

    async def activate(self):
        self.update()
        self.story_index = (self.story_index + 1) % len(self.get_stories()) if len(self.get_stories()) > 0 else 0
    
    def get_stories(self):
        return self.stories
    
    async def fetch_news_data(self):
        try:
            # Use unified HTTP request helper
            reader, writer = await self._http_request.get()

            # Stream parse JSON array without buffering entire response
            self.stories = []
            async for story in parse_flat_json_array(reader):
                self.stories.append(story)

            writer.close()
            await writer.wait_closed()

            # Clean up after HTTP request
            import gc
            gc.collect()

            print(f"News data fetched: {len(self.stories)} stories")

        except Exception as e:
            print(f"Error fetching news data: {e}")

    def update(self):
        stories = self.get_stories()

        y_offset = 70

        self.display.rect(0, y_offset, self.display_width, self.display_height - y_offset, 0x0000, True)

        try:
            story = stories[self.story_index]
        except IndexError:
            story = '?'

        label_height = 16

        textbox.draw_textbox(self.display, story, 0, y_offset, self.display_width, self.display_height - y_offset, color=0xFFFF, font='regular', wrap=True)

        # Render only the news display region (below the time/temperature displays)
        self.display.update((0, y_offset, self.display_width, self.display_height - y_offset))