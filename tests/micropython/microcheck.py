import binascii

failures = []

def check(label, cond, detail=''):
    if cond:
        print('PASS', label)
    else:
        print('FAIL', label, detail)
        failures.append(label)

def check_pixels(label, framebuffer, expected):
    crc = binascii.crc32(framebuffer)
    if expected is None:
        print('BASELINE %-24s 0x%08x' % (label, crc))
    else:
        check(label, crc == expected,
              'crc 0x%08x != expected 0x%08x' % (crc, expected))
    check(label + ' drew something',
          framebuffer != bytearray(len(framebuffer)))

def summarize():
    print()
    if failures:
        print('FAILURES:', failures)
        raise SystemExit(1)
    print('ALL CHECKS PASSED')