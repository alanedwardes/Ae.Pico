import config
import asyncio
from network import WLAN, STA_IF
from servicefactory import ServiceFactory

provider = {'nic': WLAN(STA_IF), 'config': config.config}

factory = ServiceFactory(provider)

try:
    asyncio.run(factory.run_components_forever())
finally:
    asyncio.new_event_loop()