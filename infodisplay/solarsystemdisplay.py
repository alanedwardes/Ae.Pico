import math
import utime
import asyncio
import textbox
import random

class SolarSystemDisplay:
    def __init__(self, display):
        self.display = display
        
        self.display_width, self.display_height = self.display.get_bounds()
        self.center_x = int(self.display_width / 2)
        
        # Assume top bar takes 70px, similar to InfoDisplay and WeatherDisplay
        self.top_margin = 70
        self.center_y = int(self.top_margin + (self.display_height - self.top_margin) / 2)
        
        self.sun_color = 0xFFE0  # Yellow
        self.orbit_color = 0x4208 # Dark Grey
        self.bg_color = 0x0000    # Black
        
        # Solar system data (J2000.0 Elements)
        # a: semi-major axis (AU), e: eccentricity
        # i: inclination (deg), node: long. asc. node (deg), arg_p: arg. of perihelion (deg)
        # L0: Mean Longitude at J2000 (deg), period: Sidereal period (days)
        # size: Display size (px), color: color 565
        self.planets = [
            # Mercury
            {'name': 'Mercury', 'a': 0.387, 'e': 0.2056, 'i': 7.00, 'node': 48.33, 'arg_p': 29.12, 'L0': 252.25, 'period': 87.97, 'color': 0x8410, 'size': 2},
            # Venus
            {'name': 'Venus', 'a': 0.723, 'e': 0.0068, 'i': 3.39, 'node': 76.68, 'arg_p': 54.88, 'L0': 181.98, 'period': 224.7, 'color': 0xFFE0, 'size': 4},
            # Earth
            {'name': 'Earth', 'a': 1.000, 'e': 0.0167, 'i': 0.00, 'node': 0.00, 'arg_p': 102.9, 'L0': 100.46, 'period': 365.25, 'color': 0x041F, 'size': 4},
            # Mars
            {'name': 'Mars', 'a': 1.524, 'e': 0.0934, 'i': 1.85, 'node': 49.58, 'arg_p': 286.50, 'L0': 355.45, 'period': 686.97, 'color': 0xF800, 'size': 3},
            # Jupiter
            {'name': 'Jupiter', 'a': 5.204, 'e': 0.0489, 'i': 1.30, 'node': 100.56, 'arg_p': 273.87, 'L0': 34.40, 'period': 4332.59, 'color': 0xFD20, 'size': 7},
            # Saturn
            {'name': 'Saturn', 'a': 9.582, 'e': 0.0565, 'i': 2.49, 'node': 113.72, 'arg_p': 339.39, 'L0': 49.94, 'period': 10759.2, 'color': 0xDBC0, 'size': 6},
            # Uranus
            {'name': 'Uranus', 'a': 19.20, 'e': 0.0472, 'i': 0.77, 'node': 74.00, 'arg_p': 96.66, 'L0': 313.23, 'period': 30685.4, 'color': 0x07FF, 'size': 5},
            # Neptune
            {'name': 'Neptune', 'a': 30.05, 'e': 0.0086, 'i': 1.77, 'node': 131.78, 'arg_p': 272.85, 'L0': 304.88, 'period': 60189.0, 'color': 0x001F, 'size': 5},
            # Pluto (Dwarf)
            {'name': 'Pluto', 'a': 39.48, 'e': 0.2488, 'i': 17.16, 'node': 110.30, 'arg_p': 113.76, 'L0': 238.93, 'period': 90560, 'color': 0xC618, 'size': 2},
             # Ceres (Dwarf)
            {'name': 'Ceres', 'a': 2.767, 'e': 0.0758, 'i': 10.59, 'node': 80.33, 'arg_p': 73.51, 'L0': 77.0, 'period': 1682, 'color': 0x8410, 'size': 2} 
        ]
        
        # Comets
        # For comets, 'L0' is often not standard, use Time of Perihelion or just L at epoch if available.
        # Here we approximate with L0 for visualization.
        self.comets = [
            # Halley's Comet
            {'name': 'Halley', 'a': 17.83, 'e': 0.967, 'i': 162.3, 'node': 58.42, 'arg_p': 111.33, 'L0': 38.0, 'period': 27510, 'color': 0xFFFF, 'size': 2},
             # Encke
            {'name': 'Encke', 'a': 2.21, 'e': 0.848, 'i': 11.78, 'node': 334.56, 'arg_p': 186.54, 'L0': 160.0, 'period': 1204, 'color': 0xBDF7, 'size': 1}
        ]
        
        # Layout / View Configuration
        # Max radius X is half width minus padding
        self.max_radius_x = (self.display_width // 2) - 25 
        self.usable_height = self.display_height - self.top_margin
        
        # Scale to fit Neptune (approx 30 AU)
        # Using Square Root scaling: r_screen = k * sqrt(r_au)
        # Max distance Neptune: sqrt(30.05) ~= 5.48
        # We can also zoom out slightly to fit Pluto (sqrt(39.5) ~ 6.28)
        self.scale_factor = self.max_radius_x / 6.3
        
        # Camera / Projection Angle
        # We look from an angle above the ecliptic.
        # pitch = 0 -> Edge on (i=90 relative to screen normal?)
        # pitch = 90 -> Top down
        # Previous tilt_ratio was 0.53, corresponds to sin(pitch).
        # Let's define pitch angle:
        self.view_pitch_rad = math.asin(0.53) # ~32 degrees
        self.sin_pitch = math.sin(self.view_pitch_rad)
        self.cos_pitch = math.cos(self.view_pitch_rad)
    
    def _true_anomaly_approx(self, mean_anomaly, eccentricity):
        """Equation of center approximation for elliptical orbits (good for e < 0.3)"""
        e = eccentricity
        M = mean_anomaly
        # Series expansion
        true_anomaly = M + (2*e - 0.25*e**3) * math.sin(M) \
                         + 1.25 * e**2 * math.sin(2*M) \
                         + (13.0/12.0) * e**3 * math.sin(3*M)
        return true_anomaly
        
    def _solve_kepler(self, M, e):
        """Solve Kepler's Equation M = E - e*sin(E) for Eccentric Anomaly E"""
        # For M in radians
        if e < 0.3:
            return self._true_anomaly_approx(M, e)
        
        # Newton-Raphson for high eccentricity
        E = M 
        for _ in range(10):
            E = E - (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
            
        # Convert Eccentric Anomaly E to True Anomaly v
        # tan(v/2) = sqrt((1+e)/(1-e)) * tan(E/2)
        true_anom = 2 * math.atan2(
            math.sqrt(1 + e) * math.sin(E / 2),
            math.sqrt(1 - e) * math.cos(E / 2)
        )
        return true_anom

    def _get_orbital_radius(self, a, e, true_anomaly):
        """Heliocentric distance r"""
        return a * (1 - e**2) / (1 + e * math.cos(true_anomaly))
        
    def _to_heliocentric_coords(self, r, true_anom, node_deg, i_deg, arg_p_deg):
        """
        Convert orbital elements to 3D Heliocentric Ecliptic Coordinates.
        Returns (x, y, z) in AU.
        """
        node = math.radians(node_deg)
        inc = math.radians(i_deg)
        omega = math.radians(arg_p_deg)
        nu = true_anom
        
        # Argument of Latitude u = omega + nu
        u = omega + nu
        
        sin_u = math.sin(u)
        cos_u = math.cos(u)
        sin_node = math.sin(node)
        cos_node = math.cos(node)
        sin_i = math.sin(inc)
        cos_i = math.cos(inc)
        
        # 3D Position components
        x = r * (cos_node * cos_u - sin_node * sin_u * cos_i)
        y = r * (sin_node * cos_u + cos_node * sin_u * cos_i)
        z = r * (sin_u * sin_i)
        
        return x, y, z

    def _project_to_screen(self, x_au, y_au, z_au):
        """
        Project 3D AU coordinates to 2D Screen Coordinates.
        Using orthogonal projection with camera pitch.
        Apply Square-Root scaling for visualization (distance from sun).
        """
        # Calculate distance from origin (Sun) to scale it visually
        dist_3d = math.sqrt(x_au*x_au + y_au*y_au + z_au*z_au)
        
        if dist_3d < 0.001: return self.center_x, self.center_y

        # Visual Scale: k * sqrt(d)
        scale_r = math.sqrt(dist_3d) * self.scale_factor
        
        # We need to scale the vector (x,y,z) to this new length 'scale_r'
        # normalized * new_length
        ratio = scale_r / dist_3d
        
        sx = x_au * ratio
        sy = y_au * ratio
        sz = z_au * ratio
        
        # Rotate for Camera Pitch (around X-axis effectively, simply mapping Y/Z)
        # We are looking along Y? Or Z?
        # Standard: X points right (Vernal Equinox), Y points 'forward' ??
        # Let's map X_ecliptic -> X_screen
        # Y_ecliptic -> Y_screen (tilted)
        # Z_ecliptic -> Up
        
        # Logic: 
        # Screen X = sx
        # Screen Y = sy * sin(pitch) - sz * cos(pitch) 
        # (Looking from 'south' up? Or 'north' down?)
        # Let's try: looking from North Pole down (Top Down) is pitch=90.
        # Y_screen = -sy (if Y goes down)
        
        # Let's match previous tilt behavior.
        # Previously: y_screen = y_plane * tilt
        # tilt ~= sin(pitch)
        # So Z component must be projected onto Y screen.
        # If we look "down" from angle, +Z (up) should shift Y_screen "up" (negative pixel delta).
        
        px = self.center_x + sx
        
        # Y projection:
        # tilted Y component + projected Z height
        # If we tilt X-Y plane, Y gets shortened. Z gets visible.
        proj_y = sy * self.sin_pitch - sz * self.cos_pitch
        
        py = self.center_y + proj_y
        
        return int(px), int(py)

    CREATION_PRIORITY = 1
    
    @staticmethod
    def create(provider):
        return SolarSystemDisplay(provider['display'])
        
    async def start(self):
        await asyncio.Event().wait()

    def should_activate(self):
        return True

    async def activate(self):
        # Clear background
        self.display.rect(0, self.top_margin, self.display_width, self.display_height - self.top_margin, self.bg_color, True)

        # Draw Sun
        self.display.aa_circle(self.center_x, self.center_y, 6, self.sun_color)
        
        # Get constant for time
        t_seconds = utime.time()
        days_since_j2000 = t_seconds / 86400.0
        
        # Process Planets
        for p in self.planets:
            # Mean Anomaly
            # M = L - varpi (where varpi = Omega + omega_arg)
            # here we have L0 (Mean Longitude) directly.
            # M = L0 + n*t - varpi
            # But we can just use M = (L - varpi)
            
            # Calculate Mean Longitude at time t
            L = p['L0'] + (360.0 / p['period']) * days_since_j2000
            
            # Varpi (Longitude of Perihelion) = Node + Arg_Per
            varpi = p['node'] + p['arg_p']
            
            M_deg = L - varpi
            M_rad = math.radians(M_deg % 360)
            
            # True Anomaly
            true_anom = self._solve_kepler(M_rad, p['e'])
            
            # Radius (AU)
            r_au = self._get_orbital_radius(p['a'], p['e'], true_anom)
            
            # 3D Coordinates
            x, y, z = self._to_heliocentric_coords(r_au, true_anom, p['node'], p['i'], p['arg_p'])
            
            # Project to Screen
            px, py = self._project_to_screen(x, y, z)
            
            # Draw Orbit Path
            self._draw_orbit_path(p)
            
            # Draw Planet
            self._draw_planet(p['name'], px, py, p['size'], p['color'])
            await asyncio.sleep(0)
        
        # Process Comets
        for c in self.comets:
            await self._draw_comet(c, days_since_j2000)

        self.display.update((0, self.top_margin, self.display_width, self.display_height - self.top_margin))

    def _draw_orbit_path(self, body):
        # Sample points along the orbit to draw 3D ellipse
        # This is static for a body (elements don't change fast)
        # We can calculate ~60 points
        
        steps = 60
        color = self.orbit_color
        
        for i in range(steps):
            M_rad = (i / steps) * 2 * math.pi
            # Get v from M
            v = self._solve_kepler(M_rad, body['e'])
            r = self._get_orbital_radius(body['a'], body['e'], v)
            
            x, y, z = self._to_heliocentric_coords(r, v, body['node'], body['i'], body['arg_p'])
            
            px, py = self._project_to_screen(x, y, z)
            
            if self.top_margin <= py < self.display_height:
                self.display.pixel(px, py, color)

    def _draw_moon(self, cx, cy, radius_px, angle_offset, color):
        t = utime.time() / 86400.0
        angle = angle_offset + (t * 10.0)
        
        # Simple 2D orbit for moons around planet (projected with global tilt)
        mx = int(cx + math.cos(angle) * radius_px)
        # Apply simple foreshortening
        my = int(cy + math.sin(angle) * radius_px * self.sin_pitch)
        
        self.display.pixel(mx, my, color)

    def _draw_planet(self, name, cx, cy, radius, color):
        # Draw base planet
        self.display.aa_circle(cx, cy, radius, color)
        
        # Add details
        if name == 'Mercury':
            self.display.pixel(cx, cy, 0x8410)
        elif name == 'Venus':
            self.display.pixel(cx - 1, cy - 1, 0xFFFF)
        elif name == 'Earth':
            land_color = 0x07E0
            self.display.pixel(cx - 1, cy - 1, land_color)
            self.display.pixel(cx + 2, cy + 1, land_color)
            self.display.pixel(cx, cy + 1, land_color)
            self.display.pixel(cx, cy - 2, 0xFFFF) 
            self._draw_moon(cx, cy, radius + 5, 0, 0x8410)
        elif name == 'Mars':
             self.display.pixel(cx, cy, 0x8000)
             self.display.pixel(cx, cy - 1, 0xFFFF)
        elif name == 'Jupiter':
            band_color = 0xC618
            w = int(radius * 0.9)
            self.display.hline(cx - w, cy - 3, w * 2, band_color)
            self.display.hline(cx - w, cy - 2, w * 2, band_color)
            self.display.hline(cx - w, cy + 1, w * 2, band_color)
            self.display.hline(cx - w, cy + 2, w * 2, band_color)
            
            spot_color = 0xC145
            spot_cx = cx + 2
            spot_cy = cy + 3
            self.display.pixel(spot_cx - 1, spot_cy, spot_color)
            self.display.pixel(spot_cx, spot_cy, spot_color)
            self.display.pixel(spot_cx + 1, spot_cy, spot_color)
            self.display.pixel(spot_cx, spot_cy - 1, spot_color)
            self.display.pixel(spot_cx, spot_cy + 1, spot_color)
            
            self._draw_moon(cx, cy, radius + 4, 1.0, 0xFFFF)
            self._draw_moon(cx, cy, radius + 7, 2.5, 0xFFFF)
            self._draw_moon(cx, cy, radius + 10, 4.0, 0xFFFF)
            self._draw_moon(cx, cy, radius + 13, 5.5, 0xFFFF)
        elif name == 'Saturn':
            # Rings
            ring_rad_x = int(radius * 1.8)
            ring_rad_y = int(ring_rad_x * self.sin_pitch)
            self.display.ellipse(cx, cy, ring_rad_x, ring_rad_y, 0x8410, False)
            self.display.pixel(cx, cy - radius - 1, 0x0000)
            self._draw_moon(cx, cy, radius + 12, 0.5, 0xDBC0)
        elif name == 'Uranus':
            self.display.vline(cx, cy - 2, 4, 0x05FF)
            # Rings (vertical-ish)
            ring_w = 2
            ring_h = int(radius * 1.8)
            self.display.ellipse(cx, cy, ring_w, ring_h, 0x05FF, False)
        elif name == 'Neptune':
            self.display.pixel(cx + 1, cy - 1, 0x0010)

    async def _draw_comet(self, c, days_since_j2000):
        # Calculate position Same as planets
        L = c['L0'] + (360.0 / c['period']) * days_since_j2000
        varpi = c['node'] + c['arg_p']
        M_deg = L - varpi
        M_rad = math.radians(M_deg % 360)
        
        true_anom = self._solve_kepler(M_rad, c['e'])
        r_au = self._get_orbital_radius(c['a'], c['e'], true_anom)
        x, y, z = self._to_heliocentric_coords(r_au, true_anom, c['node'], c['i'], c['arg_p'])
        
        cx, cy = self._project_to_screen(x, y, z)
        
        if not (self.top_margin <= cy < self.display_height and 0 <= cx < self.display_width):
            return

        # Draw Orbit
        # Fewer dots for comet
        # Draw logic similar to planet but separate method or inline?
        # Let's reuse internal logic manually for efficiency/custom color
        steps = 40
        for i in range(steps):
             M_samp = (i / steps) * 2 * math.pi
             v = self._solve_kepler(M_samp, c['e'])
             r = self._get_orbital_radius(c['a'], c['e'], v)
             ox, oy, oz = self._to_heliocentric_coords(r, v, c['node'], c['i'], c['arg_p'])
             opx, opy = self._project_to_screen(ox, oy, oz)
             if self.top_margin <= opy < self.display_height:
                 self.display.pixel(opx, opy, 0x2104)

        # Draw Nucleus
        self.display.aa_circle(cx, cy, c['size'], c['color'])
        
        # Draw Tail (Away from Sun)
        # Vector from Sun(0,0,0) to Comet(x,y,z) is (x,y,z)
        # Tail is in direction (x,y,z).
        # We need to project the tail vector.
        # Actually in 3D, tail points radially out.
        # So we can just take point P2 = P + (P_norm * length)
        # And project P2.
        
        dist = r_au # calculated above
        if dist > 0.1:
            tail_len_au = min(2.0, 5.0 / dist) # AU length of tail
            # Tail tip position
            tx = x * (1 + tail_len_au/dist)
            ty = y * (1 + tail_len_au/dist)
            tz = z * (1 + tail_len_au/dist)
            
            tx_s, ty_s = self._project_to_screen(tx, ty, tz)
            
            # Draw line from cx,cy to tx_s, ty_s with fade
            # Simple interpolation
            dx = tx_s - cx
            dy = ty_s - cy
            steps = int(math.sqrt(dx*dx + dy*dy))
            if steps > 0:
                dx /= steps
                dy /= steps
                for i in range(steps):
                    fade = max(0, 255 - i * (255/steps)*1.5) # Fade out
                    fade = int(fade)
                    r5 = fade >> 3
                    g6 = fade >> 2
                    b5 = fade >> 3
                    col = (r5 << 11) | (g6 << 5) | b5
                    
                    px = int(cx + dx * i)
                    py = int(cy + dy * i)
                     
                    if self.top_margin <= py < self.display_height:
                        self.display.pixel(px, py, col)
        
        await asyncio.sleep(0)
