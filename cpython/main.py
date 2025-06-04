import sys
sys.path.insert(1, '../libraries')
sys.path.insert(1, '../infodisplay')

import config
import asyncio
from servicefactory import ServiceFactory

provider = {'config': config.config}

factory = ServiceFactory(provider)

try:
    asyncio.run(factory.run_components_forever())
finally:
    asyncio.new_event_loop()
