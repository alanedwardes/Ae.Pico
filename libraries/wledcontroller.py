import ujson
try:
    import machine
    import neopixel
    import network
except ImportError:
    machine = None
    neopixel = None
    network = None
import management
import asyncio
import utime
import binascii

class WLEDController:
    VERSION = "0.14.0"
    VID = 2305090
    
    def __init__(self, pin_number, num_leds):
        self.pin_number = pin_number
        self.num_leds = num_leds
        self.on = True
        self.brightness = 128
        self.color = [255, 160, 0] # Default Orange
        
        # Transition state
        self._current_brightness = self.brightness
        self._current_color = list(self.color)
        self.transition_active = False
        self.transition_start = 0
        self.transition_duration = 0
        self.target_brightness = self.brightness
        self.target_color = list(self.color)
        self.start_brightness = self.brightness
        self.start_color = list(self.color)
        
        self.effects = ["Solid", "Blink", "Breathe"]
        self.palettes = ["Default", "Random Cycle", "Rainbow"]
        self.effect = 0
        self.palette = 0
        self.intensity = 128
        self.speed = 128
        self.reverse = False
        
        self.presets = {
            "0": {},
            "1": {
                "n": "Orange", "on": True, "bri": 128,
                "seg": [{"id": 0, "grp": 1, "spc": 0, "of": 0, "on": True, "frz": False, "bri": 255, "cct": 127, "col": [[255, 160, 0], [0, 0, 0], [0, 0, 0]], "fx": 0, "sx": 128, "ix": 128, "pal": 0, "sel": True, "rev": False, "mi": False}]
            },
            "2": {
                "n": "Blink Red", "on": True, "bri": 255,
                "seg": [{"id": 0, "grp": 1, "spc": 0, "of": 0, "on": True, "frz": False, "bri": 255, "cct": 127, "col": [[255, 0, 0], [0, 0, 0], [0, 0, 0]], "fx": 1, "sx": 128, "ix": 128, "pal": 0, "sel": True, "rev": False, "mi": False}]
            }
        }
        self.current_preset = -1
        self.nightlight = { "on": False, "dur": 60, "mode": 1, "tbri": 0, "rem": -1 }
        
        self.np = None
        if machine and neopixel:
            try:
                self.np = neopixel.NeoPixel(machine.Pin(pin_number), num_leds)
            except Exception:
                pass
        
        self.mac = "00:00:00:00:00:00"
        self.ip = "0.0.0.0"
        if network:
            try:
                nic = network.WLAN(network.STA_IF)
                mac_bytes = nic.config('mac')
                self.mac = binascii.hexlify(mac_bytes).decode('utf-8')
                if nic.isconnected():
                    self.ip = nic.ifconfig()[0]
            except Exception:
                pass
            
        self._update_leds()

    CREATION_PRIORITY = 1
    @staticmethod
    def create(provider):
        config = provider['config'].get('wled', {})
        pin = config.get('pin')
        count = config.get('count')
        mgmt = provider.get('management.ManagementServer')
        
        if pin is None or count is None or mgmt is None:
            return
            
        controller = WLEDController(pin, count)
        mgmt.controllers.append(controller)

    async def start(self):
        while True:
            await self._tick()
            await asyncio.sleep(0.02)

    def route(self, method, path):
        # Handle potential query parameters by stripping them
        if b'?' in path:
            path = path.split(b'?')[0]
            
        # Match WLED JSON API endpoints
        return path == b'/json' or path == b'/json/state' or path == b'/json/info' or path == b'/presets.json' or path == b'/json/effects' or path == b'/json/palettes'

    async def serve(self, method, path, headers, reader, writer):
        # Strip query params for internal logic
        if b'?' in path:
            path = path.split(b'?')[0]
            
        if method == b'POST' and (path == b'/json' or path == b'/json/state'):
            content_length = int(headers.get(b'content-length', '0'))
            if content_length > 0:
                body = await reader.readexactly(content_length)
                try:
                    data = ujson.loads(body)
                    print("WLED Payload:", data) # Debug: Print received payload
                    await self._update_state(data)
                except ValueError:
                    pass 
            
            response = self._get_state_response()
            self._write_json(writer, response)
            
        elif method == b'GET':
            if path == b'/json/info':
                self._write_json(writer, self._get_info_response())
            elif path == b'/json/state':
                self._write_json(writer, self._get_state_response())
            elif path == b'/json':
                response = {
                    'state': self._get_state_response(),
                    'info': self._get_info_response(),
                    'effects': self.effects,
                    'palettes': self.palettes
                }
                self._write_json(writer, response)
            elif path == b'/presets.json':
                self._write_json(writer, self._get_presets_response()) 
            elif path == b'/json/effects':
                self._write_json(writer, self.effects)
            elif path == b'/json/palettes':
                self._write_json(writer, self.palettes)
            else:
                writer.write(management.NOT_FOUND_STATUS)
                writer.write(management.HEADER_TERMINATOR)

    def _get_presets_response(self):
        return self.presets

    def _write_json(self, writer, data):
        writer.write(management.OK_STATUS)
        writer.write(b'Content-Type: application/json\r\n')
        writer.write(b'Access-Control-Allow-Origin: *\r\n')
        writer.write(b'Access-Control-Allow-Methods: POST, GET, OPTIONS\r\n')
        writer.write(b'Access-Control-Allow-Headers: Content-Type\r\n')
        
        json_bytes = ujson.dumps(data).encode('utf-8')
        writer.write(b'Content-Length: %d\r\n' % len(json_bytes))
        writer.write(management.HEADER_TERMINATOR)
        writer.write(json_bytes)
        
    def _get_info_response(self):
        return {
            "ver": self.VERSION,
            "vid": self.VID,
            "leds": {
                "count": self.num_leds,
                "pwr": 0,
                "fps": 0,
                "maxpwr": 0, # Auto-brightness limiter disabled
                "maxseg": 1
            },
            "str": False,
            "name": "WLED-Pico",
            "udpport": 0,
            "live": False,
            "lm": "",
            "ip": self.ip,
            "mac": self.mac,
            "ws": -1, 
            "fxcount": len(self.effects),
            "palcount": len(self.palettes),
            "arch": "pico",
            "core": "v" + self.VERSION,
            "freeheap": 0,
            "uptime": int(utime.ticks_ms() / 1000),
            "fs": {
                "u": 1,
                "t": 1,
                "pmt": 0
            }
        }

    def _get_state_response(self):
        return {
            "on": self.on,
            "bri": self.brightness,
            "transition": 7,
            "ps": self.current_preset,
            "pl": -1,
            "nl": self.nightlight,
            "udpn": { "send": False, "recv": True },
            "lor": 0,
            "mainseg": 0,
            "seg": [
                {
                    "id": 0,
                    "start": 0,
                    "stop": self.num_leds,
                    "len": self.num_leds,
                    "grp": 1,
                    "spc": 0,
                    "of": 0,
                    "on": self.on,
                    "frz": False,
                    "bri": self.brightness,
                    "cct": 127,
                    "col": [
                        self.color,
                        [0, 0, 0],
                        [0, 0, 0]
                    ],
                    "fx": self.effect,
                    "sx": self.speed,
                    "ix": self.intensity,
                    "pal": self.palette,
                    "sel": True,
                    "rev": self.reverse,
                    "mi": False
                }
            ]
        }

    async def _update_state(self, data, from_preset=False):
        # Check if manual changes should clear the preset
        # We assume 'on', 'bri', or 'seg' imply manual changes.
        if not from_preset and ('on' in data or 'bri' in data or 'seg' in data):
            self.current_preset = -1

        # Handle Presets
        if 'ps' in data:
            ps_val = data['ps']
            ps_id = str(ps_val)
            
            # Try direct ID match
            found_id = None
            if ps_id in self.presets:
                found_id = ps_id
            else:
                # Try finding by name
                for pid, pdata in self.presets.items():
                    if pdata.get('n') == ps_val:
                        found_id = pid
                        break
            
            if found_id:
                if found_id != "0":
                    self.current_preset = int(found_id)
                    await self._apply_preset(self.presets[found_id])
                else:
                    self.current_preset = -1



        # Handle Nightlight
        if 'nl' in data:
            nl_data = data['nl']
            if isinstance(nl_data, bool):
                 self.nightlight['on'] = nl_data
                 self.nightlight['rem'] = self.nightlight['dur'] * 60 if nl_data else -1
            else:
                self.nightlight.update(nl_data)

        # Handle master brightness/on state
        if 'on' in data:
            self.on = bool(data['on'])
            
        if 'bri' in data:
            self.brightness = int(data['bri'])
            
        # Handle segments
        if 'seg' in data:
            segs = data['seg']
            if isinstance(segs, list):
                for seg in segs:
                    apply_update = False
                    if 'id' in seg:
                        if int(seg['id']) == 0: apply_update = True
                    else:
                        apply_update = True
                        
                    if apply_update:
                        if 'col' in seg:
                            cols = seg['col']
                            if isinstance(cols, list) and len(cols) > 0:
                                self.color = cols[0]
                        if 'bri' in seg: self.brightness = int(seg['bri'])
                        if 'on' in seg: self.on = bool(seg['on'])
                        if 'fx' in seg: self.effect = int(seg['fx'])
                        if 'pal' in seg: self.palette = int(seg['pal'])
                        if 'ix' in seg: self.intensity = int(seg['ix'])
                        if 'sx' in seg: self.speed = int(seg['sx'])
                        if 'rev' in seg: self.reverse = bool(seg['rev'])
        
        transition_time = data.get('transition', 7)
        self._start_transition(transition_time)

    async def _apply_preset(self, preset):
        await self._update_state(preset, from_preset=True)
        
    def _start_transition(self, duration_units):
        self.transition_duration = duration_units * 100
        if self.transition_duration > 0:
            self.transition_active = True
            self.transition_start = utime.ticks_ms()
            self.start_brightness = self._current_brightness
            self.start_color = list(self._current_color)
        else:
            self.transition_active = False
            self._current_brightness = self.brightness
            self._current_color = list(self.color)

    async def _tick(self):
        target_bri = self.brightness if self.on else 0
        target_col = self.color
        
        # Handle Transition
        if self.transition_active:
            now = utime.ticks_ms()
            elapsed = utime.ticks_diff(now, self.transition_start)
            if elapsed >= self.transition_duration:
                self.transition_active = False
                self._current_brightness = target_bri
                self._current_color = list(target_col)
            else:
                progress = elapsed / self.transition_duration
                self._current_brightness = int(self.start_brightness + (target_bri - self.start_brightness) * progress)
                self._current_color = [
                    int(self.start_color[0] + (target_col[0] - self.start_color[0]) * progress),
                    int(self.start_color[1] + (target_col[1] - self.start_color[1]) * progress),
                    int(self.start_color[2] + (target_col[2] - self.start_color[2]) * progress)
                ]
        else:
             self._current_brightness = target_bri
             self._current_color = list(target_col)
             
        # Effects
        final_bri = self._current_brightness
        final_col = self._current_color
        
        if self.on and self.effect > 0:
             if self.effect == 1: # Blink
                 now = utime.ticks_ms()
                 speed_ms = (255 - self.speed) * 5 + 200
                 if (now // speed_ms) % 2 == 0:
                     final_bri = 0
             elif self.effect == 2: # Breathe
                 now = utime.ticks_ms()
                 speed_ms = (255 - self.speed) * 10 + 500
                 t = (now % speed_ms) / speed_ms
                 val = t * 2 if t < 0.5 else (1.0 - t) * 2
                 final_bri = int(final_bri * (0.1 + 0.9*val))

        self._update_leds(final_bri, final_col)

    def _update_leds(self, brightness=None, color=None):
        if self.np:
            bri = brightness if brightness is not None else self._current_brightness
            col = color if color is not None else self._current_color
            
            factor = bri / 255.0
            r = int(col[0] * factor)
            g = int(col[1] * factor)
            b = int(col[2] * factor)
            color_tuple = (r, g, b)
                
            for i in range(self.num_leds):
                self.np[i] = color_tuple
                    
            self.np.write()

