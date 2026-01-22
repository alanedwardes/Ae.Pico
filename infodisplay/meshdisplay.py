import math
import utime
import asyncio
import gc
from array import array

WIDTH = 320
HEIGHT = 240

def load_obj(filename):
    vertices = []
    faces = []
    with open(filename, 'r') as f:
        for line in f:
            if line.startswith('v '):
                parts = line.strip().split()
                vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif line.startswith('f '):
                parts = line.strip().split()
                # OBJ indices are 1-based, so subtract 1
                face = [int(p.split('/')[0]) - 1 for p in parts[1:]]
                faces.append(face)
    return vertices, faces

def project(x, y, z, angle):
    # Simple perspective projection
    fov = 256
    distance = fov / (z + 4)
    x_proj = int(x * distance + WIDTH // 2)
    y_proj = int(-y * distance + HEIGHT // 2)
    return x_proj, y_proj

def draw_mesh(display, angle, vertices, faces):
    # Rotate vertices
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

    # Calculate average Z for each face for painter's algorithm
    face_depths = []
    for i, face in enumerate(faces):
        avg_z = sum(rotated[idx][2] for idx in face) / len(face)
        face_depths.append((avg_z, i))
    face_depths.sort(reverse=True)  # Draw farthest faces first

    # Simple color cycling for faces
    base_colors = [
        (255, 0, 0), (0, 255, 0), (0, 0, 255),
        (255, 255, 0), (0, 255, 255), (255, 0, 255)
    ]

    # Draw filled faces
    for _, face_idx in face_depths:
        face = faces[face_idx]
        points = [projected[idx] for idx in face]
        color = base_colors[face_idx % len(base_colors)]
        # Expecting callers to pass ints; here we convert the static palette to ints inline
        r, g, b = color
        face_pen = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        flat = []
        for (px, py) in points:
            flat.append(int(px))
            flat.append(int(py))
        display.poly(0, 0, array('h', flat), face_pen, True)

    # Draw edges on top
    edge_pen = 0xFFFF
    for face in faces:
        for i in range(len(face)):
            start = face[i]
            end = face[(i + 1) % len(face)]
            x1, y1 = projected[start]
            x2, y2 = projected[end]
            display.line(x1, y1, x2, y2, edge_pen)

class MeshDisplay:
    def __init__(self, display, mesh_vertices, mesh_faces):
        self.display = display
        self.display_width, self.display_height = self.display.get_bounds()
        self.angle = 0
        self.vertices = mesh_vertices
        self.faces = mesh_faces

    CREATION_PRIORITY = 1
    @staticmethod
    def create(provider):
        # You can set the OBJ file path in your config or hardcode it here
        obj_path = provider['config'].get('obj_path', 'mesh.obj')
        vertices, faces = load_obj(obj_path)
        return MeshDisplay(provider['display'], vertices, faces)

    async def start(self):
        while True:
            self.angle += 0.05
            self.update()
            await asyncio.sleep(0.01)

    def update(self):
        start_update_ms = utime.ticks_ms()
        mem_before = gc.mem_alloc()
        # Clear with black
        self.display.fill(0x0000)
        draw_mesh(self.display, self.angle, self.vertices, self.faces)

        update_time_ms = utime.ticks_diff(utime.ticks_ms(), start_update_ms)
        mem_after = gc.mem_alloc()
        print(f"MeshDisplay: {update_time_ms}ms, mem: {mem_before} -> {mem_after} ({mem_after - mem_before:+d})")
