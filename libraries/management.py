import binascii
import network
import machine
import socket
import utime
import uos
import gc

HEADER_TERMINATOR = b'\r\n'

MINIMAL_CSS = b'<style>' \
    b'form{display:inline;}' \
    b'body{background-color:Canvas;color:CanvasText;color-scheme:light dark;font-family:sans-serif;}' \
    b'</style>'

BACK_LINK = b'<p><a href="/">Back</a></p>'

ERROR_STATUS = b'HTTP/1.0 500 Internal Server Error' + HEADER_TERMINATOR
OK_STATUS = b'HTTP/1.0 200 OK' + HEADER_TERMINATOR
NOT_FOUND_STATUS = b'HTTP/1.0 404 Not Found' + HEADER_TERMINATOR
UNAUTHORIZED_STATUS = b'HTTP/1.0 401 Unauthorized' + HEADER_TERMINATOR
HTML_HEADER = b'Content-Type: text/html; charset=utf-8' + HEADER_TERMINATOR

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

def parse_headers(connection):
    headers = {}
    offset = 0
    
    while True:
        header = connection.readline()
        offset += len(header)
        if not header or header == HEADER_TERMINATOR:
            break
        
        header_parts = header.split(b':', 1)
        header_name = header_parts[0].lower().strip()
        header_value = header_parts[1][:-len(HEADER_TERMINATOR)].strip()
        headers[header_name] = header_value
        
    return (offset, headers)

class IndexController:
    def route(self, method, path):
        return method == b'GET' and path == b'/'
    
    def serve(self, headers, connection):
        started_ticks_ms = utime.ticks_ms()
        statvfs = uos.statvfs("/")
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
        
        uname = uos.uname()
        mac = mac_address().encode('utf-8')
        ip = ifconfig[0].encode('utf-8')

        connection.write(OK_STATUS)
        connection.write(HTML_HEADER)
        connection.write(HEADER_TERMINATOR)
        connection.write(MINIMAL_CSS)
        connection.write(b'<h1>Management Dashboard</h1>')
        connection.write(b'<p><b>MicroPython:</b> %s <b>Machine:</b> %s</p>' % (uname[3].encode('utf-8'), uname[4].encode('utf-8')))
        connection.write(b'<p>')
        connection.write(b'<b>Memory</b> <progress max="%i" value="%i" title="Used: %.2f KB, free: %.2f KB"></progress>' % (free_memory + used_memory, used_memory, used_memory / KB, free_memory / KB))
        connection.write(b' <b>Flash</b> <progress max="%i" value="%i" title="Used: %.2f KB, free: %.2f KB"></progress>' % (free_space + used_space, used_space, used_space / KB, free_space / KB))
        connection.write(b' <b>WiFi</b> <progress max="60" value="%i" title="Signal: %i dBm, SSID: %s, Mac: %s, IP: %s"></progress>' % (60 - abs(rssi) + 30, rssi, ssid, mac, ip))
        connection.write(b'</p>')
        connection.write(b'<p><b>CPU:</b> %.0f MHz <b>ID:</b> %s <b>Mac:</b> %s <b>IP:</b> %s</p>' % (machine.freq() / 1_000_000, unique_id().encode('utf-8'), mac, ip))
        connection.write(b'<h2>System</h2>')
        connection.write(b'<form action="reboot" method="post"><button>Reboot Now</button></form>')
        connection.write(b' <form onsubmit="this.datetime.value = new Date().toISOString()" action="time" method="post"><input type="hidden" name="datetime" value=""/><button>Set Time from Browser</button></form>')
        connection.write(b' <form action="shell" method="post"><button>Open Shell</button></form>')
        connection.write(b'<h2>Filesystem</h2>')
        connection.write(b'<table>')
        connection.write(b'<thead><tr><th>Name</th><th>Size</th><th>Actions</th></tr></thead>')
        connection.write(b'<tbody>')
        
        def write_file(parent, node):
            path = parent + node[0]
            connection.write(b'<tr>')
            connection.write(b'<td>%s</td>' % (path))
            connection.write(b'<td>%.2f KB</td>' % (node[3] / KB))
            connection.write(b'<td>')
            connection.write(b'<form action="delete" method="post"><input type="hidden" name="filename" value="%s"/><button>Delete</button></form>' % (path))
            if node[1] == 0x8000:
                connection.write(b' <form action="download" method="post"><input type="hidden" name="filename" value="%s"/><button>Download</button></form>' % (path))
            connection.write(b'</td>')
            connection.write(b'</tr>')
        
        def list_contents_recursive(start):
            for node in uos.ilistdir(start):
                write_file(start, node)
                if node[1] == 0x4000:
                    list_contents_recursive(start + node[0] + b'/')
        
        list_contents_recursive(b'')
        
        connection.write(b'</tbody>')
        connection.write(b'</table>')
        
        connection.write(b'<h3>Upload File</h3>')        
        connection.write(b'<form enctype="multipart/form-data" action="upload" method="post"><input type="file" name="file"/><button>Upload File</button/></form>')
        
        connection.write(b'<p>Generated in %i ms. System time is %04u-%02u-%02uT%02u:%02u:%02u.</p>' % ((utime.ticks_diff(utime.ticks_ms(), started_ticks_ms),) + utime.localtime()[0:6]))

