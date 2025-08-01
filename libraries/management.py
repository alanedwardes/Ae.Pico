import binascii
import network
import machine
import asyncio
from hashlib import sha1
import utime
import os
import gc

HEADER_TERMINATOR = b'\r\n'

MINIMAL_CSS = b'<style>' \
    b'form{display:inline;}' \
    b'body{background-color:Canvas;color:CanvasText;color-scheme:light dark;font-family:sans-serif;}' \
    b'</style>'

BACK_LINK = b'<p><a href="/">Back</a></p>'

ERROR_STATUS = b'HTTP/1.0 500 Internal Server Error' + HEADER_TERMINATOR
OK_STATUS = b'HTTP/1.0 200 OK' + HEADER_TERMINATOR
ACCEPTED_STATUS = b'HTTP/1.0 202 Accepted' + HEADER_TERMINATOR
NOT_FOUND_STATUS = b'HTTP/1.0 404 Not Found' + HEADER_TERMINATOR
UNAUTHORIZED_STATUS = b'HTTP/1.0 401 Unauthorized' + HEADER_TERMINATOR
HTML_HEADER = b'Content-Type: text/html; charset=utf-8' + HEADER_TERMINATOR

def escape(string, quote=True):
    if not string:
        return b''

    if isinstance(string, str):
        string = string.encode('utf-8')
        
    string = string.replace(b'&', b'&amp;').replace(b'<', b'&lt;').replace(b'>', b'&gt;')
         
    if quote:
         string = string.replace(b'"', b'&quot;').replace(b"'", b'&#x27;')
    
    return string

def unquote(string):
    """unquote('abc%20def') -> b'abc def'.

    Note: if the input is a str instance it is encoded as UTF-8.
    This is only an issue if it contains unescaped non-ASCII characters,
    which URIs should not.
    """
    if not string:
        return b''

    if isinstance(string, str):
        string = string.encode('utf-8')

    bits = string.split(b'%')
    if len(bits) == 1:
        return string

    res = bytearray(bits[0])
    append = res.append
    extend = res.extend

    for item in bits[1:]:
        try:
            append(int(item[:2], 16))
            extend(item[2:])
        except KeyError:
            append(b'%')
            extend(item)

    return bytes(res)

def parse_form(form):
    data = {}

    for item in form.split(b'&'):
        if not item:
            continue
        
        item = item.replace(b'+', b' ')
        parts = item.split(b'=')
        key = unquote(parts[0])
        value = unquote(parts[1])
        data[key] = value
    
    return data

async def parse_headers(reader):
    headers = {}
    offset = 0
    
    while True:
        header = await reader.readline()
        offset += len(header)
        if not header or header == HEADER_TERMINATOR:
            break
        
        header_parts = header.split(b':', 1)
        header_name = header_parts[0].lower().strip()
        header_value = header_parts[1][:-len(HEADER_TERMINATOR)].strip()
        headers[header_name] = header_value
        
    return (offset, headers)

async def writechunks(reader, length, destination, chunk_processor = None, chunksize = 512):
    remaining = length
    while remaining > 0:
        chunk = await reader.readexactly(min(chunksize, remaining))
        remaining -= chunksize
        if chunk_processor is not None:
            chunk = chunk_processor(chunk)
        destination.write(chunk)

async def readchunks(writer, length, source, chunk_processor = None, chunksize = 512):
    remaining = length
    while remaining > 0:
        chunk = source.read(min(chunksize, remaining))
        remaining -= chunksize
        if chunk_processor is not None:
            chunk = chunk_processor(chunk)
        writer.write(chunk)
        await writer.drain()

def hashfile(filename, length, chunksize = 512):
    hasher = sha1()
    with open(filename, 'rb') as reader:
        remaining = length
        while remaining > 0:
            chunk = reader.read(min(chunksize, remaining))
            remaining -= chunksize
            hasher.update(chunk)
    return binascii.hexlify(hasher.digest())

