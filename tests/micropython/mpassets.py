import io

def load_bytes(path):
    with open(path, 'rb') as f:
        return io.BytesIO(f.read())

def stage(path):
    staged = '/tmp/aepico-' + path.replace('/', '_')
    with open(path, 'rb') as src, open(staged, 'wb') as dst:
        dst.write(src.read())
    return staged