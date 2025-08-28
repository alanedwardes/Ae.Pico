import sys
sys.path.insert(1, '../libraries')
sys.path.insert(1, '../infodisplay')

import config
import asyncio
import traceback
from servicefactory import ServiceFactory

provider = {'config': config.config}

def handle_factory_exception(e):
    traceback.print_exception(type(e), e, e.__traceback__)

factory = ServiceFactory(provider, handle_factory_exception)

try:
    asyncio.run(factory.run_components_forever())
finally:
    asyncio.new_event_loop()
