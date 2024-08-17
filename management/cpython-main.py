import sys
sys.path.insert(0,'../libraries')
sys.path.insert(0,'../shims')

import time
import management

server = management.ManagementServer()

while True:
    server.update()
    time.sleep(0.01)
