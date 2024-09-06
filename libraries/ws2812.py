import array, time
import management
from machine import Pin
import rp2

@rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW, out_shiftdir=rp2.PIO.SHIFT_LEFT, autopull=True, pull_thresh=24)
def ws2812():
    T1 = 2
    T2 = 5
    T3 = 3
    wrap_target()
    label("bitloop")
    out(x, 1)               .side(0)    [T3 - 1]
    jmp(not_x, "do_zero")   .side(1)    [T1 - 1]
    jmp("bitloop")          .side(1)    [T2 - 1]
    label("do_zero")
    nop()                   .side(0)    [T2 - 1]
    wrap()

class Ws2812Controller:
    def route(self, method, path):
        return method == b'POST' and path == b'/ws2812'
    
    def serve(self, method, path, headers, connection):
        content_length = int(headers.get(b'content-length', '0'))
        form = management.parse_form(connection.read(content_length))
        
        NUM_LEDS = int(form.get(b'leds'))
        PIN_NUM = int(form.get(b'pin', b'0'))
        color = list(map(int, form.get(b'color', b'255, 255, 255').split(b',')))
        brightness = float(form.get(b'brightness', b'0.1'))
        
        connection.write(b'HTTP/1.0 200 OK\r\n')
        connection.write(b'Content-Type: text/plain\r\n')
        connection.write(b'\r\n')
        connection.write(b'OK')

        sm = rp2.StateMachine(0, ws2812, freq=8_000_000, sideset_base=Pin(PIN_NUM))
        sm.active(1)
        ar = array.array("I", [0 for _ in range(NUM_LEDS)])
        
        def pixels_show(brightness):
            dimmer_ar = array.array("I", [0 for _ in range(NUM_LEDS)])
            for i,c in enumerate(ar):
                r = int(((c >> 8) & 0xFF) * brightness)
                g = int(((c >> 16) & 0xFF) * brightness)
                b = int((c & 0xFF) * brightness)
                dimmer_ar[i] = (g<<16) + (r<<8) + b
            sm.put(dimmer_ar, 8)
            time.sleep_ms(10)

        def pixels_set(i, color):
            ar[i] = (color[1]<<16) + (color[0]<<8) + color[2]

        def pixels_fill(color):
            for i in range(len(ar)):
                pixels_set(i, color)

        pixels_fill(color)
        pixels_show(brightness)
        sm.active(0)
