import math
import utime
import asyncio
import textbox
import random

class SolarSystemDisplay:
    def __init__(self, display, rtc):
        self.display = display
        self.rtc = rtc
        
        self.display_width, self.display_height = self.display.get_bounds()
        self.center_x = int(self.display_width / 2)
        
        # Assume top bar takes 70px, similar to InfoDisplay and WeatherDisplay
        self.top_margin = 70
        self.center_y = int(self.top_margin + (self.display_height - self.top_margin) / 2)
        
        self.sun_color = 0xFFE0  # Yellow
        self.orbit_color = 0x4208 # Dark Grey
        self.bg_color = 0x0000    # Black
        
        # Solar system data
        # Orbital period (days), Distance (AU), Color, Size (px), Name, J2000 Longitude (deg) (Approximate)
        self.planets = [
            # Mercury
            {'period': 87.97, 'dist': 0.39, 'color': 0x8410, 'size': 2, 'name': 'Mercury', 'L0': 252.25},
            # Venus
            {'period': 224.7, 'dist': 0.72, 'color': 0xFFE0, 'size': 4, 'name': 'Venus', 'L0': 181.98},
            # Earth
            {'period': 365.25, 'dist': 1.00, 'color': 0x041F, 'size': 4, 'name': 'Earth', 'L0': 100.46},
            # Mars
            {'period': 686.97, 'dist': 1.52, 'color': 0xF800, 'size': 3, 'name': 'Mars', 'L0': 355.45},
            # Jupiter
            {'period': 4332.59, 'dist': 5.20, 'color': 0xFD20, 'size': 7, 'name': 'Jupiter', 'L0': 34.40},
            # Saturn
            {'period': 10759.22, 'dist': 9.58, 'color': 0xDBC0, 'size': 6, 'name': 'Saturn', 'L0': 49.94},
            # Uranus
            {'period': 30685.4, 'dist': 19.20, 'color': 0x07FF, 'size': 5, 'name': 'Uranus', 'L0': 313.23},
            # Neptune
            {'period': 60189.0, 'dist': 30.05, 'color': 0x001F, 'size': 5, 'name': 'Neptune', 'L0': 304.88}
        ]
        
        # Calculate scale to fit Neptune in the available space
        # We use the full width (320px) now, as we will tilt the view (ellipse)
        # Usable height is approx 170px (240 - 70)
        # Width is 320px
        
        # Max radius X is half width minus padding
        max_radius_x = (self.display_width // 2) - 25 
        
        # Max radius Y is half usable height minus padding
        usable_height = self.display_height - self.top_margin
        max_radius_y = (usable_height // 2) - 10
        
        # Scale factor based on X (Width)
        # Using Square Root scaling: r_screen = k * sqrt(r_au)
        # Max distance Neptune: sqrt(30.05) ~= 5.48
        self.scale_factor_x = max_radius_x / 5.48
        
        # Calculate tilt ratio to fit Y
        # scaled_y = scaled_x * tilt
        # tilt = max_radius_y / max_radius_x
        self.tilt_ratio = max_radius_y / max_radius_x
        
        self.stars = self._generate_stars(50)
        self.asteroids = self._generate_asteroids(100)
    
    def _generate_stars(self, count):
        stars = []
        for _ in range(count):
            x = random.randint(0, self.display_width - 1)
            y = int(self.top_margin + (self.display_height - self.top_margin) * random.random())
            brightness = random.choice([0x4208, 0x8410, 0xC618])
            stars.append((x, y, brightness))
        return stars

    def _generate_asteroids(self, count):
        # Asteroid belt approx 2.2 to 3.2 AU
        # We store (angle_offset, radius_au, speed_factor)
        asteroids = []
        for _ in range(count):
            angle = random.random() * 2 * math.pi
            r_au = 2.2 + random.random() * 1.0 # 2.2 to 3.2
            speed = 1.0 / math.sqrt(r_au**3) # Kepler's 3rd law approx
            asteroids.append((angle, r_au, speed))
        return asteroids
    
    CREATION_PRIORITY = 1
    
    @staticmethod
    def create(provider):
        rtc = provider.get('remotetime.RemoteTime')
        if not rtc:
            import machine
            rtc = machine.RTC()
        return SolarSystemDisplay(provider['display'], rtc)
        
    async def start(self):
        await asyncio.Event().wait()

    def should_activate(self):
        return True

    async def activate(self):
        self.draw()
            
    def draw(self):
        # Clear background
        self.display.rect(0, self.top_margin, self.display_width, self.display_height - self.top_margin, self.bg_color, True)
        
        # Draw Stars
        for x, y, c in self.stars:
            self.display.pixel(x, y, c)

        # Draw Sun
        self.display.aa_circle(self.center_x, self.center_y, 6, self.sun_color)
        
        # Get constant for time
        # Approx days since J2000.0 (2000-01-01 12:00 UTC)
        # utime.time() is seconds since 2000-01-01 00:00 UTC
        t_seconds = utime.time()
        days_since_j2000 = t_seconds / 86400.0
        
        # Draw Asteroids
        self._draw_asteroids(days_since_j2000)
        
        for p in self.planets:
            # Square root scaling for better visibility of inner solar system
            r_au = p['dist']
            r_base = math.sqrt(r_au)
            
            radius_x = int(r_base * self.scale_factor_x)
            radius_y = int(radius_x * self.tilt_ratio)
            
            # Draw Orbit (Elliptical)
            self._draw_orbit_dots(radius_x, radius_y, self.orbit_color)
            
            # Calculate Planet Position
            # Mean longitude
            L = p['L0'] + (360.0 / p['period']) * days_since_j2000
            L_rad = math.radians(L)
            
            px = int(self.center_x + math.cos(L_rad) * radius_x)
            py = int(self.center_y + math.sin(L_rad) * radius_y)
            
            # Draw Planet
            self._draw_planet(p['name'], px, py, p['size'], p['color'])

        self.display.update((0, self.top_margin, self.display_width, self.display_height - self.top_margin))

    def _draw_moon(self, cx, cy, radius_px, angle_offset, color):
        # Draw a moon at a given radius and angle from planet center
        # We can animate them based on time if we want, or just static/random
        # Let's simple orbit based on time to make them move
        t = utime.time() / 86400.0 # Days
        angle = angle_offset + (t * 10.0) # Arbitrary fast speed
        
        mx = int(cx + math.cos(angle) * radius_px)
        # Apply tile to moon orbit too? Maybe just simple circle for moons as they are close
        my = int(cy + math.sin(angle) * radius_px * self.tilt_ratio) 
        
        self.display.pixel(mx, my, color)

    def _draw_planet(self, name, cx, cy, radius, color):
        # Draw base planet
        self.display.aa_circle(cx, cy, radius, color)
        
        # Add details based on planet
        if name == 'Mercury':
             # Greyish crater?
            self.display.pixel(cx, cy, 0x8410)
        
        elif name == 'Venus':
            # Brighter cloud top
            self.display.pixel(cx - 1, cy - 1, 0xFFFF)

        elif name == 'Earth':
            # Continents (Green)
            land_color = 0x07E0
            self.display.pixel(cx - 1, cy - 1, land_color)
            self.display.pixel(cx + 2, cy + 1, land_color)
            self.display.pixel(cx, cy + 1, land_color)
            # Polar cap / Cloud (White)
            self.display.pixel(cx, cy - 2, 0xFFFF) 
            
            # The Moon
            self._draw_moon(cx, cy, radius + 5, 0, 0x8410)

        elif name == 'Mars':
             # Darker red patch (Syrtis Major)
             self.display.pixel(cx, cy, 0x8000)
             # Polar cap (White)
             self.display.pixel(cx, cy - 1, 0xFFFF)

        elif name == 'Jupiter':
            # Draw bands (thicker)
            band_color = 0xC618 # Darker orange/brown
            w = int(radius * 0.9)
            # Upper band (2px thick)
            self.display.hline(cx - w, cy - 3, w * 2, band_color)
            self.display.hline(cx - w, cy - 2, w * 2, band_color)
            # Lower band (2px thick)
            self.display.hline(cx - w, cy + 1, w * 2, band_color)
            self.display.hline(cx - w, cy + 2, w * 2, band_color)
            
            # Great Red Spot (iconic oval)
            spot_color = 0xC145 # Reddish/orange
            spot_cx = cx + 2
            spot_cy = cy + 3
            # Draw a small 3x2 oval for the spot
            self.display.pixel(spot_cx - 1, spot_cy, spot_color)
            self.display.pixel(spot_cx, spot_cy, spot_color)
            self.display.pixel(spot_cx + 1, spot_cy, spot_color)
            self.display.pixel(spot_cx, spot_cy - 1, spot_color)
            self.display.pixel(spot_cx, spot_cy + 1, spot_color)
            
            # Galilean Moons (Io, Europa, Ganymede, Callisto)
            # Distances approximated for visual flair
            self._draw_moon(cx, cy, radius + 4, 1.0, 0xFFFF)
            self._draw_moon(cx, cy, radius + 7, 2.5, 0xFFFF)
            self._draw_moon(cx, cy, radius + 10, 4.0, 0xFFFF)
            self._draw_moon(cx, cy, radius + 13, 5.5, 0xFFFF)

        elif name == 'Saturn':
            # Draw rings
            ring_rad_x = int(radius * 1.8)
            ring_rad_y = int(ring_rad_x * self.tilt_ratio)
            self.display.ellipse(cx, cy, ring_rad_x, ring_rad_y, 0x8410, False)
            # Shadow on rings (behind planet)
            self.display.pixel(cx, cy - radius - 1, 0x0000)
            
            # Titan
            self._draw_moon(cx, cy, radius + 12, 0.5, 0xDBC0)

        elif name == 'Uranus':
            # Vertical banding (subtle)
            self.display.vline(cx, cy - 2, 4, 0x05FF) # Slightly different blue
            # Faint rings (Vertical-ish?) Uranus is tilted 98 deg.
            # Let's draw a vertical ellipse for rings
            ring_w = 2
            ring_h = int(radius * 1.8)
            self.display.ellipse(cx, cy, ring_w, ring_h, 0x05FF, False)

        elif name == 'Neptune':
            # Great Dark Spot
            self.display.pixel(cx + 1, cy - 1, 0x0010) # Dark blue

    def _draw_orbit_dots(self, radius_x, radius_y, color):
        # Draw dotted ellipse approximation
        steps = 60 # Number of dots
        for i in range(steps):
            angle = (i / steps) * 2 * math.pi
            x = int(self.center_x + math.cos(angle) * radius_x)
            y = int(self.center_y + math.sin(angle) * radius_y)
            # Only draw if within bounds
            if self.top_margin <= y < self.display_height:
                 self.display.pixel(x, y, color)

    def _draw_asteroids(self, days):
        color = 0x8410 # Grey
        for angle_offset, r_au, speed_factor in self.asteroids:
            # Simple rotation
            # Earth period is 365.25. Speed factor 1.0 would match roughly earth? 
            # Kepler's 3rd law implies T^2 ~ a^3. 
            # We just need visual movement.
            # Speed = 2pi / T. sqrt(r^3) ~ T.
            # We can just say angle = offset + (some_const * speed * days)
            # Use a slower constant to make it look nice
            
            # Using Earth angular speed as reference: 2pi / 365.25 rad/day
            # speed_factor is roughly relative to Earth speed (actually proportional 1/T)
            # Wait, 1/sqrt(r^3) is proportional to mean motion n. n = k * a^(-3/2).
            # So angle = offset + n * days
            
            mean_motion_deg_per_day = (360.0 / 365.25) * 1.0 # Reference earth
            # But speed_factor was 1/sqrt(r^3). Earth r=1, so factor=1. 
            # So angle = offset + speed_factor * mean_motion * days
            
            current_angle_deg = (angle_offset * 180/math.pi) + (speed_factor * mean_motion_deg_per_day * days)
            angle_rad = math.radians(current_angle_deg)
            
            # Scale radius
            r_screen_base = math.sqrt(r_au) * self.scale_factor_x
            r_x = int(r_screen_base)
            r_y = int(r_x * self.tilt_ratio)
            
            px = int(self.center_x + math.cos(angle_rad) * r_x)
            py = int(self.center_y + math.sin(angle_rad) * r_y)
            
            if self.top_margin <= py < self.display_height:
                self.display.pixel(px, py, color)
