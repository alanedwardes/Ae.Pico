import utime
import math


def effect_rainbow(ctrl, seg):
    """Match WLED colorloop/rainbow hue progression and spacing."""
    if not ctrl.np:
        return

    now = utime.ticks_ms()
    speed = seg["sx"]
    intensity = seg["ix"]

    # Effective brightness comes from transition state
    factor = seg["_current_bri"] / 255.0

    counter = (now * ((speed >> 2) + 2)) & 0xFFFF
    counter = counter >> 8
    span_scale = 16 << (intensity // 29)  # upstream mapping

    length = max(1, seg["len"])

    for i in range(seg["start"], seg["stop"]):
        local_i = i - seg["start"]
        remapped_i = ctrl._remap_pixel_index(local_i, seg)

        hue = ((remapped_i * span_scale) // length + counter) & 0xFF
        color = ctrl._get_palette_color(seg["pal"], hue, seg)

        ctrl.pixel_buffer[i] = (
            int(color[0] * factor),
            int(color[1] * factor),
            int(color[2] * factor),
        )


def effect_color_wipe(ctrl, seg):
    """Match WLED timing; add intensity-based edge softness."""
    now = utime.ticks_ms()
    speed = seg["sx"]

    cycle_duration = 750 + (255 - speed) * 150
    progress = (now % cycle_duration) / cycle_duration

    wipe_pos = int(seg["len"] * progress)
    effective_bri = seg["_current_bri"]
    factor = effective_bri / 255.0
    intensity = seg["ix"]  # 0-255
    intensity_factor = intensity / 255.0

    # Edge softness like upstream rem calculation
    edge = int(progress * 2 * seg["len"])
    edge = edge // (intensity + 1)
    if edge > 255:
        edge = 255
    edge_factor = edge / 255.0

    for i in range(seg["len"]):
        idx = seg["start"] + i
        remapped_i = ctrl._remap_pixel_index(i, seg)
        color = ctrl._get_palette_color(
            seg["pal"], (remapped_i * 255 // seg["len"]) & 255, seg
        )

        if (i <= wipe_pos and not seg["rev"]) or (
            i > (seg["len"] - wipe_pos) and seg["rev"]
        ):
            base = (
                int(color[0] * factor * intensity_factor),
                int(color[1] * factor * intensity_factor),
                int(color[2] * factor * intensity_factor),
            )
            ctrl.pixel_buffer[idx] = base
            if i == wipe_pos and edge_factor < 1.0:
                ctrl.pixel_buffer[idx] = (
                    int(base[0] * edge_factor),
                    int(base[1] * edge_factor),
                    int(base[2] * edge_factor),
                )
        else:
            ctrl.pixel_buffer[idx] = (0, 0, 0)


def effect_scan(ctrl, seg):
    """Match WLED timing and intensity-based dot size."""
    now = utime.ticks_ms()
    speed = seg["sx"]

    cycle_duration = 750 + (255 - speed) * 150
    progress = (now % cycle_duration) / cycle_duration

    if progress > 0.5:
        progress = 1.0 - progress
    scan_pos = int(seg["len"] * progress * 2)

    size = 1 + ((seg["ix"] * seg["len"]) >> 9)
    if size < 1:
        size = 1

    factor = seg["_current_bri"] / 255.0
    intensity = seg["ix"] / 255.0
    color = ctrl._get_palette_color(seg["pal"], 0, seg)
    r = int(color[0] * factor * intensity)
    g = int(color[1] * factor * intensity)
    b = int(color[2] * factor * intensity)

    for i in range(seg["len"]):
        idx = seg["start"] + i
        remapped_i = ctrl._remap_pixel_index(i, seg)

        in_window = abs(remapped_i - scan_pos) < size
        ctrl.pixel_buffer[idx] = (r, g, b) if in_window else (0, 0, 0)


def effect_theater_chase(ctrl, seg):
    """Match WLED timing and intensity-driven gap width."""
    now = utime.ticks_ms()
    speed = seg["sx"]

    cycle_duration = 50 + (255 - speed)
    offset = (now // cycle_duration) % 3

    factor = seg["_current_bri"] / 255.0
    intensity = seg["ix"] / 255.0

    width = 3 + (seg["ix"] >> 4)  # upstream width growth with intensity

    color = ctrl._get_palette_color(seg["pal"], 0, seg)
    r = int(color[0] * factor * intensity)
    g = int(color[1] * factor * intensity)
    b = int(color[2] * factor * intensity)

    for i in range(seg["len"]):
        idx = seg["start"] + i
        remapped_i = ctrl._remap_pixel_index(i, seg)

        if (remapped_i % width) == offset:
            ctrl.pixel_buffer[idx] = (r, g, b)
        else:
            ctrl.pixel_buffer[idx] = (0, 0, 0)