class DeleteController:
    def route(self, method, path):
        return method == b'POST' and path == b'/delete'
    
    def serve(self, headers, connection):
        content_length = int(headers.get(b'content-length', '0'))
        form = parse_form(connection.read(content_length))
        filename = form[b'filename']

        uos.unlink(filename)
        connection.write(OK_STATUS)
        connection.write(HTML_HEADER)
        connection.write(HEADER_TERMINATOR)
        connection.write(MINIMAL_CSS)
        connection.write(b'<p>Deleted %s</p>' % (filename))            
        connection.write(BACK_LINK)
        
class TimeController:
    def route(self, method, path):
        return method == b'POST' and path == b'/time'
    
    def serve(self, headers, connection):
        content_length = int(headers.get(b'content-length', '0'))
        form = parse_form(connection.read(content_length))
        form_datetime = form[b'datetime']
        
        parts = form_datetime.split(b'T')
        date = parts[0].split(b'-')
        time = parts[1].split(b':')
        seconds = time[2].split(b'.')
        
        # (year, month, day, weekday, hours, minutes, seconds, subseconds)
        datetime = (int(date[0]), int(date[1]), int(date[2]), 1, int(time[0]), int(time[1]), int(seconds[0]), 0)
        
        machine.RTC().datetime(datetime)

        connection.write(OK_STATUS)
        connection.write(HTML_HEADER)
        connection.write(HEADER_TERMINATOR)
        connection.write(MINIMAL_CSS)
        connection.write(b'<p>Time set %s</p>' % (str(machine.RTC().datetime())))
        connection.write(BACK_LINK)

class ShellController:
    def __init__(self):
        self.shell_locals = {}
    
    def route(self, method, path):
        return method == b'POST' and path == b'/shell'
    
    def serve(self, headers, connection):
        content_length = int(headers.get(b'content-length', '0'))
        form = parse_form(connection.read(content_length))
        history = form.get(b'history', '')
        command = form.get(b'command', '')
        is_eval = form.get(b'eval', '') == b'on'
        
        if command:
            history += b'>> ' + command + b'\n'
            try:
                if is_eval:
                    history += str(eval(command, {}, self.shell_locals)) + '\n'
                else:
                    exec(command, {}, self.shell_locals)
                
            except Exception as e:
                history += str(e) + '\n'
        
        connection.write(OK_STATUS)
        connection.write(HTML_HEADER)
        connection.write(HEADER_TERMINATOR)
        connection.write(MINIMAL_CSS)
        connection.write(b'<script>window.onload = () => {');
        connection.write(b'document.getElementById("command").focus();');
        connection.write(b'let h = document.getElementById("history");');
        connection.write(b'h.scrollTop = h.scrollHeight;');
        connection.write(b'}</script>');
        connection.write(b'<pre>Locals: %s</pre>' % str(self.shell_locals));
        connection.write(b'<form action="shell" method="post">')
        connection.write(b'<p><textarea rows="16" cols="128" readonly id="history" name="history">%s</textarea></p>' % history)
        connection.write(b'<p><input type="text" id="command" name="command"/> <input type="checkbox" id="eval" name="eval" %s/> <label for="eval">Statement</label></p>' % ('checked' if is_eval else ''))
        connection.write(b'<p><input type="submit"/></p>')
        connection.write(b'</form>')
        connection.write(BACK_LINK)

