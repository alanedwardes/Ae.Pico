# Requires connectivity.py with the following variables:
# ssid = 'your_ssid'
# key = 'your_password'
# hostname = 'your_hostname' (optional)

import sys
import asyncio
import webrepl
import network

def save_exception(file_name, exception):
    with open(file_name, 'w') as file:
        sys.print_exception(exception, file)

async def start_application(nic):
    try:
        import config
        from servicefactory import ServiceFactory

        provider = {'nic': nic, 'config': config.config}
        factory = ServiceFactory(provider)
        
        await factory.run_components_forever()
    except Exception as e:
        save_exception('application.log', e)

async def start():
    nic = network.WLAN(network.STA_IF)
    nic.active(True)
    
    import connectivity
    
    webrepl.start(getattr(connectivity, 'repl_port', 8266), getattr(connectivity, 'repl_password', ''))
    
    if hasattr(connectivity, 'hostname'):
        nic.config(hostname = connectivity.hostname)
    
    async def connect_wifi():
        while True:
            if not nic.isconnected():
                nic.disconnect()
                nic.connect(connectivity.ssid, connectivity.key)
            await asyncio.sleep(30)
            
    await asyncio.gather(connect_wifi(), start_application(nic))

def handle_async_exception(loop, context):
    save_exception('asyncio.log', context["exception"])

loop = asyncio.get_event_loop()
loop.set_exception_handler(handle_async_exception)

try:
    asyncio.run(start())
except Exception as e:
    save_exception('unhandled.log', e)
finally:
    asyncio.new_event_loop()
