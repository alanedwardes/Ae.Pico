from machine import Timer
import binascii
import machine
import socket
import utime
import os
import gc

HEADER_TERMINATOR = b'\r\n'

def __parse_headers(connection):
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
    def __init__(self):
        self.init_time = utime.ticks_ms()
    
    def route(self, method, path):
        return method == b'GET' and path == b'/'
    
    def serve(self, headers, connection):
        connection.write(b'HTTP/1.0 200 OK' + HEADER_TERMINATOR)
        connection.write(b'Content-Type: text/html' + HEADER_TERMINATOR)
        connection.write(HEADER_TERMINATOR)
        
        statvfs = os.statvfs("/")
        free_space = statvfs[0] * statvfs[3]
        free_memory = gc.mem_free()
        uptime_ms = utime.ticks_diff(utime.ticks_ms(), self.init_time)
        
        def cpu_temp():
            cpu_sensor = machine.ADC(4)
            adc_value = cpu_sensor.read_u16()
            volt = (3.3/65535) * adc_value
            return 27 - (volt - 0.706)/0.001721
        
        def unique_id():
            unique_id = machine.unique_id()
            return ''.join([f"{b:02x}" for b in unique_id])
        
        def current_time():
            rtc = machine.RTC()
            return rtc.datetime()
        
        KB = 1024
        
        connection.write('<style>body{form{display:inline}</style>')        
        connection.write('<h1>Management Dashboard</h1>')
        connection.write('<p>{}</p>'.format(os.uname()))
        connection.write('<ul>')
        connection.write('<li>Uptime: {:.0f}s</li>'.format(uptime_ms / 1000))
        connection.write('<li>CPU frequency: {:.0f} MHz</li>'.format(machine.freq() / 1_000_000))
        connection.write('<li>CPU temperature: {:.0f} celcius</li>'.format(cpu_temp()))
        connection.write('<li>Unique ID: {}</li>'.format(unique_id()))
        connection.write('<li>Current time: {}</li>'.format(current_time()))
        connection.write('</ul>')
        connection.write('<h2>System</h2>')
        connection.write('<form action="reboot" method="post"><button>Reboot</button/></form>')
        connection.write('<h2>Memory</h2>')
        connection.write('<p>Free Memory: {:.2f} KB</p>'.format(free_memory / KB))
        connection.write('<h2>Filesystem</h2>')
        connection.write('<p>Free Space: {:.2f} KB</p>'.format(free_space / KB))
        connection.write('<h3>Files</h3>')
        connection.write('<table>')
        connection.write('<thead><tr><th>Name</th><th>Size</th><th>Actions</th></tr></thead>')
        connection.write('<tbody>')
        
        def write_file(parent, file):
            path = parent + file[0]
            connection.write('<tr>')
            connection.write('<td>' + path + '</td>')
            connection.write('<td>{:.2f} KB</td>'.format(file[3] / KB))
            connection.write('<td>')
            connection.write('<form action="delete" method="post"><input type="hidden" name="filename" value="' + path + '"/><button>Delete</button/></form>')
            connection.write('<form action="download" method="post"><input type="hidden" name="filename" value="' + path + '"/><button>Download</button/></form>')
            connection.write('</td>')
            connection.write('</tr>')
        
        def list_contents_recursive(start):
            for node in os.ilistdir(start):
                if node[1] == 0x4000:
                    list_contents_recursive(start + node[0] + '/')
                else:
                    write_file(start, node)
        
        list_contents_recursive('')
        
        connection.write('</tbody>')
        connection.write('</table>')
        
        connection.write('<h3>Upload File</h3>')        
        connection.write('<form enctype="multipart/form-data" action="upload" method="post"><input type="file" name="file"/><button>Upload File</button/></form>')

class DeleteController:
    def route(self, method, path):
        return method == b'POST' and path == b'/delete'
    
    def serve(self, headers, connection):
        connection.write(b'HTTP/1.0 200 OK' + HEADER_TERMINATOR)
        connection.write(b'Content-Type: text/html' + HEADER_TERMINATOR)
        connection.write(HEADER_TERMINATOR)
        
        content_length = int(headers.get(b'content-length', '0'))
        filename = connection.read(content_length).split(b'filename=')[1]
        
        try:
            os.unlink(filename)
            connection.write('<p>Deleted "{}"</p>'.format(filename))
        except Exception as e:
            connection.write('<p>Error deleting "{}": {}</p>'.format(filename, e))
            
        connection.write('<p><a href="/">Back</a></p>')
        
