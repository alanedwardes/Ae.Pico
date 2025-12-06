# Copyright (c) 2016-present Christian Schwinne and individual WLED contributors
#
# This file is part of Ae.Pico, which is a derivative work of WLED.
# Ae.Pico is licensed under the EUPL v. 1.2, the same license as WLED.
# A copy of the license is included in this directory.
#
# For more information, please see the WLED project at:
# https://github.com/Aircoookie/WLED

try:
    import ujson
except ModuleNotFoundError:
    import json as ujson

try:
    import machine
    import neopixel
except ImportError:
    machine = None
    neopixel = None
import management
import asyncio
import utime
import binascii
import os
import math
import wledpalettes
import wledeffects

class WLEDController:
    VERSION = "0.15.3"
    VID = 2305090
    # Match WLED C++ color order enums (see cfg.cpp: DEFAULT_LED_COLOR_ORDER).
    COLOR_ORDER_MAP = {
        "RGB": (0, 1, 2),
        "GRB": (1, 0, 2),
        "BRG": (2, 0, 1),
        "RBG": (0, 2, 1),
        "GBR": (1, 2, 0),
        "BGR": (2, 1, 0),
    }
    COLOR_ORDER_VALUES = {
        0: "RGB",
        1: "GRB",
        2: "BRG",
        3: "RBG",
        4: "GBR",
        5: "BGR",
    }
    
    def __init__(self, pin, num_leds, color_order="GRB", nic=None, max_brightness_pct=100):
        self.pin = pin
        self.num_leds = num_leds
        self.nic = nic
        self.color_order = self._normalize_color_order(color_order)
        # Safety cap to avoid overheating or overcurrent. 1–100 (% of requested brightness).
        self.max_brightness_pct = max(1, min(100, int(max_brightness_pct)))
        self.on = True
        self.brightness = 128
        self.transition = 7
        
        # Nightlight state
        self.nightlight = { "on": False, "dur": 60, "mode": 1, "tbri": 0, "rem": -1 }
        self._nightlight_start_ms = 0
        self._nightlight_start_bri = 0

        # Segments
        self.segments = [
            self._create_segment(0, 0, self.num_leds)
        ]
        self.mainseg = 0
        self.lor = 0
        self.udpn = { "send": False, "recv": True }
        self.live = False

        # Transition state
        self.transition_active = False
        self.transition_start = 0
        self.transition_duration = 0
        
        # Rendering buffer
        self.pixel_buffer = [(0,0,0)] * self.num_leds
        
        self.effects = wledeffects.SUPPORTED_EFFECTS
        self.palettes = wledpalettes.PALETTE_NAMES
        
        self.presets = {
            "0": {}
        }
        self.current_preset = -1
        
        self.np = neopixel.NeoPixel(self.pin, self.num_leds)
        
        self.mac = "00:00:00:00:00:00"
        self.ip = "0.0.0.0"
        self.hostname = None
        self.name = "WLED-Pico"
        self._init_network_identity()
            
        self._update_leds()

    def _create_segment(self, id, start, stop):
        seg = {
            "id": id,
            "on": True,
            "bri": 255,
            "col": [
                [255, 160, 0], # Default Orange
                [0, 0, 0],
                [0, 0, 0]
            ],
            "fx": 0, "sx": 128, "ix": 128, "pal": 0,
            "rev": False, "mi": False,
            "start": start, "stop": stop, "len": stop - start,
            "grp": 1, "spc": 0, "of": 0, "frz": False, "cct": 127,
            "sel": True
        }
        # Runtime state for transitions and effects
        is_on = self.on and seg['on']
        effective_bri = int(self.brightness * seg['bri'] / 255)
        
        seg['_current_bri'] = effective_bri if is_on else 0
        seg['_current_col'] = list(seg['col'][0])
        seg['_start_bri'] = seg['_current_bri']
        seg['_start_col'] = list(seg['_current_col'])
        return seg

    def _init_network_identity(self):
        mac_bytes = self.nic.config('mac')
        if mac_bytes:
            self.mac = binascii.hexlify(mac_bytes).decode('utf-8')

        if self.nic.isconnected():
            self.ip = self.nic.ifconfig()[0]

        hostname = None
        # Prefer explicit hostname, then DHCP hostname if provided.
        for key in ('hostname', 'dhcp_hostname'):
            try:
                value = self.nic.config(key)
            except Exception:
                value = None
            if value:
                hostname = value.decode('utf-8') if isinstance(value, (bytes, bytearray)) else str(value)
                break

        self.hostname = hostname
        if hostname:
            self.name = hostname

    CREATION_PRIORITY = 1
    @staticmethod
    def create(provider):
        config = provider['config'].get('wled', {})
        pin = config.get('pin')
        count = config.get('count')
        # Accept both numeric enum (0-5) and string (RGB/GRB/...) from config,
        # matching WLED C++ color order definitions.
        color_order = config.get('color_order', config.get('order', "GRB"))
        max_brightness_pct = config.get('max_brightness_pct', 100)
        mgmt = provider.get('management.ManagementServer')
        nic = provider.get('nic')
            
        controller = WLEDController(pin, count, color_order=color_order, nic=nic, max_brightness_pct=max_brightness_pct)
        mgmt.controllers.append(controller)
        return controller

    def _normalize_color_order(self, value):
        """Normalize user-supplied color order (int enum or string) to a valid key."""
        if isinstance(value, int):
            return self.COLOR_ORDER_VALUES.get(value, "GRB")
        if isinstance(value, str):
            order = value.strip().upper()
            # allow numeric strings like "2"
            if order.isdigit():
                as_int = int(order)
                return self.COLOR_ORDER_VALUES.get(as_int, "GRB")
            if order in self.COLOR_ORDER_MAP:
                return order
        return "GRB"

    def _color_order_code(self):
        """Return numeric enum (0-5) for reporting/debug, mirroring WLED C++ codes."""
        for code, name in self.COLOR_ORDER_VALUES.items():
            if name == self.color_order:
                return code
        return 1  # default to GRB code

    def _apply_color_order(self, color):
        """Re-map RGB color to the configured LED color order before writing."""
        idx = self.COLOR_ORDER_MAP.get(self.color_order, (0, 1, 2))
        return (color[idx[0]], color[idx[1]], color[idx[2]])

    async def start(self):
        while True:
            await self._tick()
            await asyncio.sleep(0.01)

    def route(self, method, path):
        # Handle potential query parameters by stripping them
        if b'?' in path:
            path = path.split(b'?')[0]
        
        # Strip trailing slash
        if path.endswith(b'/') and len(path) > 1:
            path = path[:-1]
            
        # Match WLED JSON API endpoints
        if path.startswith(b'/json'):
            return True
        if path == b'/presets.json':
            return True
        if path == b'/win':
            return True
        if path == b'/v':
            return True
        if path == b'/json/cfg':
            return True
        if path == b'/json/net':
            return True
        if path == b'/json/nodes':
            return True
        if path == b'/json/fxda':
            return True
        return False

    async def serve(self, method, path, headers, reader, writer):
        query = b''
        if b'?' in path:
            path, query = path.split(b'?', 1)
            
        # Strip trailing slash for internal logic
        if path.endswith(b'/') and len(path) > 1:
            path = path[:-1]
            
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
            if path == b'/win':
                params = self._parse_query_params(query)
                await self._handle_win_request(params)
                # The /win endpoint typically redirects or shows a simple status
                writer.write(management.OK_STATUS)
                writer.write(b'Content-Type: text/plain\r\n')
                writer.write(management.HEADER_TERMINATOR)
                writer.write(b'WLED-Pico OK')
            elif path == b'/v':
                self._write_json(writer, self._get_version_response())
            elif path == b'/json/info':
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
            elif path == b'/json/effects' or path == b'/json/eff':
                self._write_json(writer, self.effects)
            elif path == b'/json/palettes' or path == b'/json/pal':
                self._write_json(writer, self.palettes)
            elif path == b'/json/palx':
                params = self._parse_query_params(query)
                page = int(params.get(b'page', b'0'))
                self._write_json(writer, self._get_palettes_x_response(page))
            elif path == b'/json/live':
                self._write_json(writer, self._get_live_response())
            elif path == b'/json/si':
                response = {
                    'state': self._get_state_response(),
                    'info': self._get_info_response()
                }
                self._write_json(writer, response)
            elif path == b'/json/nodes':
                self._write_json(writer, self._get_nodes_response())
            elif path == b'/json/cfg':
                self._write_json(writer, self._get_cfg_response())
            elif path == b'/json/fxda':
                self._write_json(writer, self._get_fxda_response())
            else:
                writer.write(management.NOT_FOUND_STATUS)
                writer.write(management.HEADER_TERMINATOR)

    def _get_version_response(self):
        return {
            "version": self.VERSION,
            "vid": self.VID
        }

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
        
    def _parse_query_params(self, query):
        params = {}
        if query:
            pairs = query.split(b'&')
            for pair in pairs:
                if b'=' in pair:
                    key, val = pair.split(b'=', 1)
                    params[key] = val
        return params
        
    def _get_palettes_x_response(self, page=0):
        # WLED's /json/palx returns palettes in pages of 8
        palettes_per_page = 8
        start_index = page * palettes_per_page
        end_index = start_index + palettes_per_page
        
        response = {"p": []}
        
        for i in range(start_index, min(end_index, len(self.palettes))):
            palette_name = self.palettes[i]
            # Generate a representative gradient for the palette
            gradient = []
            for j in range(8): # 8 color stops for the preview
                color = self._get_palette_color(i, j * 32)
                gradient.append(f"[{color[0]},{color[1]},{color[2]}]")
            
            response["p"].append(f'"{i}":"{palette_name}",' + ",".join(gradient))

        # The JSON format for this endpoint is a bit unusual, it's a string
        # containing a JSON-like structure. We construct it manually.
        pages = "{" + "".join(response['p'])[:-1] + "}"
        return {"p": pages}

    def _get_palette_color(self, palette_id, position, seg=None):
        """Lightweight wrapper that mirrors WLED palette sampling."""
        seg = seg or (self.segments[0] if self.segments else None)
        return wledpalettes.get_palette_color(palette_id, position, seg)

    def _get_live_response(self):
        # Returns the current state of the LEDs as a JSON array
        # This is a simplified version of the WLED live view
        led_data = []
        for r, g, b in self.pixel_buffer:
            led_data.append(f'[{r},{g},{b}]')
        return "{\"leds\":[" + ",".join(led_data) + "]}"

    def _remap_pixel_index(self, i, seg):
        if seg['rev']:
            i = (seg['len'] - 1) - i
        
        if seg['mi']:
            half_len = seg['len'] // 2
            if i >= half_len:
                i = (seg['len'] - 1) - i
        return i

    async def _handle_win_request(self, params):
        update = {}
        seg_update = {}

        if b'A' in params: update['bri'] = int(params[b'A'])
        if b'T' in params: update['on'] = int(params[b'T']) != 0
        if b'FX' in params: seg_update['fx'] = int(params[b'FX'])
        if b'SX' in params: seg_update['sx'] = int(params[b'SX'])
        if b'IX' in params: seg_update['ix'] = int(params[b'IX'])
        if b'FP' in params: seg_update['pal'] = int(params[b'FP'])
        if b'PL' in params: update['ps'] = int(params[b'PL'])
        if b'RV' in params: seg_update['rev'] = bool(int(params.get(b'RV', 0)))
        if b'MI' in params: seg_update['mi'] = bool(int(params.get(b'MI', 0)))
        if b'SB' in params: seg_update['bri'] = int(params[b'SB'])

        # Color
        has_color = False
        r, g, b = self.segments[0]['col'][0]
        if b'R' in params: r = int(params[b'R']); has_color = True
        if b'G' in params: g = int(params[b'G']); has_color = True
        if b'B' in params: b = int(params[b'B']); has_color = True
        if has_color:
            seg_update['col'] = [[r, g, b]]

        if seg_update:
            seg_update['id'] = 0 # Target main segment
            update['seg'] = [seg_update]
            
        if update:
            await self._update_state(update)

    def _get_info_response(self):
        return {
            "ver": self.VERSION,
            "vid": self.VID,
            "color_order": self.color_order,
            "color_order_id": self._color_order_code(),
            "max_brightness_pct": self.max_brightness_pct,
            "leds": {
                "count": self.num_leds,
                "pwr": 0,
                "fps": 0,
                "maxpwr": 0, # Auto-brightness limiter disabled
                "maxseg": 16,
                "seglc": [1] * 16
            },
            "str": False,
        "name": self.name,
            "udpport": 0,
            "live": self.live,
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
            "transition": self.transition,
            "co": self._color_order_code(),
            "ps": self.current_preset,
            "pl": -1,
            "nl": self.nightlight,
            "udpn": self.udpn,
            "lor": self.lor,
            "mainseg": self.mainseg,
            "seg": self.segments
        }

    async def _update_state(self, data, from_preset=False):
        # Track whether anything that affects visible output changed; used to decide if a transition is needed.
        state_changed = any(k in data for k in ('on', 'bri', 'seg', 'ps', 'nl', 'lor', 'live', 'udpn', 'co'))
        transition_override = None
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


        # Handle Preset Saving & Deletion
        if 'psave' in data:
            preset_id = str(data['psave'])
            if preset_id != "0":
                # Create a snapshot of the current state for the preset
                preset_state = self._get_state_response()
                # Remove transition and preset fields before saving
                preset_state.pop('transition', None)
                preset_state.pop('ps', None)
                self.presets[preset_id] = preset_state

        if 'pdel' in data:
            preset_id = str(data['pdel'])
            if preset_id in self.presets:
                del self.presets[preset_id]

        if 'mainseg' in data:
            self.mainseg = int(data['mainseg'])

        if 'lor' in data:
            self.lor = int(data['lor'])

        if 'live' in data:
            self.live = bool(data['live'])

        if 'udpn' in data:
            self.udpn.update(data['udpn'])

        # Handle Nightlight
        if 'nl' in data:
            nl_data = data['nl']
            is_turning_on = False
            if isinstance(nl_data, bool):
                 if nl_data and not self.nightlight['on']: is_turning_on = True
                 self.nightlight['on'] = nl_data
                 self.nightlight['rem'] = self.nightlight['dur'] * 60 if nl_data else -1
            else:
                if nl_data.get('on') and not self.nightlight['on']: is_turning_on = True
                self.nightlight.update(nl_data)
            
            if is_turning_on:
                self._nightlight_start_ms = utime.ticks_ms()
                self._nightlight_start_bri = self.brightness

        # Handle color order (controller-level, matches WLED enum)
        if 'co' in data:
            self.color_order = self._normalize_color_order(data['co'])
        
        # Handle master brightness/on state
        if 'on' in data:
            val = data['on']
            if isinstance(val, str) and val.lower() == 't':
                self.on = not self.on
            else:
                self.on = bool(val)
            
        if 'bri' in data:
            self.brightness = int(data['bri'])
            
        # Handle segments
        if 'seg' in data:
            segs = data['seg']
            if isinstance(segs, list):
                for seg_update in segs:
                    seg_id = seg_update.get('id', -1)
                    
                    target_seg = next((s for s in self.segments if s['id'] == seg_id), None)
                    
                    if 'stop' in seg_update and seg_update['stop'] == 0:
                        if target_seg:
                            self.segments.remove(target_seg)
                            self._rebuild_segments()
                        continue
                        
                    if not target_seg:
                        # Create new segment
                        start = seg_update.get('start', 0)
                        stop = seg_update.get('stop', self.num_leds)
                        new_id = len(self.segments)
                        target_seg = self._create_segment(new_id, start, stop)
                        self.segments.append(target_seg)
                    
                    if 'start' in seg_update: target_seg['start'] = int(seg_update['start'])
                    if 'stop' in seg_update: target_seg['stop'] = int(seg_update['stop'])
                    target_seg['len'] = target_seg['stop'] - target_seg['start']

                    if 'col' in seg_update:
                        cols = seg_update['col']
                        if isinstance(cols, list) and len(cols) > 0:
                            target_seg['col'][0] = cols[0]
                            if len(cols) > 1: target_seg['col'][1] = cols[1]
                            if len(cols) > 2: target_seg['col'][2] = cols[2]
                    if 'bri' in seg_update: target_seg['bri'] = int(seg_update['bri'])
                    if 'on' in seg_update: target_seg['on'] = bool(seg_update['on'])
                    if 'fx' in seg_update: target_seg['fx'] = int(seg_update['fx'])
                    if 'pal' in seg_update: target_seg['pal'] = int(seg_update['pal'])
                    if 'ix' in seg_update: target_seg['ix'] = int(seg_update['ix'])
                    if 'sx' in seg_update: target_seg['sx'] = int(seg_update['sx'])
                    if 'rev' in seg_update: target_seg['rev'] = bool(seg_update['rev'])
                    if 'mi' in seg_update: target_seg['mi'] = bool(seg_update['mi'])
                    if 'frz' in seg_update: target_seg['frz'] = bool(seg_update['frz'])
                    if 'grp' in seg_update: target_seg['grp'] = int(seg_update['grp'])
                    if 'spc' in seg_update: target_seg['spc'] = int(seg_update['spc'])
                    if 'sel' in seg_update: target_seg['sel'] = bool(seg_update['sel'])
        
        if 'tt' in data:
            transition_override = int(data['tt'])
        elif 'transition' in data:
            self.transition = int(data['transition'])
            transition_override = self.transition

        if state_changed:
            duration = self.transition if transition_override is None else transition_override
            self._start_transition(duration)
        elif transition_override is not None:
            # Only update default transition duration without starting a new transition.
            self.transition = transition_override

    def _rebuild_segments(self):
        # Re-assign IDs to be contiguous
        for i, seg in enumerate(self.segments):
            seg['id'] = i
            
    async def _apply_preset(self, preset):
        await self._update_state(preset, from_preset=True)
        
    def _start_transition(self, duration_units):
        duration_units = max(0, int(duration_units))
        self.transition_duration = duration_units * 100
        if self.transition_duration > 0:
            self.transition_active = True
            self.transition_start = utime.ticks_ms()
            for seg in self.segments:
                seg['_start_bri'] = seg['_current_bri']
                seg['_start_col'] = list(seg['_current_col'])
        else:
            self.transition_active = False
            for seg in self.segments:
                is_on = self.on and seg['on']
                effective_bri = int(self.brightness * seg['bri'] / 255)
                seg['_current_bri'] = effective_bri if is_on else 0
                seg['_current_col'] = list(seg['col'][0])

    async def _tick(self):
        # End transition globally (once) before processing segments to avoid per-segment early termination.
        if self.transition_active:
            now = utime.ticks_ms()
            if utime.ticks_diff(now, self.transition_start) >= self.transition_duration:
                self.transition_active = False

        # Handle Nightlight
        if self.nightlight['on']:
            duration_ms = self.nightlight['dur'] * 60 * 1000
            now = utime.ticks_ms()
            elapsed = utime.ticks_diff(now, self._nightlight_start_ms)
            
            if elapsed >= duration_ms:
                self.brightness = self.nightlight['tbri']
                self.nightlight['on'] = False
                self.nightlight['rem'] = -1
            else:
                progress = elapsed / duration_ms
                target = self.nightlight['tbri']
                self.brightness = int(self._nightlight_start_bri + (target - self._nightlight_start_bri) * progress)
            
            self.nightlight['rem'] = (duration_ms - elapsed) // 1000 if elapsed < duration_ms else 0
            
        # Reset pixel buffer
        for i in range(self.num_leds):
            self.pixel_buffer[i] = (0,0,0)
            
        for seg in self.segments:
            self._process_segment(seg)

        # Ensure we mark transition complete after processing if it elapsed during the loop.
        if self.transition_active:
            now = utime.ticks_ms()
            if utime.ticks_diff(now, self.transition_start) >= self.transition_duration:
                self.transition_active = False

        self._render_pixels()

    def _ease_progress(self, progress):
        """Apply smoothstep easing for softer transitions."""
        progress = max(0.0, min(1.0, progress))
        return progress * progress * (3 - 2 * progress)

    def _process_segment(self, seg):
        # Combine master and segment state
        is_on = self.on and seg['on']
        capped_master_bri = int(self.brightness * self.max_brightness_pct / 100)
        effective_bri = int(capped_master_bri * seg['bri'] / 255)
        
        target_bri = effective_bri if is_on else 0
        target_col = seg['col'][0]

        # Allow palette colors for palette-capable effects (e.g. Breathe),
        # matching upstream WLED behavior instead of always using solid RGB.
        if (
            seg['fx'] != 0 and
            seg['pal'] not in [0, 2, 4] and
            seg['pal'] in wledpalettes.PALETTE_DATA
        ):
            target_col = list(wledpalettes.get_palette_color(seg['pal'], 0, seg))
        
        # Handle Transition
        if self.transition_active:
            now = utime.ticks_ms()
            elapsed = utime.ticks_diff(now, self.transition_start)
            if elapsed >= self.transition_duration:
                seg['_current_bri'] = target_bri
                seg['_current_col'] = list(target_col)
            else:
                linear_progress = elapsed / self.transition_duration
                progress = self._ease_progress(linear_progress)
                seg['_current_bri'] = int(seg['_start_bri'] + (target_bri - seg['_start_bri']) * progress)
                seg['_current_col'] = [
                    int(seg['_start_col'][0] + (target_col[0] - seg['_start_col'][0]) * progress),
                    int(seg['_start_col'][1] + (target_col[1] - seg['_start_col'][1]) * progress),
                    int(seg['_start_col'][2] + (target_col[2] - seg['_start_col'][2]) * progress)
                ]
        else:
            seg['_current_bri'] = target_bri
            seg['_current_col'] = list(target_col)
             
        if seg['frz']: return

        # Effects
        final_bri = seg['_current_bri']
        final_col = seg['_current_col']

        if is_on and seg['fx'] > 0:
            handler = wledeffects.resolve_effect_handler(seg['fx'])
            if handler:
                handler(self, seg)
                return

        self._update_segment_leds(seg, final_bri, final_col)

    def _update_segment_leds(self, seg, brightness, color):
        factor = brightness / 255.0
        use_palette = seg['pal'] not in [0, 2, 4] and seg['pal'] in wledpalettes.PALETTE_DATA

        if use_palette:
            for i in range(seg['start'], seg['stop']):
                local_i = i - seg['start']
                pal_color = wledpalettes.color_from_palette(seg, local_i, self._remap_pixel_index)
                if pal_color is None:
                    self.pixel_buffer[i] = (0, 0, 0)
                    continue
                r = int(pal_color[0] * factor)
                g = int(pal_color[1] * factor)
                b = int(pal_color[2] * factor)
                self.pixel_buffer[i] = (r, g, b)
        else:
            # Solid color
            r = int(color[0] * factor)
            g = int(color[1] * factor)
            b = int(color[2] * factor)
            color_tuple = (r, g, b)
            for i in range(seg['start'], seg['stop']):
                self.pixel_buffer[i] = color_tuple

    def _render_pixels(self):
        if self.np:
            for i in range(self.num_leds):
                ordered_color = self._apply_color_order(self.pixel_buffer[i])
                self.np[i] = ordered_color
            self.np.write()

    def _update_leds(self, brightness=None, color=None):
        # This method is now a legacy wrapper.
        # It's kept for the initial state update in __init__ but should be phased out.
        if self.np:
            seg = self.segments[0] # Assume segment 0 for this legacy call
            bri = brightness if brightness is not None else seg['_current_bri']
            col = color if color is not None else seg['_current_col']
            
            self._update_segment_leds(seg, bri, col)
            self._render_pixels()


    def _get_nodes_response(self):
        # In a real implementation, this would discover other WLED nodes
        return []

    def _get_cfg_response(self):
        # This is a placeholder. A real implementation would return a lot of config.
        return {"rev": [0,0], "vid": self.VID, "id": {"mdns": (self.hostname or "wled-pico"), "name": self.name}}

    def _get_fxda_response(self):
        # Placeholder. This should return detailed effect data.
        return "Not implemented"

