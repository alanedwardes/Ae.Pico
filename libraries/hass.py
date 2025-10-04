try:
    import ujson
except ModuleNotFoundError:
    import json as ujson

import asyncio
from httpstream import parse_url

class Hass:
    
    def __init__(self, endpoint, token, keep_alive = False):
        self.uri = parse_url(endpoint)
        self.token = token
        self.keep_alive = keep_alive
        
    def create(provider):
        config = provider['config']['hass']
        return Hass(config['url'], config['token'], config.get('keep_alive', False))

    async def start(self):
        # If enabled, send an HTTP request every 5 minutes
        # Ensures WiFi kept alive, DNS up to date, etc
        while self.keep_alive:
            await asyncio.sleep(300)
            await self.ensure_api_reachable()
        
        await asyncio.Event().wait()
            
    async def ensure_api_reachable(self):
        reader, writer = await asyncio.open_connection(self.uri.hostname, self.uri.port, ssl = self.uri.port == 443)
        self.write_protocol(writer, b'GET', b'/')
        self.write_auth_header(writer)
        writer.write('\r\n')
        await writer.drain()
        await self.ensure_success_status_code(reader)
        content_length = await self.get_content_length(reader)
        print(await reader.readexactly(content_length))
        writer.close()
        await writer.wait_closed()

    async def send_update(self, state, unit, device_class, friendly_name, sensor):
        data = { "state": state, "attributes": {} }

        if friendly_name is not None:
            data['attributes']['friendly_name'] = friendly_name

        if device_class is not None:
            data['attributes']['device_class'] = device_class
        
        if unit is not None:
            data['attributes']['unit_of_measurement'] = unit
            data['attributes']['state_class'] = "measurement"
            
        return await self.post_state(sensor, data)
    
    async def post_state(self, sensor_type, payload):
        reader, writer = await asyncio.open_connection(self.uri.hostname, self.uri.port, ssl = self.uri.port == 443)
        self.write_protocol(writer, b'POST', b'/states/%s' % sensor_type.encode('utf-8'))
        self.write_auth_header(writer)
        self.write_json_content_type_header(writer)
        self.write_content(writer, ujson.dumps(payload).encode('utf-8'))
        await writer.drain()
        await self.ensure_success_status_code(reader)

        content_length = await self.get_content_length(reader)
        content = await reader.readexactly(content_length)
        writer.close()
        await writer.wait_closed()
        
        print(content)
        return content
    
    async def post_event(self, event_type, payload):
        reader, writer = await asyncio.open_connection(self.uri.hostname, self.uri.port, ssl = self.uri.port == 443)
        self.write_protocol(writer, b'POST', b'/events/%s' % event_type.encode('utf-8'))
        self.write_auth_header(writer)
        self.write_json_content_type_header(writer)
        self.write_content(writer, ujson.dumps(payload).encode('utf-8'))
        await writer.drain()
        await self.ensure_success_status_code(reader)

        content_length = await self.get_content_length(reader)
        content = await reader.readexactly(content_length)
        writer.close()
        await writer.wait_closed()
        
        print(content)
        return content
    
    def write_protocol(self, writer, method, path):
        writer.write(b'%s %sapi%s HTTP/1.0\r\n' % (method, self.uri.path.encode('utf-8'), path))
        writer.write(b'Host: %s\r\n' % self.uri.hostname.encode('utf-8'))

    def write_auth_header(self, writer):
        writer.write(b'Authorization: Bearer %s\r\n' % self.token.encode('utf-8'))

    def write_json_content_type_header(self, writer):
        writer.write(b'Content-Type: application/json; charset=utf-8\r\n')

    def write_content(self, writer, content):
        writer.write(b'Content-Length: %i\r\n' % len(content))
        writer.write(b'\r\n')
        writer.write(content)
    
    async def ensure_success_status_code(self, reader):
        line = await reader.readline()
        status = line.split(b' ', 2)
        status_code = int(status[1])
        if not status_code in [200, 201]:
            raise Exception(line)
        
    async def get_content_length(self, reader):
        content_length = None
        while True:
            line = await reader.readline()
            parts = line.lower().split(b'content-length: ', 2)
            if len(parts) > 1:
                content_length = int(parts[1])
            elif line == b'\r\n':
                break
        return content_length
    
    async def render_template(self, template):
        data = { "template": template }

        reader, writer = await asyncio.open_connection(self.uri.hostname, self.uri.port, ssl = self.uri.port == 443)
        self.write_protocol(writer, b'POST', b'/template')
        self.write_auth_header(writer)
        self.write_json_content_type_header(writer)
        self.write_content(writer, ujson.dumps(data).encode('utf-8'))
        await writer.drain()
        await self.ensure_success_status_code(reader)

        content_length = await self.get_content_length(reader)
        content = await reader.readexactly(content_length)
        writer.close()
        await writer.wait_closed()

        return content

    async def set_time(self):
        now = await self.render_template("{{ now().timestamp() | timestamp_custom('%Y,%m,%d,%w,%H,%M,%S,%f') }}")
        ts = tuple(map(int, now.split(',')))
        import machine
        machine.RTC().datetime(ts)
