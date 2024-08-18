import os

def statvfs(path):
    return (0,0,0,0,0,0)

def uname():
    return 'cypython'

def ilistdir(path):
    with os.scandir(b'./' + path) as it:
        for entry in it:
            stat = entry.stat()
            yield (entry.name, 0x4000 if entry.is_dir() else 0, None, stat.st_size)

def stat(path):
    stat = os.stat(path)
    return (None, None, None, None, None, None, stat.st_size)

def unlink(path):
    os.unlink(path)
