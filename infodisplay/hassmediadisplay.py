import asyncio
import utime

from httpstream import parse_url, stream_reader_to_buffer

class HassMediaDisplay:
    def __init__(self, display, hass, event_bus, entity_id, background_converter, start_offset=0):
        self.display = display
        self.hass = hass
        self.event_bus = event_bus
        self.entity_id = entity_id
        self.background_converter = background_converter
        self.start_offset = start_offset
        self.current_image_url = None
        self.entity = None
        self.prev_state = None
        
        self.display_width, self.display_height = self.display.get_bounds()

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['media']
        return HassMediaDisplay(
            provider['display'],
            provider['hassws.HassWs'],
            provider['eventbus.EventBus'],
            config['entity_id'],
            config['background_converter'],
            config.get('start_offset', 0)
        )
    
    def entity_updated(self, entity_id, entity):
        if entity_id != self.entity_id:
            return
            
        should_request_focus = False
        
        # Store the entity data
        self.entity = entity
        
        # Check if media is playing and has an image
        state = entity.get('s', '')
        attributes = entity.get('a', {})
        entity_picture = attributes.get('entity_picture_local') or attributes.get('entity_picture')
        
        # Check if media just started playing (state changed to 'playing')
        if self.prev_state is not None and self.prev_state != 'playing' and state == 'playing':
            should_request_focus = True
        
        # Update previous state
        self.prev_state = state
        
        if entity_picture and state == 'playing':
            # Combine with Home Assistant base URL
            hass_url = self.hass.url.replace('ws://', 'http://').replace('wss://', 'https://')
            full_image_url = hass_url + entity_picture
            self.current_image_url = full_image_url
        else:
            self.current_image_url = None
        
        # Request focus if media just started playing
        if should_request_focus:
            self.event_bus.publish('focus.request', {
                'instance': self,
                'hold_ms': 5000  # Show for 5 seconds when media starts
            })
    
    async def start(self):
        await self.hass.subscribe([self.entity_id], self.entity_updated)
        await asyncio.Event().wait()
    
    def should_activate(self):
        return self.current_image_url is not None

    async def activate(self, new_active):
        self.is_active = new_active
        if self.is_active:
            await self.update()

    async def update(self):
        start_fetch_ms = utime.ticks_ms()
        await asyncio.wait_for(self.__update(), timeout=5)
        fetch_time_ms = utime.ticks_diff(utime.ticks_ms(), start_fetch_ms)
        print(f"HassMediaDisplay: {fetch_time_ms}ms")

    async def __update(self):
        # Construct the background converter URL with the image source
        converter_url = f"{self.background_converter}{self.current_image_url}"
        
        print(f"HassMediaDisplay: {converter_url}")
        uri = parse_url(converter_url)
        host, port, path, secure = uri.hostname, uri.port, uri.path, uri.secure
        
        reader, writer = await asyncio.open_connection(host, port, ssl=secure)
        
        # Write HTTP request
        writer.write(f'GET {path} HTTP/1.0\r\n'.encode('utf-8'))
        writer.write(f'Host: {host}\r\n'.encode('utf-8'))
        writer.write(b'\r\n')
        await writer.drain()
        
        # Read response status
        line = await reader.readline()
        status = line.split(b' ', 2)
        status_code = int(status[1])
        
        if status_code != 200:
            print(f"Failed to fetch framebuffer data: HTTP {status_code}")
            writer.close()
            await writer.wait_closed()
            return
        
        # Skip headers
        while True:
            line = await reader.readline()
            if line == b'\r\n':
                break
        
        # Check if still active before reading into framebuffer
        if not self.is_active:
            writer.close()
            await writer.wait_closed()
            return
        
        # Get direct access to the display framebuffer with offset
        framebuffer = memoryview(self.display)[self.start_offset:]
        
        # Stream data directly into framebuffer using shared method
        await stream_reader_to_buffer(reader, framebuffer)
        
        writer.close()
        await writer.wait_closed()

        # Tell display to update the screen (only the region we wrote to)
        # start_offset is in bytes, RGB565 uses 2 bytes per pixel
        y_offset = (self.start_offset // 2) // self.display_width
        height = self.display_height - y_offset
        self.display.update((0, y_offset, self.display_width, height))
