import utime
import network

class Thermostat:
    def __init__(self, display):
        self.display = display
        self.wlan = network.WLAN(network.STA_IF)
        
        self.white = self.display.create_pen(255, 255, 255)
        self.grey = self.display.create_pen(128, 128, 128)
        self.hidden = self.display.create_pen(32, 32, 32)
        self.black = self.display.create_pen(0, 0, 0)
        self.orange = self.display.create_pen(255, 165, 0)
        self.turquoise = self.display.create_pen(0, 206, 209)
        self.green = self.display.create_pen(0, 255, 0)
        self.red = self.display.create_pen(255, 0, 0)

        self.display_width, self.display_height = self.display.get_bounds()
        self.display_half_width = self.display_width * 0.5

        self.entity = {'min_temp': 0, 'max_temp': 0, 'current_temperature': 0, 'temperature': 0, 'target_temp_step': 0, 'hvac_action': 'idle'}
    
    def draw_text(self, text, scale, y):
        width = self.display.measure_text(text, scale)
        height = scale * 20
        self.display.set_thickness(int(scale * 3))

        x = int(self.display_half_width - width * 0.5)
        
        half_height = height * 0.5
        
        self.display.text(text, x, int(y + half_height), scale=scale)
        
        return int(height)

    def draw_rectangle(self, width, height, y):
        x = int(self.display_half_width - width * 0.5)
        
        self.display.rectangle(x, y, width, height)
        
        return height

    def update(self):
        self.display.set_font("sans")
        self.display.set_pen(self.black)
        self.display.clear()

        now = utime.localtime()
        
        spacer = 16
        
        y = spacer
        
        self.display.set_pen(self.white)
        y += self.draw_text("%02i:%02i:%02i" % (now[3], now[4], now[5]), 2.25, y)
        
        y += spacer
        
        self.display.set_pen(self.turquoise)
        y += self.draw_rectangle(320, 8, y)
        
        y += spacer
        
        self.display.set_pen(self.white)
        y += self.draw_text("%.1fC" % (self.entity['temperature']), 2.25, y)
    
        y += spacer
        
        self.display.set_pen(self.orange)
        y += self.draw_rectangle(320, 8, y)
        
        y += spacer
        
        self.display.set_pen(self.grey)
        y += self.draw_text("%.1fC" % (self.entity['current_temperature']), 2.25, y)
        
        y += spacer
        
        self.display.set_font("bitmap8")
        self.display.set_pen(self.hidden)
        self.display.set_thickness(1)
        self.display.text("%i dB" % (self.wlan.status('rssi')), 10, 220, scale=1)
        
        self.display.update()
