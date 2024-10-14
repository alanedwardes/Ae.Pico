import sys
sys.path.insert(0,'../libraries')
sys.path.insert(0,'../shims')

import asyncio
import management

server = management.ManagementServer()

asyncio.run(server.start())