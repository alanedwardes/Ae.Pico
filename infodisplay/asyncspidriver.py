import time
import _thread
import array
import uctypes
import micropython
from mipidcs import _rgb565_to_888_line, _rgb332_to_888_line, _rgb332_to_565_line, _rgb565_swap_line


@micropython.viper
def core1_spi_push565_888(dma_read_addr: int, dma_write_addr: int,
                          dma_count_addr: int, dma_ctrl_addr: int,
                          ctrl_word: int, spi_dr: int, spi_sr: int,
                          write_len: int, linebuf_a: int, linebuf_b: int,
                          fb: ptr16, fb_width: int, fb_ptr0: int,
                          rw: int, rh: int, lut: ptr8):
    r_read = ptr32(dma_read_addr)
    r_write = ptr32(dma_write_addr)
    r_count = ptr32(dma_count_addr)
    r_ctrl = ptr32(dma_ctrl_addr)
    sr = ptr32(spi_sr)
    r_write[0] = spi_dr
    cur = linebuf_a
    nxt = linebuf_b
    _rgb565_to_888_line(ptr8(cur), fb, fb_ptr0, rw, lut)
    r_read[0] = cur
    r_count[0] = write_len
    r_ctrl[0] = ctrl_word
    i = 1
    while i < rh:
        _rgb565_to_888_line(ptr8(nxt), fb, fb_ptr0 + i * fb_width, rw, lut)
        while r_ctrl[0] & 0x4000000:
            pass
        r_read[0] = nxt
        r_count[0] = write_len
        r_ctrl[0] = ctrl_word
        t = cur; cur = nxt; nxt = t
        i += 1
    while r_ctrl[0] & 0x4000000:
        pass
    while sr[0] & 0x10:
        pass


@micropython.viper
def core1_spi_push332_888(dma_read_addr: int, dma_write_addr: int,
                          dma_count_addr: int, dma_ctrl_addr: int,
                          ctrl_word: int, spi_dr: int, spi_sr: int,
                          write_len: int, linebuf_a: int, linebuf_b: int,
                          fb: ptr8, fb_width: int, fb_ptr0: int,
                          rw: int, rh: int, lut: ptr8):
    r_read = ptr32(dma_read_addr)
    r_write = ptr32(dma_write_addr)
    r_count = ptr32(dma_count_addr)
    r_ctrl = ptr32(dma_ctrl_addr)
    sr = ptr32(spi_sr)
    r_write[0] = spi_dr
    cur = linebuf_a
    nxt = linebuf_b
    _rgb332_to_888_line(ptr8(cur), fb, fb_ptr0, rw, lut)
    r_read[0] = cur
    r_count[0] = write_len
    r_ctrl[0] = ctrl_word
    i = 1
    while i < rh:
        _rgb332_to_888_line(ptr8(nxt), fb, fb_ptr0 + i * fb_width, rw, lut)
        while r_ctrl[0] & 0x4000000:
            pass
        r_read[0] = nxt
        r_count[0] = write_len
        r_ctrl[0] = ctrl_word
        t = cur; cur = nxt; nxt = t
        i += 1
    while r_ctrl[0] & 0x4000000:
        pass
    while sr[0] & 0x10:
        pass


@micropython.viper
def core1_spi_push565_565(dma_read_addr: int, dma_write_addr: int,
                          dma_count_addr: int, dma_ctrl_addr: int,
                          ctrl_word: int, spi_dr: int, spi_sr: int,
                          write_len: int, linebuf_a: int, linebuf_b: int,
                          fb: ptr16, fb_width: int, fb_ptr0: int,
                          rw: int, rh: int, lut: ptr8):
    r_read = ptr32(dma_read_addr)
    r_write = ptr32(dma_write_addr)
    r_count = ptr32(dma_count_addr)
    r_ctrl = ptr32(dma_ctrl_addr)
    sr = ptr32(spi_sr)
    r_write[0] = spi_dr
    cur = linebuf_a
    nxt = linebuf_b
    _rgb565_swap_line(ptr16(cur), fb, fb_ptr0, rw, lut)
    r_read[0] = cur
    r_count[0] = write_len
    r_ctrl[0] = ctrl_word
    i = 1
    while i < rh:
        _rgb565_swap_line(ptr16(nxt), fb, fb_ptr0 + i * fb_width, rw, lut)
        while r_ctrl[0] & 0x4000000:
            pass
        r_read[0] = nxt
        r_count[0] = write_len
        r_ctrl[0] = ctrl_word
        t = cur; cur = nxt; nxt = t
        i += 1
    while r_ctrl[0] & 0x4000000:
        pass
    while sr[0] & 0x10:
        pass


