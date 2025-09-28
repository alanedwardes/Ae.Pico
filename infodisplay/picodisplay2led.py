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
        
    CREATION_PRIORITY = 1
    def create(provider):
        led_config = provider['config'].get('led', {})
        led_pins = led_config.get('pins')
        return PicoDisplay2Led(provider['hassws.HassWs'], led_config['entity_id'], led_pins)
    
    def entity_updated(self, entity_id, entity):
        color_str = entity.get('s', '')
        r, g, b = [int(x.strip()) for x in color_str.split(',')[:3]]
        self.led.set_rgb(r, g, b)
        print(f"LED color updated to {r}, {g}, {b}")

    async def start(self):
        await self.hass.subscribe([self.rgb_entity_id], self.entity_updated)
        await asyncio.Event().wait()
