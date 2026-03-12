import asyncio
import gc

class LocalDisplay:
    def __init__(self, display, paths, start_offset):
        self.display = display
        self.paths = paths
        self.start_offset = start_offset
        self.display_width, self.display_height = self.display.get_bounds()
        self.path_index = 0

    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['local']
        display = provider['display']
        y_separator = provider['config']['display'].get('y_separator', 70)
        
        # Support both simple path array and config dict
        if isinstance(config, list):
            paths = config
        else:
            paths = config['paths']
            
        start_offset = y_separator * display.width * display.bytes_per_pixel
            
        return LocalDisplay(
            display,
            paths,
            start_offset
        )
       
    async def start(self):
        await asyncio.Event().wait()

    async def activate(self):
        # Update once, then cycle for next time
        await self.update()
        if self.paths:
            self.path_index = (self.path_index + 1) % len(self.paths)
        
        # After updating once, wait for next activation
        await asyncio.Event().wait()

    async def update(self):
        if not self.paths:
            return

        path = self.paths[self.path_index]
        
        # MicroPython uses 'rb' for reading binary files
        try:
            with open(path, 'rb') as f:
                # Slice the framebuffer taking into account the header offset
                framebuffer = self.display.framebuffer[self.start_offset:]

                # Read directly from file into framebuffer
                # MicroPython's readinto is efficient here
                bytes_read = f.readinto(framebuffer)
                
            # Tell display to update the screen (only the region we wrote to)
            # start_offset is in bytes
            bytes_per_pixel = self.display.bytes_per_pixel
            y_offset = (self.start_offset // bytes_per_pixel) // self.display_width
            height = self.display_height - y_offset
            self.display.update((0, y_offset, self.display_width, height))

            # Clean up
            gc.collect()
        except Exception as e:
            print(f"Error reading local image {path}: {e}")