class UploadController:    
    def route(self, method, path):
        return method == b'POST' and path == b'/upload'
    
    def serve(self, headers, connection):
        content_length = int(headers.get(b'content-length', '0'))        
        boundary = connection.readline()        
        (headers_offset, content_headers) = parse_headers(connection)
        filename = content_headers[b'content-disposition'].split(b'filename=')[1].split(b'"')[1]        
        offset = headers_offset + len(boundary)
        content_size = content_length - offset - len(boundary) - len(HEADER_TERMINATOR) * 2
        
        with open(filename, 'wb') as f:
            f.write(connection.read(content_size))
        
        # After the content there should always be a terminator
        if connection.readline() != HEADER_TERMINATOR:
            raise Exception('Expected newline')
        
        # Read the final boundary
        if connection.readline() != boundary[:len(boundary) - len(HEADER_TERMINATOR)] + b'--\r\n':
            raise Exception('Expected final boundary')

        connection.write(OK_STATUS)
        connection.write(HTML_HEADER)
        connection.write(HEADER_TERMINATOR)
        connection.write(MINIMAL_CSS)
        connection.write(b'<p>%s uploaded (%i bytes)' % (filename, content_size))
        connection.write(BACK_LINK)

class DownloadController:
    def route(self, method, path):
        return method == b'POST' and path == b'/download'
    
    def serve(self, headers, connection):        
        content_length = int(headers.get(b'content-length', '0'))
        form = parse_form(connection.read(content_length))
        filename = form[b'filename']
        
        with open(filename, 'rb') as f:
            stat = uos.stat(filename)
            connection.write(OK_STATUS)
            connection.write(b'Content-Length: %i' % (stat[6]) + HEADER_TERMINATOR)
            connection.write(b'Content-Type: application/octet-stream' + HEADER_TERMINATOR)
            connection.write(b'Content-Disposition: attachment; filename="%s"' % (filename) + HEADER_TERMINATOR)
            connection.write(HEADER_TERMINATOR)
            connection.write(f.read())
            
class RebootController:
    def route(self, method, path):
        return method == b'POST' and path == b'/reboot'
    
    def serve(self, headers, connection):
        connection.write(OK_STATUS)
        connection.write(HTML_HEADER)
        connection.write(HEADER_TERMINATOR)
        connection.write(MINIMAL_CSS)
        connection.write(b'<p>System will reboot in 5 seconds.</p>')
        connection.write(BACK_LINK)
        connection.close()
        utime.sleep(5)
        machine.reset()

class ManagementServer:   
    def __init__(self, port = 80):
        addr = socket.getaddrinfo('0.0.0.0', port)[0][-1]
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setblocking(False)
        self.socket.bind(addr)
        self.socket.listen(5)
        self.controllers = [IndexController(), DownloadController(), UploadController(),
                            DeleteController(), RebootController(), TimeController(),
                            ShellController()]
        self.authorization_header = None
    
    def set_credentials(self, username, password):
        encoded = binascii.b2a_base64(('%s:%s' % (username, password)).encode('utf-8'))
        self.authorization_header = b'Basic ' + encoded[:-1]
    
    def update(self):
        try:
            connection, addr = self.socket.accept()
            connection.settimeout(2)
            self.__serve(connection.makefile('rwb'), addr)
        except OSError:
            pass
        
    def __serve(self, connection, addr):
        gc.collect()
        
        try:
            command = connection.readline().split(b' ')
            (offset, headers) = parse_headers(connection)
            
            # HTTP Basic Authentication
            if self.authorization_header and headers.get(b'authorization', None) != self.authorization_header:
                connection.write(UNAUTHORIZED_STATUS)
                connection.write(b'WWW-Authenticate: Basic realm="Management Server"' + HEADER_TERMINATOR)
                connection.write(HTML_HEADER)
                connection.write(HEADER_TERMINATOR)
                connection.write(MINIMAL_CSS)
                connection.write(b'<p>Unauthorized</p>' + HEADER_TERMINATOR)
            else:
                self.__route(command[0], command[1], headers, connection)
            
        except Exception as e:
            connection.write(ERROR_STATUS)
            connection.write(HTML_HEADER)
            connection.write(HEADER_TERMINATOR)
            connection.write(MINIMAL_CSS)
            connection.write(b'<p>Unhandled Exception: %s</p>' % type(e).__name__.encode('utf-8'))
            connection.write(b'<pre>%s</pre>' % str(e).encode('utf-8'))
            connection.write(BACK_LINK)
        
        finally:
            connection.close()
            gc.collect()
        
    def __route(self, method, path, headers, connection):
        for controller in self.controllers:
            if controller.route(method, path):
                controller.serve(headers, connection)
                return
        
        connection.write(NOT_FOUND_STATUS)
        connection.write(HTML_HEADER)
        connection.write(HEADER_TERMINATOR)
        connection.write(MINIMAL_CSS)
        connection.write(b'<p>Not found</p>')
        connection.write(BACK_LINK)
