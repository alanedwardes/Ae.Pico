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

    draws = [0]
    _orig_rect = display.rect
    def _count_rect(*a, **k):
        draws[0] += 1
        return _orig_rect(*a, **k)
    display.rect = _count_rect

    td = ThermostatDisplay(display, None, ENTITY, 70)
    td.entities[ENTITY] = _entity(21.5, 20.9, 'heating')

    td.update()
    check('first update renders', draws[0] == 1, 'draws = %d' % draws[0])
    check_pixels('thermostat rgb565', display._framebuffer, EXPECTED.get('thermostat rgb565'))

    td.update()
    check('identical update skipped', draws[0] == 1, 'draws = %d' % draws[0])

    td.entities[ENTITY] = _entity(21.5, 20.9, 'heating', extra=1)
    td.update()
    check('unrelated attribute skipped', draws[0] == 1, 'draws = %d' % draws[0])

    td.entities[ENTITY] = _entity(21.5, 21.0, 'heating')
    td.update()
    check('changed value renders', draws[0] == 2, 'draws = %d' % draws[0])

    td._rendered = None
    td.update()
    check('reactivation renders', draws[0] == 3, 'draws = %d' % draws[0])

    summarize()

main()