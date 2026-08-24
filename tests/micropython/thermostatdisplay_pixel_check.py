import asyncio
import os

import mpassets
from drawing import Drawing
from thermostatdisplay import ThermostatDisplay
from microcheck import check, check_pixels, summarize

WIDTH = 320
HEIGHT = 480
ENTITY = 'climate.living_room'

EXPECTED = {
    'thermostat rgb565': 0x9b1b5ae7,
}

class CountingDriver:
    def __init__(self):
        self.renders = 0

    def render(self, framebuffer, width, height, region):
        self.renders += 1

def _entity(target, current, hvac, extra=0):
    return {'s': 'heat', 'a': {
        'temperature': target, 'current_temperature': current,
        'min_temp': 7.0, 'max_temp': 35.0, 'hvac_action': hvac,
        'unrelated_attribute': extra}}

def main():
    if 'fonts' not in os.listdir('.'):
        os.chdir('cpython')
    mpassets.preload_fonts(('headline', 'small', 'regular'))

    display = Drawing(WIDTH, HEIGHT, 'RGB565')
    driver = CountingDriver()
    display.set_driver(driver)

    td = ThermostatDisplay(display, None, ENTITY, 70)
    td.entities[ENTITY] = _entity(21.5, 20.9, 'heating')

    asyncio.run(td.update())
    check('first update renders', driver.renders == 1,
          'renders = %d' % driver.renders)

    check_pixels('thermostat rgb565', display._framebuffer, EXPECTED.get('thermostat rgb565'))

    asyncio.run(td.update())
    check('identical update skipped', driver.renders == 1,
          'renders = %d' % driver.renders)

    td.entities[ENTITY] = _entity(21.5, 20.9, 'heating', extra=1)
    asyncio.run(td.update())
    check('unrelated attribute skipped', driver.renders == 1,
          'renders = %d' % driver.renders)

    td.entities[ENTITY] = _entity(21.5, 21.0, 'heating')
    asyncio.run(td.update())
    check('changed value renders', driver.renders == 2,
          'renders = %d' % driver.renders)

    td._rendered = None
    asyncio.run(td.update())
    check('reactivation renders', driver.renders == 3,
          'renders = %d' % driver.renders)

    summarize()

main()