class IndexController:
    def route(self, method, path):
        return method == b'GET' and path == b'/'
    
    async def serve(self, method, path, headers, reader, writer):
        started_ticks_ms = utime.ticks_ms()
        statvfs = os.statvfs("/")
        total_space = statvfs[0] * statvfs[2]
        free_space = statvfs[0] * statvfs[3]
        used_space = total_space - free_space
        used_memory = gc.mem_alloc() if hasattr(gc, 'mem_alloc') else 0
        free_memory = gc.mem_free() if hasattr(gc, 'mem_free') else 0
        
        wlan = network.WLAN(network.STA_IF)
        
        ssid = wlan.config('ssid').encode('utf-8')
        rssi = wlan.status('rssi')
        ifconfig = wlan.ifconfig()
        
        def mac_address():
            mac = wlan.config('mac')
            return ':'.join([f"{b:02x}" for b in mac])
        
        def unique_id():
            unique_id = machine.unique_id()
            return ''.join([f"{b:02x}" for b in unique_id])
        
        KB = 1024
        
        uname = os.uname()
        mac = mac_address().encode('utf-8')
        ip = ifconfig[0].encode('utf-8')

        writer.write(OK_STATUS)
        writer.write(HTML_HEADER)
        writer.write(HEADER_TERMINATOR)
        writer.write(MINIMAL_CSS)
        writer.write(b'<h1>Management Dashboard</h1>')
        writer.write(b'<p><b>MicroPython:</b> %s <b>Machine:</b> %s</p>' % (uname[3].encode('utf-8'), uname[4].encode('utf-8')))
        writer.write(b'<p>')
        writer.write(b'<b>Memory</b> <progress max="%i" value="%i" title="Used: %.2f KB, free: %.2f KB"></progress>' % (free_memory + used_memory, used_memory, used_memory / KB, free_memory / KB))
        writer.write(b' <b>Flash</b> <progress max="%i" value="%i" title="Used: %.2f KB, free: %.2f KB"></progress>' % (free_space + used_space, used_space, used_space / KB, free_space / KB))
        writer.write(b' <b>WiFi</b> <progress max="60" value="%i" title="Signal: %i dBm, SSID: %s, Mac: %s, IP: %s"></progress>' % (60 - abs(rssi) + 30, rssi, ssid, mac, ip))
        writer.write(b'</p>')
        writer.write(b'<p><b>CPU:</b> %.0f MHz <b>ID:</b> %s <b>Mac:</b> %s <b>IP:</b> %s</p>' % (machine.freq() / 1_000_000, unique_id().encode('utf-8'), mac, ip))
        writer.write(b'<h2>System</h2>')
        writer.write(b'<form action="reset" method="post"><button>Reset</button></form>')
        writer.write(b' <form onsubmit="this.datetime.value = new Date().toISOString()" action="time" method="post"><input type="hidden" name="datetime" value=""/><button>Set Time from Browser</button></form>')
        writer.write(b' <form action="shell" method="post"><button>Open Shell</button></form>')
        writer.write(b'<h2>Filesystem</h2>')
        writer.write(b'<p>Create file: <form action="new" enctype="multipart/form-data" method="post"><input type="text" name="filename" placeholder="newfile.txt"><button>Create</button></form></p>')
        writer.write(b'<table>')
        writer.write(b'<thead><tr><th>Name</th><th>Size</th><th>Hash</th><th>Actions</th></tr></thead>')
        writer.write(b'<tbody>')
        
        def write_file(parent, node):
            path = parent + node[0]
            size = node[3]
            writer.write(b'<tr>')
            writer.write(b'<td>%s</td>' % (path))
            writer.write(b'<td>%.2f KB</td>' % (size / KB))
            writer.write(b'<td><code>%s</code></td>' % (hashfile(path, size) if node[1] == 0x8000 else b'n/a'))
            writer.write(b'<td>')
            writer.write(b'<form action="delete" method="post"><input type="hidden" name="filename" value="%s"/><button>Delete</button></form>' % (path))
            if node[1] == 0x8000:
                writer.write(b' <form action="edit" enctype="multipart/form-data" method="post"><input type="hidden" name="filename" value="%s"/><button>Edit</button></form>' % (path))
                writer.write(b' <form action="download" method="post"><input type="hidden" name="filename" value="%s"/><button>Download</button></form>' % (path))
            writer.write(b'</td>')
            writer.write(b'</tr>')
        
        def list_contents_recursive(start):
            for node in os.ilistdir(start):
                write_file(start, node)
                if node[1] == 0x4000:
                    list_contents_recursive(start + node[0] + b'/')
        
        list_contents_recursive(b'')
        
        writer.write(b'</tbody>')
        writer.write(b'</table>')
        
        writer.write(b'<h3>Upload File</h3>')        
        writer.write(b'<form enctype="multipart/form-data" action="upload" method="post"><input type="file" name="file"/><button>Upload File</button/></form>')
        
        writer.write(b'<p>Generated in %i ms. System time is %04u-%02u-%02uT%02u:%02u:%02u.</p>' % ((utime.ticks_diff(utime.ticks_ms(), started_ticks_ms),) + utime.localtime()[0:6]))

