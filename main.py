# Requires connectivity.py with the following variables:
# ssid = 'your_ssid'
# key = 'your_password'
# hostname = 'your_hostname' (optional)

import sys
import asyncio
import webrepl
import network

def save_exception(file_name, exception):
    print("Exception %s: %s" % (exception.__class__.__name__, str(exception)))
    
    try:
        with open(file_name, 'w') as file:
            sys.print_exception(exception, file)
    except:
        print('Unable to write exception to flash')

def handle_factory_exception(exception):
    save_exception('factory.log', exception)
    
def handle_async_exception(loop, context):
    save_exception('asyncio.log', context["exception"])

async def start_application(nic):
    try:
        import config
        from servicefactory import ServiceFactory

        provider = {'nic': nic, 'config': config.config}
        factory = ServiceFactory(provider, handle_factory_exception)
        await factory.run_components_forever()
    except Exception as e:
        save_exception('application.log', e)
    finally:
        print('Application exit')

async def start():
    nic = network.WLAN(network.STA_IF)
    nic.active(True)
    led = None
    
    # Best-effort status LED; ignore failures on hosts without LED access
    try:
        import machine
        led = machine.Pin("LED", machine.Pin.OUT)
        led.value(0)
    except Exception:
        pass
    
    import connectivity
    
    webrepl.start(getattr(connectivity, 'repl_port', 8266), getattr(connectivity, 'repl_password', ''))
    
    if hasattr(connectivity, 'hostname'):
        nic.config(hostname = connectivity.hostname)

    while not nic.isconnected():
        print(f'connecting to {connectivity.ssid}')
        nic.connect(connectivity.ssid, connectivity.key)
        led_state = False
        for _ in range(30):
            if nic.isconnected():
                break
            led_state = not led_state
            if led:
                led.value(led_state)
            await asyncio.sleep(0.1)
    
    print(f'connected to %s with IP %s' % (connectivity.ssid, nic.ifconfig()[0]))
    if led:
        led.value(0)
    
    async def connect_wifi():
        while True:
            if not nic.isconnected():
                nic.disconnect()
                nic.connect(connectivity.ssid, connectivity.key)
            await asyncio.sleep(30)
            
    await asyncio.gather(connect_wifi(), start_application(nic))

loop = asyncio.get_event_loop()
loop.set_exception_handler(handle_async_exception)

try:
    asyncio.run(start())
except Exception as e:
    save_exception('unhandled.log', e)
    raise
finally:
    asyncio.new_event_loop()
