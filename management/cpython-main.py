import sys
sys.path.insert(0,'../libraries')
sys.path.insert(0,'../shims')

import asyncio
import management

server = management.ManagementServer()

async def main():
    await server.start()
    await asyncio.Future()

asyncio.run(main())