@micropython.viper
def core1_spi_push332_565(dma_read_addr: int, dma_write_addr: int,
                          dma_count_addr: int, dma_ctrl_addr: int,
                          ctrl_word: int, spi_dr: int, spi_sr: int,
                          write_len: int, linebuf_a: int, linebuf_b: int,
                          fb: ptr8, fb_width: int, fb_ptr0: int,
                          rw: int, rh: int, lut: ptr8):
    r_read = ptr32(dma_read_addr)
    r_write = ptr32(dma_write_addr)
    r_count = ptr32(dma_count_addr)
    r_ctrl = ptr32(dma_ctrl_addr)
    sr = ptr32(spi_sr)
    r_write[0] = spi_dr
    cur = linebuf_a
    nxt = linebuf_b
    _rgb332_to_565_line(ptr8(cur), fb, fb_ptr0, rw, lut)
    r_read[0] = cur
    r_count[0] = write_len
    r_ctrl[0] = ctrl_word
    i = 1
    while i < rh:
        _rgb332_to_565_line(ptr8(nxt), fb, fb_ptr0 + i * fb_width, rw, lut)
        while r_ctrl[0] & 0x4000000:
            pass
        r_read[0] = nxt
        r_count[0] = write_len
        r_ctrl[0] = ctrl_word
        t = cur; cur = nxt; nxt = t
        i += 1
    while r_ctrl[0] & 0x4000000:
        pass
    while sr[0] & 0x10:
        pass


class AsyncSpiDriver:
    def __init__(self, display, framebuffer, fb_width, fb_height):
        self.display = display
        self._fb = framebuffer
        self.fb_width = fb_width
        self.fb_height = fb_height
        self._frames = array.array('i', [0])
        self._stop = array.array('i', [0])
        self._running = array.array('i', [0])
        self._setup_push(display)

    def _setup_push(self, disp):
        sd = disp._spi_dma
        if sd is None:
            raise RuntimeError('async SPI push needs RP2 DMA')
        base = uctypes.addressof(sd._dma.registers)
        self._dma_read = base + 0x00
        self._dma_write = base + 0x04
        self._dma_count = base + 0x08
        self._dma_ctrl = base + 0x0c
        self._ctrl_word = sd._ctrl
        self._spi_dr = sd._dr
        self._spi_sr = sd._sr
        self._lb_a = uctypes.addressof(disp._linebuf)
        self._lb_b = uctypes.addressof(disp._linebuf2)
        self._bpp = disp._bpp
        self._lut = disp._lut
        self._color_mode = disp.source_color_mode
        if self._bpp not in (2, 3):
            raise RuntimeError('async SPI push unsupported bpp %d' % self._bpp)
        if self._color_mode not in ('RGB332', 'RGB565'):
            raise RuntimeError('async SPI push unsupported source mode %s' % self._color_mode)

    def start(self):
        if self._running[0]:
            return
        self._stop[0] = 0
        self._running[0] = 1
        _thread.start_new_thread(self._loop, ())

    def render(self, fb, width, height, region):
        pass

    def set_backlight(self, b):
        if b <= 0:
            self.stop()
        else:
            self.start()
        self.display.set_backlight(b)

    @property
    def frames_pushed(self):
        return self._frames[0]

    def stop(self):
        self._stop[0] = 1
        deadline = time.ticks_add(time.ticks_ms(), 2000)
        while self._running[0] and time.ticks_diff(deadline, time.ticks_ms()) > 0:
            time.sleep_ms(5)

    def _loop(self):
        disp = self.display
        w = self.fb_width
        h = self.fb_height
        bpp = self._bpp
        cm = self._color_mode
        lut = self._lut
        fb = self._fb
        push_args = (self._dma_read, self._dma_write, self._dma_count,
                     self._dma_ctrl, self._ctrl_word, self._spi_dr, self._spi_sr,
                     w * bpp, self._lb_a, self._lb_b, fb, w, 0, w, h, lut)
        if bpp == 3:
            push = core1_spi_push332_888 if cm == 'RGB332' else core1_spi_push565_888
        else:
            push = core1_spi_push332_565 if cm == 'RGB332' else core1_spi_push565_565
        while self._stop[0] == 0:
            disp._set_region_window(0, 0, w, h)
            disp._spi_ctrl.write_cmd(b"\x2c")
            disp._spi_ctrl.start_data()
            push(*push_args)
            disp._spi_ctrl.end_data()
            self._frames[0] += 1
        self._running[0] = 0