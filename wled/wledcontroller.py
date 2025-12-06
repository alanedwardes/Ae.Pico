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
    import network
except ImportError:
    machine = None
    neopixel = None
    network = None
import management
import asyncio
import utime
import binascii
import os
import palettes_data

class WLEDController:
    VERSION = "0.15.3"
    VID = 2305090
    
    def __init__(self, pin, num_leds):
        self.pin = pin
        self.num_leds = num_leds
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
        
        self.effects = [
            "Solid", "Blink", "Breathe", "Wipe", "Wipe Random", "Random Colors", "Sweep",
            "Dynamic", "Colorloop", "Rainbow", "Scan", "Scan Dual", "Fade", "Theater",
            "Theater Rainbow", "Running", "Saw", "Twinkle", "Dissolve", "Dissolve Rnd",
            "Sparkle", "Sparkle Dark", "Sparkle+", "Strobe", "Strobe Rainbow", "Strobe Mega",
            "Blink Rainbow", "Android", "Chase", "Chase Random", "Chase Rainbow", "Chase Flash",
            "Chase Flash Rnd", "Rainbow Runner", "Colorful", "Traffic Light", "Sweep Random",
            "Chase 2", "Aurora", "Stream", "Scanner", "Lighthouse", "Fireworks", "Rain",
            "Tetrix", "Fire Flicker", "Gradient", "Loading", "Rolling Balls", "Fairy", "Two Dots",
            "Fairytwinkle", "Running Dual", "Image", "Chase 3", "Tri Wipe", "Tri Fade",
            "Lightning", "ICU", "Multi Comet", "Scanner Dual", "Stream 2", "Oscillate",
            "Pride 2015", "Juggle", "Palette", "Fire 2012", "Colorwaves", "Bpm", "Fill Noise",
            "Noise 1", "Noise 2", "Noise 3", "Noise 4", "Colortwinkles", "Lake", "Meteor",
            "Copy Segment", "Railway", "Ripple", "Twinklefox", "Twinklecat", "Halloween Eyes", "Solid Pattern",
            "Solid Pattern Tri", "Spots", "Spots Fade", "Glitter", "Candle", "Fireworks Starburst",
            "Fireworks 1D", "Bouncing Balls", "Sinelon", "Sinelon Dual", "Sinelon Rainbow",
            "Popcorn", "Drip", "Plasma", "Percent", "Ripple Rainbow", "Heartbeat", "Pacifica",
            "Candle Multi", "Solid Glitter", "Sunrise", "Phased", "Twinkleup", "Noise Pal", "Sine",
            "Phased Noise", "Flow", "Chunchun", "Dancing Shadows", "Washing Machine", "2D Plasma Rotozoom",
            "Blends", "TV Simulator", "Dynamic Smooth", "2D Spaceships", "2D Crazybees", "2D Ghostrider",
            "2D Blobs", "2D Scrolltext", "2D Driftrose", "2D Distortionwaves", "2D Soap", "2D Octopus",
            "2D Wavingcell", "Pixels", "Pixelwave", "Juggles", "Matripix", "Gravimeter", "Plasmoid",
            "Puddles", "Midnoise", "Noisemeter", "Freqwave", "Freqmatrix", "2D GEQ", "Waterfall",
            "Freqpixels", "Binmap", "Noisefire", "Puddlepeak", "Noisemove", "2D Noise", "Perlinmove",
            "Ripplepeak", "2D Firenoise", "2D Squaredswirl", "Not Implemented", "2D DNA", "2D Matrix",
            "2D Metaballs", "Freqmap", "Gravcenter", "Gravcentric", "DJ Light", "2D Funkyplank", "Shimmer",
            "2D Pulser", "Blurz", "2D Drift", "2D Waverly", "2D Sunradiation", "2D Coloredbursts",
            "2D Julia", "Not Implemented", "Not Implemented", "Not Implemented", "Not Implemented",
            "2D Gameoflife", "2D Tartan", "2D Polarlights", "2D Swirl", "2D Lissajous", "2D Frizzles",
            "2D Plasmaball", "Flow Stripe", "2D Hipnotic", "2D Sindots", "2D Dnasprial", "2D Blackhole",
            "Wavesins", "Rocktaves", "2D Akemi", "Particle Volcano", "Particle Fire",
            "Particle Fireworks", "Particle Vortex", "Particle Perlin", "Particle Pit", "Particle Box",
            "Particle Attractor", "Particle Impact", "Particle Waterfall", "Particle Spray",
            "Particle sGEQ", "Particle CenterGEQ", "Particle Ghostrider", "Particle Blobs", "PS Drip",
            "PS Pinball", "PS Dancing Shadows", "PS Fireworks 1D", "PS Sparkler", "PS Hourglass",
            "PS 1D Spray", "PS Balance", "PS Chase", "PS Starburst", "PS 1D GEQ", "PS Fire 1D",
            "PS 1D Sonic Stream", "PS 1D Sonic Boom", "PS 1D Springy", "Particle Galaxy"
        ]
        self.palettes = palettes_data.PALETTE_NAMES
        
        self.presets = {
            "0": {}
        }
        self.current_preset = -1
        
        self.np = neopixel.NeoPixel(self.pin, self.num_leds)
        
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

    CREATION_PRIORITY = 1
    @staticmethod
    def create(provider):
        config = provider['config'].get('wled', {})
        pin = config.get('pin')
        count = config.get('count')
        mgmt = provider.get('management.ManagementServer')
            
        controller = WLEDController(pin, count)
        mgmt.controllers.append(controller)
        return controller

    async def start(self):
        while True:
            await self._tick()
            await asyncio.sleep(0.02)

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
            elif path == b'/json/net':
                self._write_json(writer, self._get_net_response())
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
            "leds": {
                "count": self.num_leds,
                "pwr": 0,
                "fps": 0,
                "maxpwr": 0, # Auto-brightness limiter disabled
                "maxseg": 16,
                "seglc": [1] * 16
            },
            "str": False,
            "name": "WLED-Pico",
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
            "ps": self.current_preset,
            "pl": -1,
            "nl": self.nightlight,
            "udpn": self.udpn,
            "lor": self.lor,
            "mainseg": self.mainseg,
            "seg": self.segments
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
        
        transition_time = -1
        if 'tt' in data:
            transition_time = data['tt']
        elif 'transition' in data:
            self.transition = int(data['transition'])
            transition_time = self.transition
        
        if transition_time != -1:
            self._start_transition(transition_time)
        else:
            # Default transition if none specified
            self._start_transition(self.transition)

    def _rebuild_segments(self):
        # Re-assign IDs to be contiguous
        for i, seg in enumerate(self.segments):
            seg['id'] = i
            
    async def _apply_preset(self, preset):
        await self._update_state(preset, from_preset=True)
        
    def _start_transition(self, duration_units):
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

        self._render_pixels()

    def _process_segment(self, seg):
        # Combine master and segment state
        is_on = self.on and seg['on']
        effective_bri = int(self.brightness * seg['bri'] / 255)
        
        target_bri = effective_bri if is_on else 0
        target_col = seg['col'][0]
        
        # Handle Transition
        if self.transition_active:
            now = utime.ticks_ms()
            elapsed = utime.ticks_diff(now, self.transition_start)
            if elapsed >= self.transition_duration:
                self.transition_active = False # This should be global
                seg['_current_bri'] = target_bri
                seg['_current_col'] = list(target_col)
            else:
                progress = elapsed / self.transition_duration
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
             if seg['fx'] == 1: # Blink
                 now = utime.ticks_ms()
                 speed_ms = (255 - seg['sx']) * 5 + 200
                 if (now // speed_ms) % 2 == 0:
                     final_bri = 0
                 else:
                     final_bri = int(final_bri * (seg['ix'] / 255.0))
             elif seg['fx'] == 2: # Breathe
                 now = utime.ticks_ms()
                 speed_ms = (255 - seg['sx']) * 10 + 500
                 t = (now % speed_ms) / speed_ms
                 val = t * 2 if t < 0.5 else (1.0 - t) * 2
                 final_bri = int(final_bri * (0.1 + 0.9*val) * (seg['ix'] / 255.0))
             elif seg['fx'] == 3: # Color Wipe
                self._effect_color_wipe(seg)
                return
             elif seg['fx'] == 8: # Colorloop
                # This effect uses per-LED updates and writes directly to the buffer.
                self._effect_rainbow(seg)
                return
             elif seg['fx'] == 9: # Rainbow (similar to Colorloop, reuses implementation)
                self._effect_rainbow(seg)
                return
             elif seg['fx'] == 10: # Scan
                self._effect_scan(seg)
                return
             elif seg['fx'] == 13: # Theater
                self._effect_theater_chase(seg)
                return

        self._update_segment_leds(seg, final_bri, final_col)

    def _update_segment_leds(self, seg, brightness, color):
        factor = brightness / 255.0
        r = int(color[0] * factor)
        g = int(color[1] * factor)
        b = int(color[2] * factor)
        color_tuple = (r, g, b)

        for i in range(seg['start'], seg['stop']):
            self.pixel_buffer[i] = color_tuple

    def _render_pixels(self):
        if self.np:
            for i in range(self.num_leds):
                self.np[i] = self.pixel_buffer[i]
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


    def _get_palette_color(self, palette_id, position):
        """ Get a color from a palette. Position is 0-255. """
        
        # Ensure palette data exists
        data = palettes_data.PALETTE_DATA.get(palette_id)
        if not data:
            return self.segments[0]['col'][0] # Default to primary color

        # Ensure position is 0-255
        position = position % 256

        # Find interval p1 (start) and p2 (end) where p1.pos <= position < p2.pos
        p1 = data[-1]
        p2 = data[0]
        
        for point in data:
            if point[0] > position:
                p2 = point
                break
            p1 = point
            
        # Calculate fraction
        idx1 = p1[0]
        idx2 = p2[0]
        
        if idx2 < idx1: # Wrap around
            idx2 += 256
            if position < idx1:
                position += 256
        
        delta = idx2 - idx1
        if delta == 0: return (p1[1], p1[2], p1[3])
        
        frac = (position - idx1) / delta
        
        r = int(p1[1] + (p2[1] - p1[1]) * frac)
        g = int(p1[2] + (p2[2] - p1[2]) * frac)
        b = int(p1[3] + (p2[3] - p1[3]) * frac)
        
        return (r, g, b)

    def _color_blend(self, c1, c2, frac):
        frac = frac / 255.0
        r = int(c1[0] + (c2[0] - c1[0]) * frac)
        g = int(c1[1] + (c2[1] - c1[1]) * frac)
        b = int(c1[2] + (c2[2] - c1[2]) * frac)
        return (r,g,b)

    def _get_nodes_response(self):
        # In a real implementation, this would discover other WLED nodes
        return []

    def _get_net_response(self):
        # Scan for wifi networks. This can be slow.
        networks = []
        if network:
            try:
                nic = network.WLAN(network.STA_IF)
                if not nic.active(): nic.active(True)
                scan_results = nic.scan()
                for res in scan_results:
                    ssid, bssid, channel, rssi, authmode, hidden = res
                    networks.append({
                        "ssid": ssid.decode('utf-8', 'ignore'),
                        "rssi": rssi,
                        "ch": channel,
                        "enc": authmode
                    })
            except Exception:
                pass # ignore errors
        return {"networks": networks}

    def _get_cfg_response(self):
        # This is a placeholder. A real implementation would return a lot of config.
        return {"rev": [0,0], "vid": self.VID, "id": {"mdns": "wled-pico", "name": "WLED-Pico"}}

    def _get_fxda_response(self):
        # Placeholder. This should return detailed effect data.
        return "Not implemented"

    def _effect_rainbow(self, seg):
        if not self.np: return
        
        now = utime.ticks_ms()
        speed = seg['sx']
        intensity = seg['ix']
        
        # Calculate the effective brightness from the transitioning value
        effective_bri = seg['_current_bri']
        factor = effective_bri / 255.0
        
        for i in range(seg['start'], seg['stop']):
            # Calculate hue based on position and time
            # Use segment-local position for the effect
            local_i = i - seg['start']
            
            # Remap for mirror and reverse
            remapped_i = self._remap_pixel_index(local_i, seg)
            
            hue = ((remapped_i * 255) // seg['len'] + (now * speed // 100)) & 255
            
            # Get the color from the palette
            color = self._get_palette_color(seg['pal'], hue)
            
            # Apply brightness and intensity
            r = int(color[0] * factor * (intensity / 255.0))
            g = int(color[1] * factor * (intensity / 255.0))
            b = int(color[2] * factor * (intensity / 255.0))
            
            self.pixel_buffer[i] = (r, g, b)
        
        # This effect writes to the buffer, _render_pixels will handle the final write.

    def _effect_color_wipe(self, seg):
        now = utime.ticks_ms()
        speed = seg['sx']
        
        # Calculate progress
        cycle_duration = (256 - speed) * 10
        progress = (now % cycle_duration) / cycle_duration
        
        wipe_pos = int(seg['len'] * progress)
        
        effective_bri = seg['_current_bri']
        factor = effective_bri / 255.0
        intensity = seg['ix'] / 255.0
        
        for i in range(seg['len']):
            idx = seg['start'] + i
            
            local_i = i
            remapped_i = self._remap_pixel_index(local_i, seg)
            
            color = self._get_palette_color(seg['pal'], (remapped_i * 255 // seg['len']) & 255 )
            
            if (i <= wipe_pos and not seg['rev']) or (i > (seg['len'] - wipe_pos) and seg['rev']):
                r = int(color[0] * factor * intensity)
                g = int(color[1] * factor * intensity)
                b = int(color[2] * factor * intensity)
                self.pixel_buffer[idx] = (r, g, b)
            else:
                self.pixel_buffer[idx] = (0,0,0)

    def _effect_scan(self, seg):
        now = utime.ticks_ms()
        speed = seg['sx']
        
        cycle_duration = (256 - speed) * 20
        progress = (now % cycle_duration) / cycle_duration
        
        # Ping-pong motion
        if progress > 0.5:
            progress = 1.0 - progress
        scan_pos = int(seg['len'] * progress * 2)
        
        effective_bri = seg['_current_bri']
        factor = effective_bri / 255.0
        intensity = seg['ix'] / 255.0
        
        color = self._get_palette_color(seg['pal'], 0)
        r = int(color[0] * factor * intensity)
        g = int(color[1] * factor * intensity)
        b = int(color[2] * factor * intensity)
        
        for i in range(seg['len']):
            idx = seg['start'] + i
            
            remapped_i = self._remap_pixel_index(i, seg)

            if remapped_i == scan_pos:
                self.pixel_buffer[idx] = (r, g, b)
            else:
                self.pixel_buffer[idx] = (0,0,0)

    def _effect_theater_chase(self, seg):
        now = utime.ticks_ms()
        speed = seg['sx']
        
        cycle_duration = (256 - speed) * 5
        offset = (now // cycle_duration) % 3

        effective_bri = seg['_current_bri']
        factor = effective_bri / 255.0
        intensity = seg['ix'] / 255.0
        
        color = self._get_palette_color(seg['pal'], 0)
        r = int(color[0] * factor * intensity)
        g = int(color[1] * factor * intensity)
        b = int(color[2] * factor * intensity)

        for i in range(seg['len']):
            idx = seg['start'] + i
            
            remapped_i = self._remap_pixel_index(i, seg)

            if (remapped_i % 3) == offset:
                self.pixel_buffer[idx] = (r, g, b)
            else:
                self.pixel_buffer[idx] = (0,0,0)

