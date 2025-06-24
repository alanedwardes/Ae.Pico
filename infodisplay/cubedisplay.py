import math
import asyncio

WIDTH = 320
HEIGHT = 240

# Function to project 3D points to 2D
def project(x, y, z, angle):
    # Simple perspective projection
    fov = 256
    distance = fov / (z + 4)
    x_proj = int(x * distance + WIDTH // 2)
    y_proj = int(-y * distance + HEIGHT // 2)
    return x_proj, y_proj

# Function to draw a cube
def draw_cube(display, angle):
    # Define cube vertices
    size = 1
    vertices = [
        [-size, -size, -size],
        [size, -size, -size],
        [size, size, -size],
        [-size, size, -size],
        [-size, -size, size],
        [size, -size, size],
        [size, size, size],
        [-size, size, size]
    ]

    # Rotate the cube
    rotated = []
    for v in vertices:
        # Rotate around the Y-axis
        x = v[0] * math.cos(angle) - v[2] * math.sin(angle)
        z = v[0] * math.sin(angle) + v[2] * math.cos(angle)
        # Rotate around the X-axis for a better 3D effect
        y = v[1] * math.cos(angle) - z * math.sin(angle)
        z2 = v[1] * math.sin(angle) + z * math.cos(angle)
        rotated.append([x, y, z2])

    # Project vertices
    projected = [project(v[0], v[1], v[2], angle) for v in rotated]

    # Define cube faces (each as a list of 4 vertex indices)
    faces = [
        [0, 1, 2, 3],  # back
        [4, 5, 6, 7],  # front
        [0, 1, 5, 4],  # bottom
        [2, 3, 7, 6],  # top
        [1, 2, 6, 5],  # right
        [0, 3, 7, 4],  # left
    ]

    # Calculate average Z for each face for painter's algorithm
    face_depths = []
    for i, face in enumerate(faces):
        avg_z = sum(rotated[idx][2] for idx in face) / 4
        face_depths.append((avg_z, i))
    face_depths.sort(reverse=True)  # Draw farthest faces first

    # Colors for faces (optional)
    face_colors = [
        (255, 0, 0),    # back - red
        (0, 255, 0),    # front - green
        (0, 0, 255),    # bottom - blue
        (255, 255, 0),  # top - yellow
        (0, 255, 255),  # right - cyan
        (255, 0, 255),  # left - magenta
    ]

    # Draw filled faces
    for _, face_idx in face_depths:
        face = faces[face_idx]
        points = [projected[idx] for idx in face]
        color = face_colors[face_idx]
        display.set_pen(display.create_pen(*color))
        display.polygon(points)

    # Draw edges on top
    edges = [
        (0, 1), (1, 2), (2, 3), (3, 0),  # bottom face
        (4, 5), (5, 6), (6, 7), (7, 4),  # top face
        (0, 4), (1, 5), (2, 6), (3, 7)   # vertical edges
    ]
    display.set_pen(display.create_pen(255, 255, 255))
    for start, end in edges:
        x1, y1 = projected[start]
        x2, y2 = projected[end]
        display.line(x1, y1, x2, y2)

class CubeDisplay:
    def __init__(self, display):
        self.display = display
        self.is_active = True        
        self.display_width, self.display_height = self.display.get_bounds()
        self.angle = 0
    
    CREATION_PRIORITY = 1
    def create(provider):
        config = provider['config']['rain']
        return CubeDisplay(provider['display'])
    
    async def start(self):
        while True:
            self.angle += 0.05
            self.update()
            await asyncio.sleep(0.01)

    def update(self):
        self.display.set_pen(self.display.create_pen(0, 0, 0))
        self.display.clear()
        
        self.display.set_pen(self.display.create_pen(255, 255, 255))
        draw_cube(self.display, self.angle)
        
        self.display.update()
