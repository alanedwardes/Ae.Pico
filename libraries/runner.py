import io
import gc
import sys
import utime
import asyncio
from collections import deque

class ExceptionController:
    def __init__(self):
        self.exceptions = deque([], 10)
    
    def __htmlencode(self, text):
        return text.replace(b'>', b'&lt;').replace(b'<', b'&gt;')
    
    def route(self, method, path):
        return method == b'GET' and path == b'/exceptions'
    
    async def serve(self, method, path, headers, reader, writer):
        writer.write(b'<h1>Exceptions</h1>')
        writer.write(b'<p>System time is %04u-%02u-%02uT%02u:%02u:%02u.</p>' % utime.localtime()[:6])
        for timestamp, name, exception in self.exceptions:
            writer.write(b'<h2>%s on %04u-%02u-%02uT%02u:%02u:%02u</h2>' % ((self.__htmlencode(name),) + timestamp[:6]))
            writer.write(b'<pre>')
            writer.write(self.__htmlencode(exception))
            writer.write(b'</pre>')
        await writer.drain()
        
    def handle_exception(self, exception):
        with io.StringIO() as stream:
            sys.print_exception(exception, stream)
            self.exceptions.appendleft((utime.localtime(), type(exception).__name__.encode('utf-8'), stream.getvalue().encode('utf-8')))

    def loop_handle_exception(self, loop, context):
        self.handle_exception(context["exception"])

class Runner:
    def set_exception_controller(self, exception_controller):
        self.exception_controller = exception_controller
        
    def __invoke_exception_controller(self, exception):
        sys.print_exception(exception)
        if self.exception_controller is None:
            return
        
        try:
            self.exception_controller.handle_exception(exception)
        except:
            pass
    
    async def run_component(self, component):        
        while True:
            try:
                await component.start()
            except Exception as e:
                self.__invoke_exception_controller(e)
                await asyncio.sleep(1)
            finally:
                await component.stop()
            gc.collect()

    async def run_components(self, *components):
        await asyncio.gather(*[self.run_component(component) for component in components])