class EditController:
    def route(self, method, path):
        return path == b'/edit' or path == b'/new'
    
    async def serve(self, method, path, headers, reader, writer):
        filename_disposition = b'Content-Disposition: form-data; name="filename"\r\n'
        body_disposition = b'Content-Disposition: form-data; name="body"\r\n'
        final_trailer = b'--'
        
        remaining = int(headers[b'content-length'])
        boundary_line = await reader.readline()
        remaining -= len(boundary_line)
        assert boundary_line[-len(HEADER_TERMINATOR):] == HEADER_TERMINATOR
        boundary = boundary_line[:-len(HEADER_TERMINATOR)]
        
        assert await reader.readline() == filename_disposition
        remaining -= len(filename_disposition)
        
        assert await reader.readline() == HEADER_TERMINATOR
        remaining -= len(HEADER_TERMINATOR)
        
        filename_line = await reader.readline()
        remaining -= len(filename_line)        
        assert filename_line[-len(HEADER_TERMINATOR):] == HEADER_TERMINATOR        
        filename = filename_line[:-len(HEADER_TERMINATOR)]
        
        mid_boundary = await reader.readline()
        remaining -= len(mid_boundary)
        assert mid_boundary[:len(boundary)] == boundary
        
        mid_boundary_trailer = mid_boundary[len(boundary):-len(HEADER_TERMINATOR)]
        
        if mid_boundary_trailer != final_trailer:
            last_boundary_line = await reader.readline()
            remaining -= len(last_boundary_line)
            assert last_boundary_line == body_disposition
            assert await reader.readline() == HEADER_TERMINATOR
            remaining -= len(HEADER_TERMINATOR)
            
            # b'\r\n-----------------------------333641318729372457933988938254--\r\n'
            trailer_length = len(HEADER_TERMINATOR) + len(boundary) + len(final_trailer) + len(HEADER_TERMINATOR)
            body_length = remaining - trailer_length
            with open(filename, 'wb') as f:
                await writechunks(reader, body_length, f)
            remaining -= body_length
            assert remaining == trailer_length
            await reader.readexactly(remaining)
            
        if path == b'/new':
            with open(filename, 'x') as f:
                pass
        
        with open(filename, 'rb') as f:
            stat = os.stat(filename)
            content_size = stat[6]
            writer.write(OK_STATUS)
            writer.write(HTML_HEADER)
            writer.write(HEADER_TERMINATOR)
            writer.write(MINIMAL_CSS)
            writer.write(b'<h1>Edit</h1>')
            writer.write(b'<form enctype="multipart/form-data" action="edit" method="post">')
            writer.write(b'<input type="hidden" name="filename" value="%s"/>' % filename)
            writer.write(b'<textarea rows="48" cols="128" name="body">')
            await readchunks(writer, content_size, f, escape)
        writer.write(b'</textarea>')
        writer.write(b'<p><input type="submit" value="Submit"/></p>')
        writer.write(b'</form>')
        writer.write(BACK_LINK)

