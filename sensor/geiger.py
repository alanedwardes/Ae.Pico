from machine import Pin

class Geiger:
    clicks = 0
    datapoint = DataPoint()

    def __init__(self, pin):
        pin.irq(trigger=Pin.IRQ_RISING, handler=self.__click, hard=True)

    def __click():
        clicks += 1
    
    def update():
        
