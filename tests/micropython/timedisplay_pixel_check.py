import asyncio
import os

import mpassets
from drawing import Drawing
import timedisplay
from microcheck import check_pixels, summarize

WIDTH = 320
HEIGHT = 480

EXPECTED = {
    'first render rgb565': 0x3b7fdb84,
    'tenth changed rgb565': 0xbb4afeb2,
    'second changed rgb565': 0xb165dec5,
    'first render gs8': 0x2de89e59,
}

class FakeTime:
    def __init__(self):
        self.now = [2026, 7, 28, 13, 37, 42, 1, 209, 300]

    def local_time(self):
        return tuple(self.now)

async def _prime(td):
    task = asyncio.create_task(td.start())
    await asyncio.sleep(0)
    task.cancel()

def main():
    if 'fonts' not in os.listdir('.'):
        os.chdir('cpython')
    mpassets.preload_fonts(('headline', 'small', 'regular'))

    display = Drawing(WIDTH, HEIGHT, 'RGB565')
    faketime = FakeTime()
    td = timedisplay.TimeDisplay(display, faketime, 70, True)

    asyncio.run(_prime(td))
    asyncio.run(td.update())
    check_pixels('first render rgb565', display._framebuffer, EXPECTED.get('first render rgb565'))

    faketime.now[8] = 400
    asyncio.run(td.update())
    check_pixels('tenth changed rgb565', display._framebuffer, EXPECTED.get('tenth changed rgb565'))

    faketime.now[5] = 43
    faketime.now[8] = 500
    asyncio.run(td.update())
    check_pixels('second changed rgb565', display._framebuffer, EXPECTED.get('second changed rgb565'))

    display_gs8 = Drawing(WIDTH, HEIGHT, 'GS8')
    td_gs8 = timedisplay.TimeDisplay(display_gs8, FakeTime(), 70, True)
    asyncio.run(_prime(td_gs8))
    asyncio.run(td_gs8.update())
    check_pixels('first render gs8', display_gs8._framebuffer, EXPECTED.get('first render gs8'))

    summarize()

main()