class DeleteController:
    def route(self, method, path):
        return method == b'POST' and path == b'/delete'
    
    async def serve(self, method, path, headers, reader, writer):
        content_length = int(headers.get(b'content-length', '0'))
        form = parse_form(await reader.readexactly(content_length))
        filename = form[b'filename']

        os.unlink(filename)
        writer.write(OK_STATUS)
        writer.write(HTML_HEADER)
        writer.write(HEADER_TERMINATOR)
        writer.write(MINIMAL_CSS)
        writer.write(b'<p>Deleted %s</p>' % (filename))            
        writer.write(BACK_LINK)
        
class TimeController:
    def route(self, method, path):
        return method == b'POST' and path == b'/time'
    
    async def serve(self, method, path, headers, reader, writer):
        content_length = int(headers.get(b'content-length', '0'))
        form = parse_form(await reader.readexactly(content_length))
        form_datetime = form[b'datetime']
        
        parts = form_datetime.split(b'T')
        date = parts[0].split(b'-')
        time = parts[1].split(b':')
        seconds = time[2].split(b'.')
        
        # (year, month, day, weekday, hours, minutes, seconds, subseconds)
        datetime = (int(date[0]), int(date[1]), int(date[2]), 1, int(time[0]), int(time[1]), int(seconds[0]), 0)
        
        machine.RTC().datetime(datetime)

        writer.write(OK_STATUS)
        writer.write(HTML_HEADER)
        writer.write(HEADER_TERMINATOR)
        writer.write(MINIMAL_CSS)
        writer.write(b'<p>Time set %s</p>' % (str(machine.RTC().datetime())))
        writer.write(BACK_LINK)

class ShellController:
    def __init__(self):
        self.clear()
        
    def clear(self):
        self.shell_locals = {}
        self.history = b''
    
    def route(self, method, path):
        return path == b'/shell'
    
    async def serve(self, method, path, headers, reader, writer):
        content_length = int(headers.get(b'content-length', '0'))
        form = parse_form(await reader.readexactly(content_length))
        command = form.get(b'command', '')
        is_eval = form.get(b'eval', '') == b'on'
        
        if b'clear' in form:
            self.clear()
        
        if command:
            self.history += b'>> ' + command + b'\n'
            try:
                if is_eval:
                    self.history += str(eval(command, {}, self.shell_locals)) + '\n'
                else:
                    exec(command, {}, self.shell_locals)
                
            except Exception as e:
                self.history += str(e).encode('utf-8') + b'\n'
        
        writer.write(OK_STATUS)
        writer.write(HTML_HEADER)
        writer.write(HEADER_TERMINATOR)
        writer.write(MINIMAL_CSS)
        writer.write(b'<script>window.onload = () => {')
        writer.write(b'document.getElementById("command").focus();')
        writer.write(b'let h = document.getElementById("history");')
        writer.write(b'h.scrollTop = h.scrollHeight;')
        writer.write(b'}</script>')
        writer.write(b'<pre>Locals: %s</pre>' % escape(str(self.shell_locals)))
        writer.write(b'<form action="shell" method="post">')
        writer.write(b'<p><textarea rows="16" cols="128" readonly id="history" name="history">%s</textarea></p>' % escape(self.history))
        writer.write(b'<p>')
        writer.write(b'<input type="text" id="command" name="command" size="64"/> <input type="checkbox" id="eval" name="eval" %s/>' % (b'checked' if is_eval else b''))
        writer.write(b' <label for="eval">Statement</label>')
        writer.write(b' <input type="submit" value="Execute"/>')
        writer.write(b' <input type="submit" name="clear" value="Reset"/>')
        writer.write(b'</p>')
        writer.write(b'</form>')
        writer.write(BACK_LINK)

