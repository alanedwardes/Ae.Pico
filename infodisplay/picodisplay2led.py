import asyncio
from machine import Pin, PWM

class RGBLED:
    def __init__(self, pin_r, pin_g, pin_b, invert=True, frequency=1000):
        self.invert = invert  # ACTIVE_LOW default to match previous Pimoroni behavior
        self._pwm_r = PWM(Pin(pin_r))
        self._pwm_g = PWM(Pin(pin_g))
        self._pwm_b = PWM(Pin(pin_b))
        self._pwm_r.freq(frequency)
        self._pwm_g.freq(frequency)
        self._pwm_b.freq(frequency)
        self.set_rgb(0, 0, 0)

    def set_rgb(self, r, g, b):
        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))
        self._apply((r, g, b))

    @staticmethod
    def _gamma_u16(x):
        # 2.8 gamma curve scaled to 16-bit to mirror C++ GAMMA_8BIT table usage
        return int(pow(x / 255.0, 2.8) * 65535 + 0.5) if x > 0 else 0

    def _apply(self, rgb):
        r16 = int(self._gamma_u16(rgb[0]))
        g16 = int(self._gamma_u16(rgb[1]))
        b16 = int(self._gamma_u16(rgb[2]))
        if self.invert:
            r16 = 65535 - r16
            g16 = 65535 - g16
            b16 = 65535 - b16
        self._pwm_r.duty_u16(r16)
        self._pwm_g.duty_u16(g16)
        self._pwm_b.duty_u16(b16)

class PicoDisplay2Led:
    def __init__(self, hass, rgb_entity_id, led_pins, brightness=1.0):
        self.hass = hass
        self.rgb_entity_id = rgb_entity_id
        self.led = RGBLED(*led_pins)
        self.brightness = brightness
        self._last_rgb = None
        self._fade_task = None
        
    CREATION_PRIORITY = 1
    def create(provider):
        led_config = provider['config'].get('led', {})
        led_pins = led_config.get('pins')
        brightness = float(led_config.get('brightness', 1.0))
        return PicoDisplay2Led(provider['hassws.HassWs'], led_config['entity_id'], led_pins, brightness)
    
    def entity_updated(self, entity_id, entity):
        color_str = entity.get('s', '')
        r, g, b = [int(x.strip()) for x in color_str.split(',')[:3]]
        target = (
            int(r * self.brightness),
            int(g * self.brightness),
            int(b * self.brightness)
        )
        if self._last_rgb is None:
            self._last_rgb = target
            self.led.set_rgb(*target)
            print(f"LED color updated to {target[0]}, {target[1]}, {target[2]}")
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
