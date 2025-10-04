import asyncio
import utime
import re

try:
    ThreadSafeFlag = asyncio.ThreadSafeFlag
except AttributeError:
    from threadsafeflag import ThreadSafeFlag

URL_RE = re.compile(r'(http|https)://([A-Za-z0-9-\.]+)(?:\:([0-9]+))?(.+)?')

class HassMediaDisplay:
    def __init__(self, display, hass, entity_id, background_converter, start_offset=0):
        self.display = display
        self.hass = hass
        self.entity_id = entity_id
        self.background_converter = background_converter
        self.start_offset = start_offset
        self.is_active = False
        self.update_flag = ThreadSafeFlag()
        self.current_image_url = None
        
        self.display_width, self.display_height = self.display.get_bounds()
        
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['media']
        return HassMediaDisplay(
            provider['display'],
            provider['hassws.HassWs'],
            config['entity_id'],
            config['background_converter'],
            config.get('start_offset', 0)
        )
    
    def entity_updated(self, entity_id, entity):
        if entity_id != self.entity_id:
            return
            
        # Check if media is playing
        state = entity.get('s', '')
        was_active = self.is_active
        self.is_active = (state == 'playing')
        
        # Get entity_picture attribute for background image
        attributes = entity.get('a', {})
        entity_picture = attributes.get('entity_picture')
        
        if entity_picture and self.is_active:
            # Combine with Home Assistant base URL
            hass_url = self.hass.url.replace('ws://', 'http://').replace('wss://', 'https://')
            full_image_url = hass_url + entity_picture
            
            # Only update if the image URL has changed
            if full_image_url != self.current_image_url:
                self.current_image_url = full_image_url
                self.update_flag.set()
        elif not self.is_active:
            self.current_image_url = None
        
        # Trigger update if activation state changed
        if was_active != self.is_active:
            self.update_flag.set()
    
    async def start(self):
        # Subscribe to the media entity
        await self.hass.subscribe([self.entity_id], self.entity_updated)
        
        while True:
            if self.is_active and self.current_image_url:
                await self.fetch_framebuffer()
                # Wait for either an update or activation change
                try:
                    await asyncio.wait_for(self.update_flag.wait(), 1.0)  # 1 second refresh
                except asyncio.TimeoutError:
                    pass
            else:
                # Wait for activation change
                await self.update_flag.wait()
    
    def should_activate(self):
        return self.is_active

    def activate(self, new_active):
        # This is handled by entity_updated based on media state
        pass

    def update(self):
        # This class doesn't use update() since it streams continuously
        # The main loop in start() handles the refresh timing
        pass
    
    def parse_url(self, url):
        match = URL_RE.match(url)
        if match:
            protocol = match.group(1)
            host = match.group(2)
            port = match.group(3)
            path = match.group(4)

            if protocol == 'https':
                if port is None:
                    port = 443
            elif protocol == 'http':
                if port is None:
                    port = 80
            else:
                raise ValueError('Scheme {} is invalid'.format(protocol))

            return (host, int(port), path if path else '/', protocol == 'https')
        raise ValueError('Invalid URL format')
    
    async def fetch_framebuffer(self):
        if not self.current_image_url:
            return
            
        start_fetch_ms = utime.ticks_ms()
        await self.__fetch_framebuffer()
        fetch_time_ms = utime.ticks_diff(utime.ticks_ms(), start_fetch_ms)
        print(f"HassMediaDisplay: {fetch_time_ms}ms")

    async def __fetch_framebuffer(self):
        try:
            # Construct the background converter URL with the image source
            converter_url = f"{self.background_converter}&src={self.current_image_url}"
            host, port, path, use_ssl = self.parse_url(converter_url)
            
            reader, writer = await asyncio.open_connection(host, port, ssl=use_ssl)
            
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
            
            # Stream data directly into framebuffer - read until no more data
            bytes_read = 0
            if hasattr(reader, 'readinto'):
                # MicroPython - keep reading chunks until no more data
                while bytes_read < len(framebuffer):
                    remaining_buffer = framebuffer[bytes_read:]
                    chunk_bytes = await reader.readinto(remaining_buffer)
                    if chunk_bytes is None or chunk_bytes == 0:
                        break
                    bytes_read += chunk_bytes
            else:
                # CPython - keep reading until no more data
                while bytes_read < len(framebuffer):
                    chunk = await reader.read(len(framebuffer) - bytes_read)
                    if not chunk:
                        break
                    chunk_len = len(chunk)
                    framebuffer[bytes_read:bytes_read + chunk_len] = chunk
                    bytes_read += chunk_len
            writer.close()
            await writer.wait_closed()
            
            # Tell display to update the screen
            self.display.update()
                
        except Exception as e:
            print(f"Error streaming framebuffer data: {e}")
