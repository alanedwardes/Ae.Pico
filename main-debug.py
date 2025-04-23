import sys
import config
import asyncio
import time
from network import WLAN, STA_IF
from servicefactory import ServiceFactory

provider = {'nic': WLAN(STA_IF), 'config': config.config}

def save_exception(exception):
    with open('exceptions.log', 'a+') as f:
        f.write(f'{time.time()}: ')
        sys.print_exception(exception, f)

def set_global_exception():
    def handle_exception(loop, context):
        save_exception(context["exception"])
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)
set_global_exception()

try:
    factory = ServiceFactory(provider)
    asyncio.run(factory.run_components_forever())
except Exception as e:
    save_exception(e)
    raise
finally:
    asyncio.new_event_loop()
