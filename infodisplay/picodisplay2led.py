import asyncio
try:
    from pimoroni import RGBLED
except ImportError:
    class RGBLED:
        def __init__(self, *args):
            pass
        def set_rgb(self, r, g, b):
            pass

class PicoDisplay2Led:
    def __init__(self, hass, rgb_entity_id, led_pins):
        self.hass = hass
        self.rgb_entity_id = rgb_entity_id
        self.led = RGBLED(*led_pins)
        self._last_rgb = None
        self._fade_task = None
        
    CREATION_PRIORITY = 1
    def create(provider):
        led_config = provider['config'].get('led', {})
        led_pins = led_config.get('pins')
        return PicoDisplay2Led(provider['hassws.HassWs'], led_config['entity_id'], led_pins)
    
    def entity_updated(self, entity_id, entity):
        color_str = entity.get('s', '')
        r, g, b = [int(x.strip()) for x in color_str.split(',')[:3]]
        target = (r, g, b)
        if self._last_rgb is None:
            self._last_rgb = target
            self.led.set_rgb(r, g, b)
            print(f"LED color updated to {r}, {g}, {b}")
            return
        if target == self._last_rgb:
            return
        if self._fade_task is not None and not self._fade_task.done():
            self._fade_task.cancel()
        self._fade_task = asyncio.create_task(self._fade_to(target))

    async def start(self):
        await self.hass.subscribe([self.rgb_entity_id], self.entity_updated)
        await asyncio.Event().wait()

    async def _fade_to(self, target, duration=0.3, steps=20):
        start = self._last_rgb
        dr = target[0] - start[0]
        dg = target[1] - start[1]
        db = target[2] - start[2]
        try:
            for i in range(1, steps + 1):
                nr = int(start[0] + dr * i / steps)
                ng = int(start[1] + dg * i / steps)
                nb = int(start[2] + db * i / steps)
                self.led.set_rgb(nr, ng, nb)
                self._last_rgb = (nr, ng, nb)
                await asyncio.sleep(duration / steps)
            self._last_rgb = target
            print(f"LED color updated to {target[0]}, {target[1]}, {target[2]}")
        except asyncio.CancelledError:
            raise
