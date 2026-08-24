import io

def load_bytes(path):
    with open(path, 'rb') as f:
        return io.BytesIO(f.read())

def stage(path):
    staged = '/tmp/aepico-' + path.replace('/', '_')
    with open(path, 'rb') as src, open(staged, 'wb') as dst:
        dst.write(src.read())
    return staged

def preload_fonts(names):
    from bmfont import BMFont
    import textbox
    for name in names:
        textbox._BM_FONT_CACHE[name] = (
            BMFont.load(stage('fonts/%s.fnt' % name)),
            [load_bytes('fonts/%s_0.bin' % name)])