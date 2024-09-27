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

        self.display_width, self.display_height = self.display.get_bounds()
        self.display_half_width = self.display_width * 0.5

        self.display.set_font("sans")
        self.entity = {'s': 0, 'a': {'min_temp': 0, 'max_temp': 0, 'current_temperature': 0, 'temperature': 0, 'target_temp_step': 0, 'hvac_action': 'idle'}}
    
    def draw_text(self, text, scale, y):
        width = self.display.measure_text(text, scale)
        height = scale * 20
        self.display.set_thickness(int(scale * 2))

        x = int(self.display_half_width - width * 0.5)
        
        half_height = height * 0.5
        
        self.display.text(text, x, int(y + half_height), scale=scale)
        
        return height

    def draw_rectangle(self, width, height, y):
        x = int(self.display_half_width - width * 0.5)
        
        self.display.rectangle(x, y, width, height)
        
        return height

    def update(self):
        self.display.set_pen(self.black)
        self.display.clear()

        now = utime.localtime()
        
        y = 64
        
        self.display.set_pen(self.white)
        y += self.draw_text("%.1fC" % (self.entity['a']['temperature']), 2, y)
    
        y += 16
        
        self.display.set_pen(self.orange)
        y += self.draw_rectangle(280, 8, y)
        
        y += 16
        
        self.display.set_pen(self.grey)
        y += self.draw_text("%.1fC" % (self.entity['a']['current_temperature']), 2, y)
        
        y += 16
        
        self.display.set_pen(self.hidden)
        y += self.draw_text("%i dB" % (self.wlan.status('rssi')), 1, y)
        
        self.display.update()
