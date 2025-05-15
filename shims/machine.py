import datetime

def freq():
    return 0

def unique_id():
    return b'\xe6c8a\xa3x/,'

def reset():
    pass

class ADC():
    def __init__(self, pin):
        pass

    def read_u16(self):
        return 0

class RTC:
    ts = None

    def datetime(self, *args):
        if len(args) == 1:
            RTC.ts = args[0]

        now = datetime.datetime.now()
        return (now.year, now.month, now.day, now.weekday(), now.hour, now.minute, now.second, 0)
