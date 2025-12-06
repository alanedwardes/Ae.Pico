import utime
import math

import wledpalettes

try:
    import urandom as _urandom
except ImportError:
    _urandom = None

def _randint(a, b):
    """Deterministic-friendly randint that works on MicroPython."""
    if _urandom:
        span = b - a + 1
        return a + (_urandom.getrandbits(16) % span)
    import random  # type: ignore
    return random.randint(a, b)


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


def effect_scan_dual(ctrl, seg):
    """Two scanning dots mirrored across the segment."""
    now = utime.ticks_ms()
    speed = seg["sx"]

    cycle_duration = 750 + (255 - speed) * 150
    progress = (now % cycle_duration) / cycle_duration

    pos = int(seg["len"] * progress)
    mirror_pos = seg["len"] - 1 - pos

    size = 1 + ((seg["ix"] * seg["len"]) >> 10)
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
        hit = abs(remapped_i - pos) < size or abs(remapped_i - mirror_pos) < size
        ctrl.pixel_buffer[idx] = (r, g, b) if hit else (0, 0, 0)


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


def effect_theater_rainbow(ctrl, seg):
    """Theater chase with cycling palette hues."""
    now = utime.ticks_ms()
    speed = seg["sx"]
    cycle_duration = 50 + (255 - speed)
    offset = (now // cycle_duration) % 3

    factor = seg["_current_bri"] / 255.0
    intensity = seg["ix"] / 255.0
    width = 3 + (seg["ix"] >> 4)

    hue_shift = (now // 20) & 0xFF

    for i in range(seg["len"]):
        idx = seg["start"] + i
        remapped_i = ctrl._remap_pixel_index(i, seg)
        if (remapped_i % width) == offset:
            hue = (remapped_i * 4 + hue_shift) & 0xFF
            color = ctrl._get_palette_color(seg["pal"], hue, seg)
            ctrl.pixel_buffer[idx] = (
                int(color[0] * factor * intensity),
                int(color[1] * factor * intensity),
                int(color[2] * factor * intensity),
            )
        else:
            ctrl.pixel_buffer[idx] = (0, 0, 0)


def effect_wipe_random(ctrl, seg):
    """Color wipe that picks a new random palette color each cycle."""
    now = utime.ticks_ms()
    speed = seg["sx"]

    cycle_duration = 750 + (255 - speed) * 150
    cycle_pos = (now // cycle_duration) % 65535
    progress = (now % cycle_duration) / cycle_duration
    wipe_pos = int(seg["len"] * progress)

    # Cache cycle color on the segment to avoid re-sampling every tick
    last_cycle = seg.get("_wipe_cycle", -1)
    if last_cycle != cycle_pos:
        seg["_wipe_cycle"] = cycle_pos
        seg["_wipe_color"] = ctrl._get_palette_color(seg["pal"], _randint(0, 255), seg)

    color = seg.get("_wipe_color", ctrl._get_palette_color(seg["pal"], 0, seg))
    factor = seg["_current_bri"] / 255.0
    intensity_factor = seg["ix"] / 255.0

    for i in range(seg["len"]):
        idx = seg["start"] + i
        remapped_i = ctrl._remap_pixel_index(i, seg)
        active = (remapped_i <= wipe_pos and not seg["rev"]) or (
            remapped_i > (seg["len"] - wipe_pos) and seg["rev"]
        )
        if active:
            ctrl.pixel_buffer[idx] = (
                int(color[0] * factor * intensity_factor),
                int(color[1] * factor * intensity_factor),
                int(color[2] * factor * intensity_factor),
            )
        else:
            ctrl.pixel_buffer[idx] = (0, 0, 0)


def effect_random_colors(ctrl, seg):
    """Random pixels that refresh based on speed/intensity."""
    now = utime.ticks_ms()
    speed = seg["sx"]
    intensity = seg["ix"]

    # Update window; higher speed means quicker updates
    interval = max(30, 400 - (speed * 3))
    last_update = seg.get("_rand_last", 0)
    if utime.ticks_diff(now, last_update) >= interval:
        seg["_rand_last"] = now
        seg["_rand_levels"] = [_randint(0, 255) for _ in range(seg["len"])]
        seg["_rand_colors"] = [
            ctrl._get_palette_color(seg["pal"], _randint(0, 255), seg)
            for _ in range(seg["len"])
        ]

    levels = seg.get("_rand_levels") or [255] * seg["len"]
    colors = seg.get("_rand_colors") or [
        ctrl._get_palette_color(seg["pal"], _randint(0, 255), seg)
        for _ in range(seg["len"])
    ]

    factor = seg["_current_bri"] / 255.0
    intensity_factor = (intensity + 32) / 287.0  # keep a little minimum light

    for i in range(seg["len"]):
        idx = seg["start"] + i
        level = levels[i] / 255.0
        color = colors[i]
        ctrl.pixel_buffer[idx] = (
            int(color[0] * factor * intensity_factor * level),
            int(color[1] * factor * intensity_factor * level),
            int(color[2] * factor * intensity_factor * level),
        )


def effect_sweep(ctrl, seg):
    """Sinusoidal sweep across the segment."""
    now = utime.ticks_ms()
    speed = seg["sx"]
    intensity = seg["ix"]

    cycle = 20 + (255 - speed) * 8
    progress = ((now % cycle) / cycle) * 2 * math.pi
    factor = seg["_current_bri"] / 255.0

    for i in range(seg["len"]):
        idx = seg["start"] + i
        remapped_i = ctrl._remap_pixel_index(i, seg)
        phase = progress + (remapped_i * (intensity + 16) / 1024.0)
        wave = (math.sin(phase) + 1) / 2  # 0..1
        color = ctrl._get_palette_color(seg["pal"], int(wave * 255) & 255, seg)
        ctrl.pixel_buffer[idx] = (
            int(color[0] * factor * wave),
            int(color[1] * factor * wave),
            int(color[2] * factor * wave),
        )


def effect_dynamic(ctrl, seg):
    """Sparse random sparkles that fade over time."""
    now = utime.ticks_ms()
    speed = seg["sx"]
    intensity = seg["ix"]

    # probability scaled by intensity and speed
    chance = max(1, (speed + intensity) // 8)
    levels = seg.get("_dyn_levels")
    colors = seg.get("_dyn_colors")
    if levels is None or colors is None or len(levels) != seg["len"]:
        levels = [0] * seg["len"]
        colors = [(0, 0, 0)] * seg["len"]
        seg["_dyn_levels"] = levels
        seg["_dyn_colors"] = colors

    # spawn a few sparkles
    for _ in range(chance // 8 + 1):
        if _randint(0, 255) < chance:
            pos = _randint(0, seg["len"] - 1)
            levels[pos] = 255
            colors[pos] = ctrl._get_palette_color(seg["pal"], _randint(0, 255), seg)

    decay = max(4, 12 - (speed // 24))
    for i in range(seg["len"]):
        if levels[i] > 0:
            levels[i] = max(0, levels[i] - decay)

    factor = seg["_current_bri"] / 255.0
    for i in range(seg["len"]):
        idx = seg["start"] + i
        level = levels[i] / 255.0
        color = colors[i]
        ctrl.pixel_buffer[idx] = (
            int(color[0] * factor * level),
            int(color[1] * factor * level),
            int(color[2] * factor * level),
        )


def effect_saw(ctrl, seg):
    """Sawtooth gradient sliding across the strip."""
    now = utime.ticks_ms()
    speed = seg["sx"]
    intensity = seg["ix"]

    cycle = 30 + (255 - speed) * 4
    phase = (now % cycle) / cycle
    factor = seg["_current_bri"] / 255.0

    for i in range(seg["len"]):
        idx = seg["start"] + i
        remapped_i = ctrl._remap_pixel_index(i, seg)
        pos = (remapped_i / max(1, seg["len"])) + phase
        pos = pos % 1.0
        # steeper slope with intensity
        pos = pow(pos, 1.0 + (255 - intensity) / 255.0)
        hue = int(pos * 255) & 0xFF
        color = ctrl._get_palette_color(seg["pal"], hue, seg)
        ctrl.pixel_buffer[idx] = (
            int(color[0] * factor),
            int(color[1] * factor),
            int(color[2] * factor),
        )


def effect_twinkle(ctrl, seg):
    """Random twinkles that fade out."""
    now = utime.ticks_ms()
    speed = seg["sx"]
    intensity = seg["ix"]

    levels = seg.get("_tw_levels")
    colors = seg.get("_tw_colors")
    if levels is None or colors is None or len(levels) != seg["len"]:
        levels = [0] * seg["len"]
        colors = [(0, 0, 0)] * seg["len"]
        seg["_tw_levels"] = levels
        seg["_tw_colors"] = colors

    # spawn probability
    chance = max(1, (speed // 4) + (intensity // 6))
    if _randint(0, 255) < chance:
        pos = _randint(0, seg["len"] - 1)
        levels[pos] = 255
        colors[pos] = ctrl._get_palette_color(seg["pal"], _randint(0, 255), seg)

    decay = max(3, 10 - (speed // 32))
    for i in range(seg["len"]):
        if levels[i] > 0:
            levels[i] = max(0, levels[i] - decay)

    factor = seg["_current_bri"] / 255.0
    for i in range(seg["len"]):
        idx = seg["start"] + i
        level = levels[i] / 255.0
        color = colors[i]
        ctrl.pixel_buffer[idx] = (
            int(color[0] * factor * level),
            int(color[1] * factor * level),
            int(color[2] * factor * level),
        )


def effect_blink(ctrl, seg):
    """Blink effect with palette support and duty-cycle from intensity."""
    now = utime.ticks_ms()
    frame_ms = 20  # approximate upstream FRAMETIME
    cycle_ms = (255 - seg["sx"]) * 20
    on_ms = frame_ms + ((cycle_ms * seg["ix"]) >> 8)
    cycle_ms += frame_ms * 2

    iteration = now // cycle_ms
    rem = now % cycle_ms
    last_iter = seg.get("_blink_step", -1)
    on_phase = (iteration != last_iter) or (rem <= on_ms)
    seg["_blink_step"] = iteration

    brightness = seg["_current_bri"]
    factor = brightness / 255.0
    palette_active = seg["pal"] not in [0, 2, 4] and seg["pal"] in wledpalettes.PALETTE_DATA

    if on_phase:
        if palette_active:
            for i in range(seg["start"], seg["stop"]):
                local_i = i - seg["start"]
                pal_color = wledpalettes.color_from_palette(seg, local_i, ctrl._remap_pixel_index)
                if pal_color is None:
                    ctrl.pixel_buffer[i] = (0, 0, 0)
                    continue
                r = int(pal_color[0] * factor)
                g = int(pal_color[1] * factor)
                b = int(pal_color[2] * factor)
                ctrl.pixel_buffer[i] = (r, g, b)
        else:
            r = int(seg["col"][0][0] * factor)
            g = int(seg["col"][0][1] * factor)
            b = int(seg["col"][0][2] * factor)
            color_tuple = (r, g, b)
            for i in range(seg["start"], seg["stop"]):
                ctrl.pixel_buffer[i] = color_tuple
    else:
        # Off phase uses secondary color without palette sampling
        r = int(seg["col"][1][0] * factor)
        g = int(seg["col"][1][1] * factor)
        b = int(seg["col"][1][2] * factor)
        color_tuple = (r, g, b)
        for i in range(seg["start"], seg["stop"]):
            ctrl.pixel_buffer[i] = color_tuple


def effect_breathe(ctrl, seg):
    """Breathe waveform with palette mix between primary and secondary."""
    now = utime.ticks_ms()
    counter = (now * ((seg["sx"] >> 3) + 10)) & 0xFFFF
    counter = (counter >> 2) + (counter >> 4)
    var = 0
    if counter < 16384:
        if counter > 8192:
            counter = 8192 - (counter - 8192)
        var = int(math.sin((counter * 2 * math.pi) / 65535) * 32767 / 103)
    lum = 30 + var
    lum = max(0, min(255, lum))

    brightness_factor = seg["_current_bri"] / 255.0 if seg["_current_bri"] > 0 else 0
    palette_active = seg["pal"] not in [0, 2, 4] and seg["pal"] in wledpalettes.PALETTE_DATA

    for i in range(seg["start"], seg["stop"]):
        local_i = i - seg["start"]
        if palette_active:
            base_color = wledpalettes.color_from_palette(seg, local_i, ctrl._remap_pixel_index)
            if base_color is None:
                ctrl.pixel_buffer[i] = (0, 0, 0)
                continue
        else:
            base_color = seg["col"][0]

        blended = wledpalettes.color_blend(seg["col"][1], base_color, lum)
        r = int(blended[0] * brightness_factor)
        g = int(blended[1] * brightness_factor)
        b = int(blended[2] * brightness_factor)
        ctrl.pixel_buffer[i] = (r, g, b)


def _sparkle_common(ctrl, seg, sparkles=1, dark_background=False):
    """Shared sparkle helper; sparkles count controls how many pixels light up."""
    now = utime.ticks_ms()
    speed = seg["sx"]
    intensity = seg["ix"]

    # Background color
    base = seg["col"][1] if dark_background else seg["col"][0]
    factor = seg["_current_bri"] / 255.0
    base_color = (
        int(base[0] * factor * 0.1),
        int(base[1] * factor * 0.1),
        int(base[2] * factor * 0.1),
    )

    # Decide if we should spawn sparkles this frame
    chance = max(1, (speed + intensity) // 6)
    spawn = _randint(0, 255) < chance

    # fade existing sparkles
    levels = seg.get("_sp_levels")
    colors = seg.get("_sp_colors")
    if levels is None or colors is None or len(levels) != seg["len"]:
        levels = [0] * seg["len"]
        colors = [(0, 0, 0)] * seg["len"]
        seg["_sp_levels"] = levels
        seg["_sp_colors"] = colors

    decay = max(8, 18 - (speed // 18))
    for i in range(seg["len"]):
        if levels[i] > 0:
            levels[i] = max(0, levels[i] - decay)

    if spawn:
        for _ in range(sparkles):
            pos = _randint(0, seg["len"] - 1)
            levels[pos] = 255
            colors[pos] = ctrl._get_palette_color(seg["pal"], _randint(0, 255), seg)

    for i in range(seg["len"]):
        idx = seg["start"] + i
        level = levels[i] / 255.0
        if level <= 0:
            ctrl.pixel_buffer[idx] = base_color if dark_background else base_color
            continue
        color = colors[i]
        ctrl.pixel_buffer[idx] = (
            int(color[0] * factor * level),
            int(color[1] * factor * level),
            int(color[2] * factor * level),
        )


def effect_sparkle(ctrl, seg):
    """Single sparkle over dim background."""
    _sparkle_common(ctrl, seg, sparkles=1, dark_background=False)


def effect_sparkle_dark(ctrl, seg):
    """Single sparkle over dark background (uses secondary color as base)."""
    _sparkle_common(ctrl, seg, sparkles=1, dark_background=True)


def effect_sparkle_plus(ctrl, seg):
    """Multiple sparkles for denser look."""
    _sparkle_common(ctrl, seg, sparkles=3, dark_background=False)


def effect_strobe(ctrl, seg):
    """Periodic full-strip strobe."""
    now = utime.ticks_ms()
    speed = seg["sx"]
    intensity = seg["ix"]

    cycle = max(40, 200 - speed)
    on_time = max(5, (intensity // 8))

    phase = now % cycle
    factor = seg["_current_bri"] / 255.0
    color = ctrl._get_palette_color(seg["pal"], 0, seg)
    active = phase < on_time

    val = (
        int(color[0] * factor) if active else 0,
        int(color[1] * factor) if active else 0,
        int(color[2] * factor) if active else 0,
    )
    for i in range(seg["start"], seg["stop"]):
        ctrl.pixel_buffer[i] = val


def effect_fade(ctrl, seg):
    """Smoothly fade between primary and secondary colors."""
    now = utime.ticks_ms()
    speed = seg["sx"]
    intensity = seg["ix"]

    cycle = 1500 + (255 - speed) * 8
    phase = ((now % cycle) / cycle) * 2 * math.pi
    wave = (math.sin(phase) + 1) / 2  # 0..1

    # Intensity biases toward primary or secondary; 128 is neutral
    bias = (intensity - 128) / 128.0
    wave = min(1.0, max(0.0, wave + (bias * 0.25)))

    factor = seg["_current_bri"] / 255.0
    c1 = seg["col"][0]
    c2 = seg["col"][1]
    blended = (
        int(c1[0] + (c2[0] - c1[0]) * wave),
        int(c1[1] + (c2[1] - c1[1]) * wave),
        int(c1[2] + (c2[2] - c1[2]) * wave),
    )

    color = (
        int(blended[0] * factor),
        int(blended[1] * factor),
        int(blended[2] * factor),
    )
    for i in range(seg["start"], seg["stop"]):
        ctrl.pixel_buffer[i] = color


def effect_running(ctrl, seg):
    """Single running light with a short fading tail."""
    now = utime.ticks_ms()
    speed = seg["sx"]
    intensity = seg["ix"]

    cycle = 20 + (255 - speed) * 6
    pos = int((now % cycle) * seg["len"] / cycle)
    tail = max(1, 1 + (intensity >> 5))  # 1..8

    factor = seg["_current_bri"] / 255.0

    for i in range(seg["len"]):
        idx = seg["start"] + i
        remapped_i = ctrl._remap_pixel_index(i, seg)
        dist = (remapped_i - pos) % seg["len"]
        if dist == 0:
            level = 1.0
        elif dist < tail:
            level = (tail - dist) / tail
        else:
            level = 0.0
        if level <= 0:
            ctrl.pixel_buffer[idx] = (0, 0, 0)
            continue
        color = ctrl._get_palette_color(seg["pal"], (remapped_i * 255 // seg["len"]) & 255, seg)
        ctrl.pixel_buffer[idx] = (
            int(color[0] * factor * level),
            int(color[1] * factor * level),
            int(color[2] * factor * level),
        )


# Mapping of effect IDs to handlers, plus exported metadata used by the controller.
EFFECT_HANDLERS = {
    1: effect_blink,
    2: effect_breathe,
    3: effect_color_wipe,
    4: effect_wipe_random,
    5: effect_random_colors,
    6: effect_sweep,
    7: effect_dynamic,
    8: effect_rainbow,
    9: effect_rainbow,
    10: effect_scan,
    11: effect_scan_dual,
    12: effect_fade,
    13: effect_theater_chase,
    14: effect_theater_rainbow,
    15: effect_running,
    16: effect_saw,
    17: effect_twinkle,
    # Map unsupported dissolve slots to the closest available twinkle-style effect
    18: effect_twinkle,
    19: effect_random_colors,
    20: effect_sparkle,
    21: effect_sparkle_dark,
    22: effect_sparkle_plus,
    23: effect_strobe,
}

# Keep the effect list aligned to the handlers we actually ship so we
# don't advertise IDs that would otherwise fall back to a solid fill.
SUPPORTED_EFFECTS = (
    "Solid",
    "Blink",
    "Breathe",
    "Wipe",
    "Wipe Random",
    "Random Colors",
    "Sweep",
    "Dynamic",
    "Colorloop",
    "Rainbow",
    "Scan",
    "Scan Dual",
    "Fade",
    "Theater",
    "Theater Rainbow",
    "Running",
    "Saw",
    "Twinkle",
    "Dissolve",
    "Dissolve Rnd",
    "Sparkle",
    "Sparkle Dark",
    "Sparkle+",
    "Strobe",
)

# Graceful fallback for any effect ID we haven't implemented; pick a
# colourful animation instead of silently returning a solid color.
DEFAULT_EFFECT_ID = 8  # Colorloop/Rainbow


def resolve_effect_handler(effect_id: int):
    """Return an available handler or a graceful fallback."""
    if effect_id <= 0:
        return None
    handler = EFFECT_HANDLERS.get(effect_id)
    if handler:
        return handler
    return EFFECT_HANDLERS.get(DEFAULT_EFFECT_ID)
