try:
    import ujson
except ModuleNotFoundError:
    import json as ujson

import utime
import asyncio
import textbox
from httpstream import parse_url

class NewsDisplay:
    def __init__(self, display, url):
        self.display = display
        self.url = url
        self.is_active = True
        self.stories = []

        self.display_width, self.display_height = self.display.get_bounds()
        
        self.last_updated = utime.localtime()
        self.story_index = 0

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['news']
        return NewsDisplay(provider['display'], config['url'])
    
    def entity_updated(self, entity_id, entity):
        self.last_updated = utime.localtime()
        self.update()
    
    async def start(self):
        while True:
            await self.fetch_news_data()
            self.update()
            await asyncio.sleep(300)  # Fetch every 5 minutes

    def activate(self, new_active):
        self.is_active = new_active
        if self.is_active:
            self.update()
            self.story_index = (self.story_index + 1) % len(self.get_stories()) if len(self.get_stories()) > 0 else 0
    
    def get_stories(self):
        return self.stories
    
    async def fetch_news_data(self):
        try:
            url = self.url
            uri = parse_url(url)
            host, port, path, secure = uri.hostname, uri.port, uri.path, uri.secure
            
            reader, writer = await asyncio.open_connection(host, port, ssl=secure)
            
            # Write HTTP request
            writer.write(f'GET {path} HTTP/1.0\r\n'.encode('utf-8'))
            writer.write(f'Host: {host}\r\n'.encode('utf-8'))
            writer.write(b'\r\n')
            await writer.drain()
            
            # Read response
            line = await reader.readline()
            status = line.split(b' ', 2)
            status_code = int(status[1])
            
            if status_code != 200:
                print(f"Failed to fetch news data: {status_code}")
                writer.close()
                await writer.wait_closed()
                return
            
            # Skip headers
            while True:
                line = await reader.readline()
                if line == b'\r\n':
                    break
            
            # Read content
            content = await reader.read()
            writer.close()
            await writer.wait_closed()
            
            self.stories = ujson.loads(content.decode('utf-8'))
            print(f"News data fetched: {len(self.stories)} stories")
                
        except Exception as e:
            print(f"Error fetching news data: {e}")

    def update(self):
        if self.is_active == False:
            return
        start_update_ms = utime.ticks_ms()
        
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
        update_time_ms = utime.ticks_diff(utime.ticks_ms(), start_update_ms)
        print(f"NewsDisplay: {update_time_ms}ms")