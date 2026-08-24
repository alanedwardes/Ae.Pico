import asyncio
import os

from bmfont import BMFont
import mpassets
from drawing import Drawing
import textbox
import timedisplay
from microbench import bench

def _preload_fonts(names):
    for name in names:
        textbox._BM_FONT_CACHE[name] = (
            BMFont.load(mpassets.stage('fonts/%s.fnt' % name)),
            [mpassets.load_bytes('fonts/%s_0.bin' % name)])

class FakeTime:
    def __init__(self):
        self.now = [2026, 7, 28, 13, 37, 42, 1, 209, 0]

    def local_time(self):
        return tuple(self.now)

def main():
    if 'fonts' not in os.listdir('.'):
        os.chdir('cpython')
    _preload_fonts(('headline', 'small', 'regular'))

    display = Drawing(320, 480, 'RGB565')
    faketime = FakeTime()
    td = timedisplay.TimeDisplay(display, faketime, 70, True)

    async def prime():
        task = asyncio.create_task(td.start())
        await asyncio.sleep(0)
        task.cancel()

    asyncio.run(prime())
    asyncio.run(td.update())

    def tenth_tick():
        faketime.now[8] = (faketime.now[8] + 100) % 1000
        asyncio.run(td.update())

    def second_tick():
        faketime.now[5] = (faketime.now[5] + 1) % 60
        asyncio.run(td.update())

    def idle_tick():
        asyncio.run(td.update())

    bench('tenths tick (10 Hz path)', tenth_tick)
    bench('seconds tick (1 Hz path)', second_tick)
    bench('idle tick (nothing changed)', idle_tick)

main()