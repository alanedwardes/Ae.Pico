import gc
import sys
import asyncio

def set_global_exception():
    def handle_exception(loop, context):
        sys.print_exception(context["exception"])
        sys.exit()
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)

async def run_component(component):
    while True:
        try:
            await component.start()
        except Exception as e:
            gc.collect()
            sys.print_exception(e)
            await asyncio.sleep(1)
        finally:
            await component.stop()

def start(*components):
    set_global_exception()
    
    try:
        asyncio.run(asyncio.gather(*[run_component(component) for component in components]))
    finally:
        asyncio.new_event_loop()