class GPIOController:
    def route(self, method, path):
        return path.startswith(b'/gpio')
    
    def _write_pin_status(self, pin, writer):
        writer.write(OK_STATUS)
        writer.write(HEADER_TERMINATOR)
        writer.write(b'ON' if pin.value() else b'OFF')
    
    def _out(self, path, body, writer):
        pin_number = int(path.split(b'/gpio/out/')[1])
        pin = machine.Pin(pin_number, machine.Pin.OUT)
        
        if body:
            pin.value(body == b'ON')

        self._write_pin_status(pin, writer)
    
    def _in(self, path, writer):
        pin_number = int(path.split(b'/gpio/in/')[1])
        pin = machine.Pin(pin_number, machine.Pin.IN)
        self._write_pin_status(pin, writer)
    
    async def serve(self, method, path, headers, reader, writer):
        content_length = int(headers.get(b'content-length', '0'))
        body = await reader.readexactly(content_length)

        if path.startswith(b'/gpio/out'):
            self._out(path, body, writer)
        elif path.startswith(b'/gpio/in'):
            self._in(path, writer)

class PWMController:
    def route(self, method, path):
        return path.startswith(b'/pwm')
    
    async def serve(self, method, path, headers, reader, writer):
        content_length = int(headers.get(b'content-length', '0'))
        body = await reader.readexactly(content_length)
        pin_number = int(path.split(b'/pwm/')[1])
        pwm = machine.PWM(pin_number)
        DUTY_MAX = float(65535)

        if body:
            form = parse_form(body)
            freq = int(form.get(b'frequency', 5_000))
            duty_u16 = int(DUTY_MAX * float(form.get(b'duty', 50)) / 100)
            pwm.deinit() if freq < 8 else pwm.init(freq=freq, duty_u16=duty_u16)
            writer.write(ACCEPTED_STATUS)
        else:
            writer.write(OK_STATUS)
        
        writer.write(HEADER_TERMINATOR)
        writer.write('frequency=%iHz,duty=%i%%' % (pwm.freq(), pwm.duty_u16() / DUTY_MAX * 100))

class UploadController:    
    def route(self, method, path):
        return method == b'POST' and path == b'/upload'
    
    async def serve(self, method, path, headers, reader, writer):
        content_length = int(headers.get(b'content-length', '0'))   
        boundary = await reader.readline()        
        (headers_offset, content_headers) = await parse_headers(reader)
        filename = content_headers[b'content-disposition'].split(b'filename=')[1].split(b'"')[1]
        offset = headers_offset + len(boundary)
        content_size = content_length - offset - len(boundary) - len(HEADER_TERMINATOR) * 2
        
        with open(filename, 'wb') as f:
            await writechunks(reader, content_size, f)
        
        # After the content there should always be a terminator
        if (await reader.readline()) != HEADER_TERMINATOR:
            raise Exception('Expected newline')
        
        # Read the final boundary
        if (await reader.readline()) != boundary[:len(boundary) - len(HEADER_TERMINATOR)] + b'--\r\n':
            raise Exception('Expected final boundary')

        writer.write(OK_STATUS)
        writer.write(HTML_HEADER)
        writer.write(HEADER_TERMINATOR)
        writer.write(MINIMAL_CSS)
        writer.write(b'<p>%s uploaded (%i bytes)' % (filename, content_size))
        writer.write(BACK_LINK)

class DownloadController:
    def route(self, method, path):
        return method == b'POST' and path == b'/download'
    
    async def serve(self, method, path, headers, reader, writer):        
        content_length = int(headers.get(b'content-length', '0'))
        form = parse_form(await reader.readexactly(content_length))
        filename = form[b'filename']
        
        with open(filename, 'rb') as f:
            stat = os.stat(filename)
            content_size = stat[6]
            writer.write(OK_STATUS)
            writer.write(b'Content-Length: %i' % (content_size) + HEADER_TERMINATOR)
            writer.write(b'Content-Type: application/octet-stream' + HEADER_TERMINATOR)
            writer.write(b'Content-Disposition: attachment; filename="%s"' % (filename) + HEADER_TERMINATOR)
            writer.write(HEADER_TERMINATOR)
            await readchunks(writer, content_size, f)
            
