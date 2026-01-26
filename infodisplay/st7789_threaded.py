import _thread
from time import sleep_ms
from st7789 import ST7789

class ST7789Threaded(ST7789):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Thread synchronization
        self._lock = _thread.allocate_lock()
        self._pending_update = False
        self._exit_flag = False
        
        # Pending region (x, y, w, h)
        # Initialize with invalid values
        self._px = 0
        self._py = 0
        self._pw = 0
        self._ph = 0
        
        # Buffers for the worker thread to use
        self._render_framebuffer = None
        self._render_width = 0
        self._render_height = 0
        
        # Start the worker thread
        _thread.start_new_thread(self._worker, ())

    def render(self, framebuffer, width, height, region):
        # Unpack region
        x, y, rw, rh = region
        
        # Validate input (fail fast before locking)
        if x < 0 or y < 0 or rw <= 0 or rh <= 0:
            return
        if x + rw > width or y + rh > height:
            return
            
        with self._lock:
            # Store the framebuffer reference and dimensions
            # Note: We assume the framebuffer object itself doesn't change identities often
            # or if it does, the caller keeps it alive.
            self._render_framebuffer = framebuffer
            self._render_width = width
            self._render_height = height
            
            if not self._pending_update:
                # No pending update, start a new one
                self._px = x
                self._py = y
                self._pw = rw
                self._ph = rh
                self._pending_update = True
            else:
                # Merge with existing pending region
                # Calculate new bounding box
                new_x = min(self._px, x)
                new_y = min(self._py, y)
                new_w = max(self._px + self._pw, x + rw) - new_x
                new_h = max(self._py + self._ph, y + rh) - new_y
                
                self._px = new_x
                self._py = new_y
                self._pw = new_w
                self._ph = new_h

    def _worker(self):
        while not self._exit_flag:
            should_render = False
            region = None
            fb = None
            w = 0
            h = 0
            
            with self._lock:
                if self._pending_update:
                    should_render = True
                    region = (self._px, self._py, self._pw, self._ph)
                    fb = self._render_framebuffer
                    w = self._render_width
                    h = self._render_height
                    
                    # Clear pending state
                    self._pending_update = False
                    self._px = 0
                    self._py = 0
                    self._pw = 0
                    self._ph = 0
            
            if should_render and fb is not None:
                # Call the parent class render method (synchronous SPI write)
                # This happens outside the lock so render() isn't blocked
                super().render(fb, w, h, region)
            else:
                # Sleep a bit to yield if nothing to do
                # A wait of 10-20ms is usually fine for UI responsiveness (50-100fps check rate)
                sleep_ms(10)

    def deinit(self):
        self._exit_flag = True
        # Wait a bit for thread to exit? 
        # MicroPython doesn't have join(), so we just hope for the best or rely on GC.
