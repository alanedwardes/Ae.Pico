import utime
import network

class Thermostat:
    def __init__(self, display):
        self.display = display
        self.wlan = network.WLAN(network.STA_IF)
        
        self.white = self.display.create_pen(255, 255, 255)
        self.grey = self.display.create_pen(128, 128, 128)
        self.black = self.display.create_pen(0, 0, 0)
        
        self.over_41c = self.display.create_pen(154, 27, 30)
        self.over_30c = self.display.create_pen(238, 45, 41)
        self.over_21c = self.display.create_pen(242, 106, 48)
        self.over_17c = self.display.create_pen(250, 163, 26)
        self.over_15c = self.display.create_pen(251, 182, 22)
        self.over_11c = self.display.create_pen(254, 219, 0)
        self.over_9c = self.display.create_pen(208, 215, 62)
        self.over_7c = self.display.create_pen(175, 210, 81)
        self.over_5c = self.display.create_pen(159, 205, 128)
        self.over_3c = self.display.create_pen(170, 214, 174)
        self.over_1c = self.display.create_pen(174, 220, 216)
        self.over_n10 = self.display.create_pen(55, 137, 198)
        self.cold = self.display.create_pen(2, 98, 169)

        self.display_width, self.display_height = self.display.get_bounds()
        self.display_half_width = self.display_width * 0.5

        self.entity = {'min_temp': 0, 'max_temp': 0, 'current_temperature': 0, 'temperature': 0, 'target_temp_step': 0, 'hvac_action': 'idle'}
        self.weather = {'current_temperature': 0, 'maximum_temperature': 0, 'current_precipitation': 0}
    
    def pen_for_temp(self, temp):
        if temp >= 41:
            return self.over_41c
        elif temp >= 30:
            return self.over_30c
        elif temp >= 21:
            return self.over_21c
        elif temp >= 17:
            return self.over_17c
        elif temp >= 15:
            return self.over_15c
        elif temp >= 11:
            return self.over_11c
        elif temp >= 9:
            return self.over_9c
        elif temp >= 7:
            return self.over_7c
        elif temp >= 5:
            return self.over_5c
        elif temp >= 3:
            return self.over_3c
        elif temp >= 1:
            return self.over_1c
        elif temp >= -10:
            return self.over_n10
        else:
            return self.cold
    
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
        
        self.display.set_pen(self.pen_for_temp(self.entity['current_temperature']))
        y += self.draw_rectangle(320, 8, y)
        
        y += spacer
        
        y += self.draw_text("%.1fc %.1fc" % (self.entity['temperature'], self.entity['current_temperature']), 1.5, y)
        
        y += 5

        self.display.set_pen(self.grey)
        self.draw_text("target     now", 1, y)
        
        y += 12
    
        y += spacer
        
        self.display.set_pen(self.pen_for_temp(self.weather['current_temperature']))
        y += self.draw_rectangle(320, 8, y)
        
        y += spacer
        
        y += self.draw_text("%.0fc %.0fc %.0f%%" % (self.weather['current_temperature'], self.weather['maximum_temperature'], self.weather['current_precipitation']), 1.25, y)
        
        y += 5
        
        self.display.set_pen(self.grey)
        self.draw_text("now  max  rain", 1, y)
               
        self.display.set_font("bitmap8")
        self.display.set_pen(self.grey)
        self.display.set_thickness(1)
        self.display.text("%idB" % (self.wlan.status('rssi')), 0, 233, scale=1)
        
        self.display.update()
