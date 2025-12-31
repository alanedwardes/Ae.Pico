import psutil
process = psutil.Process()

def _mem_alloc():
    return process.memory_info().rss

import gc
gc.mem_alloc = _mem_alloc