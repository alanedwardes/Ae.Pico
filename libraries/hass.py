try:
    import ujson
except ModuleNotFoundError:
    import json as ujson

import re
import asyncio
from collections import namedtuple

URL_RE = re.compile(r'(http|https)://([A-Za-z0-9-\.]+)(?:\:([0-9]+))?(.+)?')
URI = namedtuple('URI', ('hostname', 'port', 'path'))

def urlparse(uri):
    match = URL_RE.match(uri)
    if match:
        protocol = match.group(1)
        host = match.group(2)
        port = match.group(3)
        path = match.group(4)

        if protocol == 'https':
            if port is None:
                port = 443
        elif protocol == 'http':
            if port is None:
                port = 80
        else:
            raise ValueError('Scheme {} is invalid'.format(protocol))

        return URI(host.encode('ascii'), int(port), path.encode('utf-8'))

class Hass:
    
    def __init__(self, endpoint, token):
        self.uri = urlparse(endpoint)
        self.token = token

    async def send_update(self, state, unit, device_class, friendly_name, sensor):
        data = { "state": state, "attributes": {} }

        if friendly_name is not None:
            data['attributes']['friendly_name'] = friendly_name

        if device_class is not None:
            data['attributes']['device_class'] = device_class
        
        if unit is not None:
            data['attributes']['unit_of_measurement'] = unit
            data['attributes']['state_class'] = "measurement"

        reader, writer = await asyncio.open_connection(self.uri.hostname, self.uri.port, ssl = self.uri.port == 443)
        writer.write(b'POST %s%s%s HTTP/1.0\r\n' % (self.uri.path, b'api/states/', sensor.encode('utf-8')))
        writer.write(b'Host: %s\r\n' % self.uri.hostname)
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
        writer.write(b'POST %s%s HTTP/1.0\r\n' % (self.uri.path, b'api/template'))
        writer.write(b'Host: %s\r\n' % self.uri.hostname)
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