class UploadController:    
    def route(self, method, path):
        return method == b'POST' and path == b'/upload'
    
    def serve(self, headers, connection):
        connection.write(b'HTTP/1.0 200 OK' + HEADER_TERMINATOR)
        connection.write(b'Content-Type: text/html' + HEADER_TERMINATOR)
        connection.write(HEADER_TERMINATOR)
        
        content_length = int(headers.get(b'content-length', '0'))
        
        boundary = connection.readline()
        
        (headers_offset, content_headers) = __parse_headers(connection)

        filename = content_headers[b'content-disposition'].split(b'filename=')[1].split(b'"')[1]
        
        offset = headers_offset + len(boundary)

        content_size = content_length - offset - len(boundary) - len(HEADER_TERMINATOR) * 2
        
        with open(filename, 'w') as f:
            f.write(connection.read(content_size))
        
        # After the content there should always be a terminator
        if connection.readline() != HEADER_TERMINATOR:
            raise Exception('Expected newline')
        
        # Read the final boundary
        if connection.readline() != boundary[:len(boundary) - len(HEADER_TERMINATOR)] + b'--\r\n':
            raise Exception('Expected final boundary')

        connection.write('<p>{} uploaded ({} bytes)'.format(filename, content_size))
        connection.write('<p><a href="/">Back</a></p>')

class DownloadController:
    def route(self, method, path):
        return method == b'POST' and path == b'/download'
    
    def serve(self, headers, connection):        
        content_length = int(headers.get(b'content-length', '0'))
        filename = connection.read(content_length).split(b'filename=')[1].decode('utf-8')
        
        connection.write(b'HTTP/1.0 200 OK' + HEADER_TERMINATOR)
        
        try:
            stat = os.stat(filename)
            connection.write(b'Content-Length: {}'.format(stat[6]) + HEADER_TERMINATOR)
            connection.write(b'Content-Type: application/octet-stream' + HEADER_TERMINATOR)
            connection.write(b'Content-Disposition: attachment; filename="{}"'.format(filename) + HEADER_TERMINATOR)
            connection.write(HEADER_TERMINATOR)
            
            with open(filename, 'r') as f:
                connection.write(f.read())
        
        except Exception as e:
            connection.write(b'HTTP/1.0 200 OK' + HEADER_TERMINATOR)
            connection.write(b'Content-Type: text/html' + HEADER_TERMINATOR)
            connection.write(HEADER_TERMINATOR)
            
            connection.write('<p>Error reading "{}": {}</p>'.format(filename, e))
            connection.write('<p><a href="/">Back</a></p>')
            
class RebootController:
    def route(self, method, path):
        return method == b'POST' and path == b'/reboot'
    
    def serve(self, headers, connection):
        connection.write(b'HTTP/1.0 200 OK' + HEADER_TERMINATOR)
        connection.write(HEADER_TERMINATOR)
        machine.reset()

class ManagementServer:   
    def __init__(self, port = 80):
        addr = socket.getaddrinfo('0.0.0.0', port)[0][-1]
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.settimeout(0)
        self.socket.bind(addr)
        self.socket.listen(5)
        self.controllers = [IndexController(), DownloadController(), UploadController(), DeleteController(), RebootController()]
        self.authorization_header = None
    
    def set_credentials(self, username, password):
        encoded = binascii.b2a_base64(('%s:%s' % (username, password)).encode('utf-8'))
        self.authorization_header = b'Basic ' + encoded[:-1]
    
    def update(self):
        try:
            cl, addr = self.socket.accept()
            self.__serve(cl, addr, 2000)
        except OSError as e:
            pass
        
    def __serve(self, connection, addr, timeout):
        gc.collect()
        
        def socket_timeout(t):
            print('Socket timeout after', timeout)
            connection.close()
        
        timer = Timer(period=timeout, mode=Timer.ONE_SHOT, callback=socket_timeout)
        connection.settimeout(None)
        
        try:
            command = connection.readline().split(b' ')
            (offset, headers) = __parse_headers(connection)
            
            # HTTP Basic Authentication
            if self.authorization_header and headers.get(b'authorization', None) != self.authorization_header:
                connection.write(b'HTTP/1.0 401 Unauthorized' + HEADER_TERMINATOR)
                connection.write(b'WWW-Authenticate: Basic realm="Management Server"' + HEADER_TERMINATOR)
                connection.write(HEADER_TERMINATOR)
                connection.write(b'<p>Unauthorized</p>' + HEADER_TERMINATOR)
            else:
                self.__route(command[0], command[1], headers, connection)
            
        except Exception as e:
            print('Error', e)
        
        finally:
            connection.close()
            timer.deinit()
            gc.collect()
        
    def __route(self, method, path, headers, connection):
        for controller in self.controllers:
            if controller.route(method, path):
                controller.serve(headers, connection)
                return
        
        connection.write('404')