class ResetController:
    def route(self, method, path):
        return method == b'POST' and path == b'/reset'
    
    async def serve(self, method, path, headers, reader, writer):
        content_length = int(headers.get(b'content-length', '0'))
        form = parse_form(await reader.readexactly(content_length))
        
        writer.write(OK_STATUS)
        writer.write(HTML_HEADER)
        writer.write(HEADER_TERMINATOR)
        writer.write(MINIMAL_CSS)
        
        if b'type' in form:
            is_hard = form[b'type'] == b'hard'
            writer.write(b'<h1>%s Reset</h1>' % (b'Hard' if is_hard else b'Soft'))
            writer.write(b'<p>System will reset in 5 seconds.</p>')
            writer.write(BACK_LINK)
            writer.close()
            await writer.wait_closed()
            await asyncio.sleep(5)
            if is_hard:
                machine.reset()
            else:
                machine.soft_reset()
        else:
            writer.write(b'<h1>Reset</h1>')
            writer.write(b'<form action="reset" method="post">')
            writer.write(b'<label for="type">Reset type:</label>')
            writer.write(b'<select name="type" id="type">')
            writer.write(b'<option value="soft">Soft</option>')
            writer.write(b'<option value="hard">Hard</option>')
            writer.write(b'</select>')
            writer.write(b'<input type="submit"/>')
            writer.write(b'</form>')

class ManagementServer:   
    def __init__(self, port = 80):
        self.port = port
        self.controllers = [IndexController(), EditController(), DownloadController(),
                            UploadController(), DeleteController(), ResetController(),
                            TimeController(), ShellController(),
                            GPIOController(), PWMController()]
        self.authorization_header = None
        self.server = None
    
    def set_credentials(self, username, password):
        encoded = binascii.b2a_base64(('%s:%s' % (username, password)).encode('utf-8'))
        self.authorization_header = b'Basic ' + encoded[:-1]
        
    def create(provider):
        config = provider['config'].get('management', {})
        return ManagementServer(config.get('port', 80))
    
    async def start(self):
        try:
            self.server = await asyncio.start_server(self.__serve, '0.0.0.0', self.port)
            await asyncio.Event().wait()
        finally:
            await self.stop()
        
    async def stop(self):
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
    
    async def __serve(self, reader, writer):
        try:
            requestline = (await reader.readline()).split(b' ')
            if len(requestline) != 3:
                # Malformed request line
                return
            
            (offset, headers) = await parse_headers(reader)
            
            # HTTP Basic Authentication
            if self.authorization_header and headers.get(b'authorization', None) != self.authorization_header:
                writer.write(UNAUTHORIZED_STATUS)
                writer.write(b'WWW-Authenticate: Basic realm="Management Server"' + HEADER_TERMINATOR)
                writer.write(HTML_HEADER)
                writer.write(HEADER_TERMINATOR)
                writer.write(MINIMAL_CSS)
                writer.write(b'<p>Unauthorized</p>' + HEADER_TERMINATOR)
            else:
                await self.__route(requestline[0], requestline[1], headers, reader, writer)
        except Exception as e:
            writer.write(ERROR_STATUS)
            writer.write(HTML_HEADER)
            writer.write(HEADER_TERMINATOR)
            writer.write(MINIMAL_CSS)
            writer.write(b'<p>Unhandled Exception: %s</p>' % type(e).__name__.encode('utf-8'))
            writer.write(b'<pre>%s</pre>' % str(e).encode('utf-8'))
            writer.write(BACK_LINK)
            raise
        finally:
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            gc.collect()
        
    async def __route(self, method, path, headers, reader, writer):
        for controller in self.controllers:
            if controller.route(method, path):
                await controller.serve(method, path, headers, reader, writer)
                return
        
        writer.write(NOT_FOUND_STATUS)
        writer.write(HTML_HEADER)
        writer.write(HEADER_TERMINATOR)
        writer.write(MINIMAL_CSS)
        writer.write(b'<p>Not found</p>')
        writer.write(BACK_LINK)
