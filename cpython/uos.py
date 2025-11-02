import os

def statvfs(path):
    return (4096, 4096, 212, 196, 196, 0, 0, 0, 0, 255)

def uname():
    return ('rp2', 'rp2', '1.21.0', 'v1.21.0 on 2023-10-06 (GNU 13.2.0 MinSizeRel)', 'Raspberry Pi Pico W with RP2040')

def ilistdir(path):
    with os.scandir(b'./' + path) as it:
        for entry in it:
            stat = entry.stat()
            yield (entry.name, 0x4000 if entry.is_dir() else 0x8000, None, stat.st_size)

def stat(path):
    stat = os.stat(path)
    return (None, None, None, None, None, None, stat.st_size)

def unlink(path):
    os.unlink(path)
