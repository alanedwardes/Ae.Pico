import array
import uctypes
import micropython
import machine
import _thread
import time
from machine import Pin
from rp2 import PIO, StateMachine, DMA, asm_pio


@micropython.viper
def convert_row_565(dst: ptr32, source: ptr16, src_row_offset: int, src_width: int, out_words: int, idx_lut: ptr32, scratch: ptr16):
    total_out_pixels = out_words * 2
    if total_out_pixels == src_width:
        s = src_row_offset
        d = 0
        n = out_words
        while n >= 4:
            p0 = int(source[s]); p1 = int(source[s + 1])
            dst[d] = ((p0 >> 11) | (p0 & 0x7C0) | ((p0 & 0x1F) << 11)) | \
                     (((p1 >> 11) | (p1 & 0x7C0) | ((p1 & 0x1F) << 11)) << 16)
            p0 = int(source[s + 2]); p1 = int(source[s + 3])
            dst[d + 1] = ((p0 >> 11) | (p0 & 0x7C0) | ((p0 & 0x1F) << 11)) | \
                         (((p1 >> 11) | (p1 & 0x7C0) | ((p1 & 0x1F) << 11)) << 16)
            p0 = int(source[s + 4]); p1 = int(source[s + 5])
            dst[d + 2] = ((p0 >> 11) | (p0 & 0x7C0) | ((p0 & 0x1F) << 11)) | \
                         (((p1 >> 11) | (p1 & 0x7C0) | ((p1 & 0x1F) << 11)) << 16)
            p0 = int(source[s + 6]); p1 = int(source[s + 7])
            dst[d + 3] = ((p0 >> 11) | (p0 & 0x7C0) | ((p0 & 0x1F) << 11)) | \
                         (((p1 >> 11) | (p1 & 0x7C0) | ((p1 & 0x1F) << 11)) << 16)
            s += 8; d += 4; n -= 4
        while n:
            p0 = int(source[s]); p1 = int(source[s + 1])
            dst[d] = ((p0 >> 11) | (p0 & 0x7C0) | ((p0 & 0x1F) << 11)) | \
                     (((p1 >> 11) | (p1 & 0x7C0) | ((p1 & 0x1F) << 11)) << 16)
            s += 2; d += 1; n -= 1
        return

    w = 0
    while w + 4 <= out_words:
        packed = idx_lut[w]
        p0 = int(source[src_row_offset + (packed & 0xFFFF)]); p1 = int(source[src_row_offset + (packed >> 16)])
        dst[w] = ((p0 >> 11) | (p0 & 0x7C0) | ((p0 & 0x1F) << 11)) | \
                 (((p1 >> 11) | (p1 & 0x7C0) | ((p1 & 0x1F) << 11)) << 16)
        packed = idx_lut[w + 1]
        p0 = int(source[src_row_offset + (packed & 0xFFFF)]); p1 = int(source[src_row_offset + (packed >> 16)])
        dst[w + 1] = ((p0 >> 11) | (p0 & 0x7C0) | ((p0 & 0x1F) << 11)) | \
                      (((p1 >> 11) | (p1 & 0x7C0) | ((p1 & 0x1F) << 11)) << 16)
        packed = idx_lut[w + 2]
        p0 = int(source[src_row_offset + (packed & 0xFFFF)]); p1 = int(source[src_row_offset + (packed >> 16)])
        dst[w + 2] = ((p0 >> 11) | (p0 & 0x7C0) | ((p0 & 0x1F) << 11)) | \
                      (((p1 >> 11) | (p1 & 0x7C0) | ((p1 & 0x1F) << 11)) << 16)
        packed = idx_lut[w + 3]
        p0 = int(source[src_row_offset + (packed & 0xFFFF)]); p1 = int(source[src_row_offset + (packed >> 16)])
        dst[w + 3] = ((p0 >> 11) | (p0 & 0x7C0) | ((p0 & 0x1F) << 11)) | \
                      (((p1 >> 11) | (p1 & 0x7C0) | ((p1 & 0x1F) << 11)) << 16)
        w += 4
    while w < out_words:
        packed = idx_lut[w]
        p0 = int(source[src_row_offset + (packed & 0xFFFF)]); p1 = int(source[src_row_offset + (packed >> 16)])
        dst[w] = ((p0 >> 11) | (p0 & 0x7C0) | ((p0 & 0x1F) << 11)) | \
                 (((p1 >> 11) | (p1 & 0x7C0) | ((p1 & 0x1F) << 11)) << 16)
        w += 1


def build_rgb332_dac_lut_into(lut):
    for i in range(256):
        r3 = (i >> 5) & 7
        g3 = (i >> 2) & 7
        b2 = i & 3
        r5 = (r3 << 2) | (r3 >> 1)
        g5 = (g3 << 2) | (g3 >> 1)
        b5 = (b2 << 3) | (b2 << 1) | (b2 >> 1)
        lut[i] = r5 | (g5 << 6) | (b5 << 11)


@micropython.viper
def convert_row_332(dst: ptr32, source: ptr8, src_row_offset: int, src_width: int, out_words: int, lut: ptr16, idx_lut: ptr32, scratch: ptr8):
    total_out_pixels = out_words * 2
    if total_out_pixels == src_width:
        s = src_row_offset
        d = 0
        n = out_words
        while n >= 4:
            dst[d] = int(lut[source[s]]) | (int(lut[source[s + 1]]) << 16)
            dst[d + 1] = int(lut[source[s + 2]]) | (int(lut[source[s + 3]]) << 16)
            dst[d + 2] = int(lut[source[s + 4]]) | (int(lut[source[s + 5]]) << 16)
            dst[d + 3] = int(lut[source[s + 6]]) | (int(lut[source[s + 7]]) << 16)
            s += 8; d += 4; n -= 4
        while n:
            dst[d] = int(lut[source[s]]) | (int(lut[source[s + 1]]) << 16)
            s += 2; d += 1; n -= 1
        return

    w = 0
    while w + 4 <= out_words:
        packed = idx_lut[w]
        dst[w] = int(lut[source[src_row_offset + (packed & 0xFFFF)]]) | (int(lut[source[src_row_offset + (packed >> 16)]]) << 16)
        packed = idx_lut[w + 1]
        dst[w + 1] = int(lut[source[src_row_offset + (packed & 0xFFFF)]]) | (int(lut[source[src_row_offset + (packed >> 16)]]) << 16)
        packed = idx_lut[w + 2]
        dst[w + 2] = int(lut[source[src_row_offset + (packed & 0xFFFF)]]) | (int(lut[source[src_row_offset + (packed >> 16)]]) << 16)
        packed = idx_lut[w + 3]
        dst[w + 3] = int(lut[source[src_row_offset + (packed & 0xFFFF)]]) | (int(lut[source[src_row_offset + (packed >> 16)]]) << 16)
        w += 4
    while w < out_words:
        packed = idx_lut[w]
        dst[w] = int(lut[source[src_row_offset + (packed & 0xFFFF)]]) | (int(lut[source[src_row_offset + (packed >> 16)]]) << 16)
        w += 1


@micropython.viper
def core1_loop_viper_565(state: ptr32, done: ptr32,
                      pool_addr_tbl: ptr32, fb: ptr16,
                      ch_ctrl_reg_addr: int, table_addr: int, table_len: int,
                      pool_size: int, src_width: int, src_height: int,
                      active_start_offset: int, v_active: int,
                      sio_gpio_in_addr: int, vsync_pin_mask: int,
                      frame_log: ptr32, log_len: int,
                      ch_pixel_reg_addr: int, pool_base_addr: int, buf_stride_bytes: int,
                      margin_target: int,
                      tail_log: ptr32, tail_log_len: int, tail_threshold: int,
                      idx_lut: ptr32, scratch: ptr16,
                      row_correctness: ptr32,
                      pattern_log: ptr32, pattern_len: int):
    gpio_in = ptr32(sio_gpio_in_addr)
    ctrl_reg = ptr32(ch_ctrl_reg_addr)
    pixel_reg = ptr32(ch_pixel_reg_addr)
    last_table_idx = -1
    last_vsync_high = 1
    lines_since_vsync = 0
    call_count = 0
    edge_reset_count = 0
    frame_count = 0
    need_log = 0
    min_margin = pool_size
    collision_count = 0
    out_of_range_count = 0
    tail_call_count = 0
    prefill_next = pool_size
    prefill_incomplete_count = 0
    entries_per_buffer = table_len // pool_size
    exact_ratio = 1 if v_active % src_height == 0 else 0
    settle_threshold = table_len * 2
    pattern_pos = 0
    while state[1] == 0:
        vsync_high = 1 if (gpio_in[0] & vsync_pin_mask) != 0 else 0
        next_table_idx = (ctrl_reg[0] - table_addr) >> 2
        displaying_table_idx = (next_table_idx - 1) % table_len

        if last_vsync_high == 1 and vsync_high == 0:
            lines_since_vsync = 0
            edge_reset_count += 1
            state[2] = edge_reset_count
            need_log = 1
            prefill_next = 0
        last_vsync_high = vsync_high

        if displaying_table_idx == last_table_idx:
            continue
        lines_since_vsync += (displaying_table_idx - last_table_idx) % table_len
        last_table_idx = displaying_table_idx

        lines_into_active = lines_since_vsync - active_start_offset
        if lines_into_active < 0:
            if prefill_next < pool_size and (displaying_table_idx * pool_size) // table_len != prefill_next:
                pf_dst_addr = pool_addr_tbl[prefill_next]
                convert_row_565(ptr32(pf_dst_addr), fb, prefill_next * src_width, src_width, buf_stride_bytes // 4, idx_lut, scratch)
                row_correctness[prefill_next] = prefill_next
                prefill_next += 1
            continue
        if lines_into_active >= v_active:
            continue

        if need_log == 1:
            if prefill_next < pool_size:
                prefill_incomplete_count += 1
                state[7] = prefill_incomplete_count
            frame_log[(frame_count % log_len) * 2] = lines_into_active
            frame_log[(frame_count % log_len) * 2 + 1] = displaying_table_idx
            frame_count += 1
            need_log = 0

        current_row = (lines_into_active * src_height) // v_active
        displaying_buffer = (displaying_table_idx * pool_size) // table_len
        if lines_into_active >= settle_threshold:
            row_correctness[pool_size + 1] += 1
            row_delta = current_row - row_correctness[displaying_buffer]
            if pattern_pos < pattern_len:
                slot = pattern_pos * 4
                pattern_log[slot] = lines_into_active
                pattern_log[slot + 1] = current_row
                pattern_log[slot + 2] = displaying_buffer
                pattern_log[slot + 3] = row_correctness[displaying_buffer]
                pattern_pos += 1
            if row_delta != 0:
                row_correctness[pool_size] += 1
                if row_delta < 0:
                    row_delta = -row_delta
                if row_delta > row_correctness[pool_size + 8]:
                    row_correctness[pool_size + 8] = row_delta
                if row_delta > 2:
                    row_correctness[pool_size + 9] += 1
                if row_correctness[pool_size + 2] == 0:
                    row_correctness[pool_size + 2] = 1
                    row_correctness[pool_size + 3] = lines_into_active
                    row_correctness[pool_size + 4] = current_row
                    row_correctness[pool_size + 5] = displaying_buffer
                    row_correctness[pool_size + 6] = row_correctness[displaying_buffer]
                    row_correctness[pool_size + 7] = displaying_table_idx
        safe_buffer = (displaying_buffer - margin_target) % pool_size
        if exact_ratio:
            delta = (safe_buffer - current_row) % pool_size
            target_row = current_row + delta
        else:
            target_table_idx_start = safe_buffer * entries_per_buffer
            steps = (target_table_idx_start - displaying_table_idx) % table_len
            future_lines_into_active = lines_into_active + steps
            target_row = (future_lines_into_active * src_height) // v_active
        if target_row >= src_height:
            target_row = src_height - 1

        if lines_into_active >= tail_threshold:
            slot = tail_call_count % tail_log_len
            tail_log[slot * 5] = lines_into_active
            tail_log[slot * 5 + 1] = current_row
            tail_log[slot * 5 + 2] = displaying_buffer
            tail_log[slot * 5 + 3] = safe_buffer
            tail_log[slot * 5 + 4] = target_row
            tail_call_count += 1

        pixel_read_addr = pixel_reg[0]
        actual_buf = (pixel_read_addr - pool_base_addr) // buf_stride_bytes
        if actual_buf < 0 or actual_buf >= pool_size:
            out_of_range_count += 1
        else:
            margin = (actual_buf - safe_buffer) % pool_size
            if margin < min_margin:
                min_margin = margin
                state[6] = lines_into_active
            if margin == 0:
                collision_count += 1
        state[3] = min_margin
        state[4] = collision_count
        state[5] = out_of_range_count

        if actual_buf != safe_buffer:
            src_offset = target_row * src_width
            dst_addr = pool_addr_tbl[safe_buffer]
            convert_row_565(ptr32(dst_addr), fb, src_offset, src_width, buf_stride_bytes // 4, idx_lut, scratch)
            row_correctness[safe_buffer] = target_row

        call_count += 1
        state[0] = call_count
    done[0] = 1


@micropython.viper
def core1_loop_viper_332(state: ptr32, done: ptr32,
                      pool_addr_tbl: ptr32, fb: ptr8,
                      ch_ctrl_reg_addr: int, table_addr: int, table_len: int,
                      pool_size: int, src_width: int, src_height: int,
                      active_start_offset: int, v_active: int,
                      sio_gpio_in_addr: int, vsync_pin_mask: int,
                      frame_log: ptr32, log_len: int,
                      ch_pixel_reg_addr: int, pool_base_addr: int, buf_stride_bytes: int,
                      margin_target: int,
                      tail_log: ptr32, tail_log_len: int, tail_threshold: int,
                      lut: ptr16, idx_lut: ptr32, scratch: ptr8,
                      row_correctness: ptr32,
                      pattern_log: ptr32, pattern_len: int):
    gpio_in = ptr32(sio_gpio_in_addr)
    ctrl_reg = ptr32(ch_ctrl_reg_addr)
    pixel_reg = ptr32(ch_pixel_reg_addr)
    last_table_idx = -1
    last_vsync_high = 1
    lines_since_vsync = 0
    call_count = 0
    edge_reset_count = 0
    frame_count = 0
    need_log = 0
    min_margin = pool_size
    collision_count = 0
    out_of_range_count = 0
    tail_call_count = 0
    prefill_next = pool_size
    prefill_incomplete_count = 0
    entries_per_buffer = table_len // pool_size
    exact_ratio = 1 if v_active % src_height == 0 else 0
    settle_threshold = table_len * 2
    pattern_pos = 0
    while state[1] == 0:
        vsync_high = 1 if (gpio_in[0] & vsync_pin_mask) != 0 else 0
        next_table_idx = (ctrl_reg[0] - table_addr) >> 2
        displaying_table_idx = (next_table_idx - 1) % table_len

        if last_vsync_high == 1 and vsync_high == 0:
            lines_since_vsync = 0
            edge_reset_count += 1
            state[2] = edge_reset_count
            need_log = 1
            prefill_next = 0
        last_vsync_high = vsync_high

        if displaying_table_idx == last_table_idx:
            continue
        lines_since_vsync += (displaying_table_idx - last_table_idx) % table_len
        last_table_idx = displaying_table_idx

        lines_into_active = lines_since_vsync - active_start_offset
        if lines_into_active < 0:
            if prefill_next < pool_size and (displaying_table_idx * pool_size) // table_len != prefill_next:
                pf_dst_addr = pool_addr_tbl[prefill_next]
                convert_row_332(ptr32(pf_dst_addr), fb, prefill_next * src_width, src_width, buf_stride_bytes // 4, lut, idx_lut, scratch)
                row_correctness[prefill_next] = prefill_next
                prefill_next += 1
            continue
        if lines_into_active >= v_active:
            continue

        if need_log == 1:
            if prefill_next < pool_size:
                prefill_incomplete_count += 1
                state[7] = prefill_incomplete_count
            frame_log[(frame_count % log_len) * 2] = lines_into_active
            frame_log[(frame_count % log_len) * 2 + 1] = displaying_table_idx
            frame_count += 1
            need_log = 0

        current_row = (lines_into_active * src_height) // v_active
        displaying_buffer = (displaying_table_idx * pool_size) // table_len
        if lines_into_active >= settle_threshold:
            row_correctness[pool_size + 1] += 1
            row_delta = current_row - row_correctness[displaying_buffer]
            if pattern_pos < pattern_len:
                slot = pattern_pos * 4
                pattern_log[slot] = lines_into_active
                pattern_log[slot + 1] = current_row
                pattern_log[slot + 2] = displaying_buffer
                pattern_log[slot + 3] = row_correctness[displaying_buffer]
                pattern_pos += 1
            if row_delta != 0:
                row_correctness[pool_size] += 1
                if row_delta < 0:
                    row_delta = -row_delta
                if row_delta > row_correctness[pool_size + 8]:
                    row_correctness[pool_size + 8] = row_delta
                if row_delta > 2:
                    row_correctness[pool_size + 9] += 1
                if row_correctness[pool_size + 2] == 0:
                    row_correctness[pool_size + 2] = 1
                    row_correctness[pool_size + 3] = lines_into_active
                    row_correctness[pool_size + 4] = current_row
                    row_correctness[pool_size + 5] = displaying_buffer
                    row_correctness[pool_size + 6] = row_correctness[displaying_buffer]
                    row_correctness[pool_size + 7] = displaying_table_idx
        safe_buffer = (displaying_buffer - margin_target) % pool_size
        if exact_ratio:
            delta = (safe_buffer - current_row) % pool_size
            target_row = current_row + delta
        else:
            target_table_idx_start = safe_buffer * entries_per_buffer
            steps = (target_table_idx_start - displaying_table_idx) % table_len
            future_lines_into_active = lines_into_active + steps
            target_row = (future_lines_into_active * src_height) // v_active
        if target_row >= src_height:
            target_row = src_height - 1

        if lines_into_active >= tail_threshold:
            slot = tail_call_count % tail_log_len
            tail_log[slot * 5] = lines_into_active
            tail_log[slot * 5 + 1] = current_row
            tail_log[slot * 5 + 2] = displaying_buffer
            tail_log[slot * 5 + 3] = safe_buffer
            tail_log[slot * 5 + 4] = target_row
            tail_call_count += 1

        pixel_read_addr = pixel_reg[0]
        actual_buf = (pixel_read_addr - pool_base_addr) // buf_stride_bytes
        if actual_buf < 0 or actual_buf >= pool_size:
            out_of_range_count += 1
        else:
            margin = (actual_buf - safe_buffer) % pool_size
            if margin < min_margin:
                min_margin = margin
                state[6] = lines_into_active
            if margin == 0:
                collision_count += 1
        state[3] = min_margin
        state[4] = collision_count
        state[5] = out_of_range_count

        if actual_buf != safe_buffer:
            src_offset = target_row * src_width
            dst_addr = pool_addr_tbl[safe_buffer]
            convert_row_332(ptr32(dst_addr), fb, src_offset, src_width, buf_stride_bytes // 4, lut, idx_lut, scratch)
            row_correctness[safe_buffer] = target_row

        call_count += 1
        state[0] = call_count
    done[0] = 1


def _flat_loop_solve(target):
    for x in range(32):
        for delay in range(32):
            if (x + 1) * (1 + delay) == target:
                return (x, delay)
    return None


def _nested_loop_solve(target):
    for outer_x in range(32):
        outer_n = outer_x + 1
        for outer_delay in range(32):
            remainder = target - outer_n * (2 + outer_delay)
            if remainder <= 0 or remainder % outer_n != 0:
                continue
            inner = _flat_loop_solve(remainder // outer_n)
            if inner is not None:
                return (outer_x, outer_delay, inner[0], inner[1])
    return None


def _closest_flat_loop(target):
    best = None
    for x in range(32):
        for delay in range(32):
            v = (x + 1) * (1 + delay)
            dev = v - target
            if best is None or abs(dev) < abs(best[0]):
                best = (dev, x, delay)
    return best


def solve_hsync_segment(segment_total, max_flat_deviation=0):
    loop_target = segment_total - 2
    flat = _flat_loop_solve(loop_target)
    if flat is not None:
        return ('flat', flat, 0)
    if max_flat_deviation > 0:
        dev, x, delay = _closest_flat_loop(loop_target)
        if abs(dev) <= max_flat_deviation:
            return ('flat', (x, delay), dev)
    nested = _nested_loop_solve(loop_target)
    if nested is not None:
        return ('nested', nested, 0)
    raise ValueError('no flat or nested loop hits segment_total=%d exactly' % segment_total)


def make_hsync_prog(pulse_total, idle_total, pulse_level=0, idle_level=1, max_flat_deviation=0):
    pulse_kind, pulse_params, pulse_dev = solve_hsync_segment(pulse_total, max_flat_deviation)
    idle_kind, idle_params, idle_dev = solve_hsync_segment(idle_total, max_flat_deviation)
    total_deviation = pulse_dev + idle_dev
    set_init = PIO.OUT_HIGH if idle_level else PIO.OUT_LOW

    if pulse_kind == 'flat' and idle_kind == 'flat':
        px, pd = pulse_params
        ix, idl = idle_params

        @asm_pio(set_init=set_init)
        def hsync_prog():
            wrap_target()
            irq(0)
            irq(1)
            set(pins, pulse_level)
            set(x, px)
            label("pulse")
            jmp(x_dec, "pulse")         [pd]
            set(pins, idle_level)
            set(x, ix)
            label("idle")
            jmp(x_dec, "idle")          [idl]
            wrap()
        return hsync_prog, total_deviation

    if pulse_kind == 'flat' and idle_kind == 'nested':
        px, pd = pulse_params
        iox, iod, iix, iid = idle_params

        @asm_pio(set_init=set_init)
        def hsync_prog():
            wrap_target()
            irq(0)
            irq(1)
            set(pins, pulse_level)
            set(x, px)
            label("pulse")
            jmp(x_dec, "pulse")         [pd]
            set(pins, idle_level)
            set(x, iox)
            label("idle_outer")
            set(y, iix)
            label("idle_inner")
            jmp(y_dec, "idle_inner")    [iid]
            jmp(x_dec, "idle_outer")    [iod]
            wrap()
        return hsync_prog, total_deviation

    if pulse_kind == 'nested' and idle_kind == 'flat':
        pox, pod, pix, pid = pulse_params
        ix, idl = idle_params

        @asm_pio(set_init=set_init)
        def hsync_prog():
            wrap_target()
            irq(0)
            irq(1)
            set(pins, pulse_level)
            set(x, pox)
            label("pulse_outer")
            set(y, pix)
            label("pulse_inner")
            jmp(y_dec, "pulse_inner")   [pid]
            jmp(x_dec, "pulse_outer")   [pod]
            set(pins, idle_level)
            set(x, ix)
            label("idle")
            jmp(x_dec, "idle")          [idl]
            wrap()
        return hsync_prog, total_deviation

    pox, pod, pix, pid = pulse_params
    iox, iod, iix, iid = idle_params

    @asm_pio(set_init=set_init)
    def hsync_prog():
        wrap_target()
        irq(0)
        irq(1)
        set(pins, pulse_level)
        set(x, pox)
        label("pulse_outer")
        set(y, pix)
        label("pulse_inner")
        jmp(y_dec, "pulse_inner")   [pid]
        jmp(x_dec, "pulse_outer")   [pod]
        set(pins, idle_level)
        set(x, iox)
        label("idle_outer")
        set(y, iix)
        label("idle_inner")
        jmp(y_dec, "idle_inner")    [iid]
        jmp(x_dec, "idle_outer")    [iod]
        wrap()
    return hsync_prog, total_deviation


def solve_color_back_porch(loop_target, max_flat_deviation=4):
    flat = _flat_loop_solve(loop_target)
    if flat is not None:
        return ('flat', flat, 0)
    if max_flat_deviation > 0:
        dev, x, delay = _closest_flat_loop(loop_target)
        if abs(dev) <= max_flat_deviation:
            return ('flat', (x, delay), dev)
    nested = _nested_loop_solve(loop_target)
    if nested is not None:
        return ('nested', nested, 0)
    raise ValueError('no flat or nested loop hits color back-porch target=%d' % loop_target)


def make_color_prog(h_sync, h_back_porch, max_flat_deviation=4):
    back_porch_loop_target = h_sync + h_back_porch - 1
    kind, params, deviation = solve_color_back_porch(back_porch_loop_target, max_flat_deviation)

    if kind == 'flat':
        bx, bd = params

        @asm_pio(out_init=(PIO.OUT_LOW,) * 16, out_shiftdir=PIO.SHIFT_RIGHT)
        def color_prog():
            pull(block)
            mov(isr, osr)

            wrap_target()

            wait(1, irq, 0)
            set(x, bx)
            label("a_p1")
            jmp(x_dec, "a_p1")          [bd]

            mov(x, isr)
            label("pxloop")
            pull(block)
            out(pins, 16)
            out(pins, 16)
            jmp(x_dec, "pxloop")

            mov(pins, null)

            wrap()
        return color_prog, deviation

    box, bod, bix, bid = params

    @asm_pio(out_init=(PIO.OUT_LOW,) * 16, out_shiftdir=PIO.SHIFT_RIGHT)
    def color_prog():
        pull(block)
        mov(isr, osr)

        wrap_target()

        wait(1, irq, 0)
        set(x, box)
        label("a_p1_outer")
        set(y, bix)
        label("a_p1_inner")
        jmp(y_dec, "a_p1_inner")    [bid]
        jmp(x_dec, "a_p1_outer")    [bod]

        mov(x, isr)
        label("pxloop")
        pull(block)
        out(pins, 16)
        out(pins, 16)
        jmp(x_dec, "pxloop")

        mov(pins, null)

        wrap()
    return color_prog, deviation


def make_vsync_prog(v_pulse_minus_1, pulse_level=0, idle_level=1):
    set_init = PIO.OUT_HIGH if idle_level else PIO.OUT_LOW

    @asm_pio(sideset_init=set_init)
    def vsync_prog():
        pull(block)
        mov(x, osr)
        pull(block)

        wrap_target()

        mov(isr, x)
        push(noblock)

        set(y, v_pulse_minus_1)
        label("pulse_line")
        wait(1, irq, 1)              .side(pulse_level)
        jmp(y_dec, "pulse_line")

        mov(y, osr)
        label("idle_line")
        wait(1, irq, 1)              .side(idle_level)
        jmp(y_dec, "idle_line")

        wrap()
    return vsync_prog


TIMINGS = {
    '640x480': dict(
        pixel_clock=25_175_000, h_sync=96, h_back_porch=48, h_active=640, h_front_porch=16,
        v_pulse=2, v_back_porch=33, v_active=480, v_front_porch=10, sync_positive=False,
    ),
    '800x600': dict(
        pixel_clock=40_000_000, h_sync=128, h_back_porch=88, h_active=800, h_front_porch=40,
        v_pulse=4, v_back_porch=23, v_active=600, v_front_porch=1, sync_positive=True,
    ),
    '1024x768': dict(
        pixel_clock=65_000_000, h_sync=136, h_back_porch=160, h_active=1024, h_front_porch=24,
        v_pulse=6, v_back_porch=29, v_active=768, v_front_porch=3, sync_positive=False,
        h_sync_max_deviation=2,
    ),
    '1280x960': dict(
        pixel_clock=108_000_000, h_sync=112, h_back_porch=312, h_active=1280, h_front_porch=96,
        v_pulse=3, v_back_porch=36, v_active=960, v_front_porch=1, sync_positive=True,
    ),
    '1280x1024': dict(
        pixel_clock=108_000_000, h_sync=112, h_back_porch=248, h_active=1280, h_front_porch=48,
        v_pulse=3, v_back_porch=38, v_active=1024, v_front_porch=1, sync_positive=True,
    ),
    '1280x720': dict(
        pixel_clock=74_250_000, h_sync=40, h_back_porch=220, h_active=1280, h_front_porch=110,
        v_pulse=5, v_back_porch=20, v_active=720, v_front_porch=5, sync_positive=True,
    ),
}


class VGA:
    SIO_GPIO_IN = 0xd0000004
    VSYNC_PIN_MASK = 1 << 17
    PIXEL_CLOCK = 25_175_000
    DREQ_PIO0_TX0 = 0
    DREQ_PIO0_RX0 = 4
    DMA_BASE = 0x50000000
    DMA_CH_STRIDE = 0x40
    DMA_AL3_READ_ADDR_TRIG_OFFSET = 0x3C
    H_SYNC = 96
    H_BACK_PORCH = 48
    H_ACTIVE = 640
    H_FRONT_PORCH = 16
    V_PULSE = 2
    V_BACK_PORCH = 33
    V_ACTIVE = 480
    V_FRONT_PORCH = 10
    POOL_SIZE = 8
    MARGIN = POOL_SIZE // 2

    def __init__(self, framebuffer, width, height, hsync_pin=16, color_base_pin=0, vsync_pin=17,
                 source_color_mode='RGB565', timing=None,
                 pixel_clock=None, h_sync=None, h_back_porch=None, h_active=None, h_front_porch=None,
                 v_pulse=None, v_back_porch=None, v_active=None, v_front_porch=None,
                 sync_positive=None, h_sync_max_deviation=None):
        if timing is not None:
            if timing not in TIMINGS:
                raise ValueError('unknown timing preset %r - known: %s' % (timing, sorted(TIMINGS)))
            preset = TIMINGS[timing]
            if pixel_clock is None: pixel_clock = preset.get('pixel_clock')
            if h_sync is None: h_sync = preset.get('h_sync')
            if h_back_porch is None: h_back_porch = preset.get('h_back_porch')
            if h_active is None: h_active = preset.get('h_active')
            if h_front_porch is None: h_front_porch = preset.get('h_front_porch')
            if v_pulse is None: v_pulse = preset.get('v_pulse')
            if v_back_porch is None: v_back_porch = preset.get('v_back_porch')
            if v_active is None: v_active = preset.get('v_active')
            if v_front_porch is None: v_front_porch = preset.get('v_front_porch')
            if sync_positive is None: sync_positive = preset.get('sync_positive')
            if h_sync_max_deviation is None: h_sync_max_deviation = preset.get('h_sync_max_deviation')
        if sync_positive is None: sync_positive = False
        if h_sync_max_deviation is None: h_sync_max_deviation = 0
        self._h_sync_max_deviation = h_sync_max_deviation
        self.width = width
        self.height = height
        self.source_color_mode = source_color_mode
        self._is_rgb565 = source_color_mode == 'RGB565'
        self.bytes_per_pixel = 2 if self._is_rgb565 else 1
        self._framebuffer = framebuffer
        self._fb_addr = uctypes.addressof(framebuffer)

        self._core1_state = array.array('i', [0, 0, 0, 0, 0, 0, -1, 0])
        self._core1_done = array.array('i', [0])
        self._started = False

        self._hsync_pin = hsync_pin
        self._color_base_pin = color_base_pin
        self._vsync_pin = vsync_pin

        if pixel_clock is not None: self.PIXEL_CLOCK = pixel_clock
        if h_sync is not None: self.H_SYNC = h_sync
        if h_back_porch is not None: self.H_BACK_PORCH = h_back_porch
        if h_active is not None: self.H_ACTIVE = h_active
        if h_front_porch is not None: self.H_FRONT_PORCH = h_front_porch
        if v_pulse is not None: self.V_PULSE = v_pulse
        if v_back_porch is not None: self.V_BACK_PORCH = v_back_porch
        if v_active is not None: self.V_ACTIVE = v_active
        if v_front_porch is not None: self.V_FRONT_PORCH = v_front_porch
        self.V_TOTAL = self.V_PULSE + self.V_BACK_PORCH + self.V_ACTIVE + self.V_FRONT_PORCH
        self.V_IDLE = self.V_TOTAL - self.V_PULSE
        self._pulse_level = 1 if sync_positive else 0
        self._idle_level = 0 if sync_positive else 1

        if not self._is_rgb565:
            self._rgb332_lut = array.array('H', bytearray(256 * 2))
            build_rgb332_dac_lut_into(self._rgb332_lut)

    def _compute_table_len(self, pool_size, src_height):
        raw_table_len = pool_size * self.V_ACTIVE // src_height
        table_len = 1
        while table_len < raw_table_len:
            table_len *= 2
        if table_len > 1:
            lower = table_len // 2
            if 2 * pool_size * self.V_ACTIVE < (lower + table_len) * src_height:
                table_len = lower
        return table_len

    def _alloc_scanline_pool(self, pool_size, words_per_line):
        pool = array.array('I', bytearray(pool_size * words_per_line * 4))
        pool_addr = uctypes.addressof(pool)
        pool_addrs = [pool_addr + b * words_per_line * 4 for b in range(pool_size)]
        pool_addr_arr = array.array('I', pool_addrs)
        self._pool = pool
        return pool_addrs, pool_addr_arr

    def _build_index_lut(self, src_width, words_per_line):
        total_out_pixels = words_per_line * 2
        idx_lut = array.array('I', bytearray(words_per_line * 4))
        for w in range(words_per_line):
            s0 = (w * 2 * src_width) // total_out_pixels
            s1 = (w * 2 + 1) * src_width // total_out_pixels
            idx_lut[w] = s0 | (s1 << 16)
        self._idx_lut = idx_lut
        return uctypes.addressof(idx_lut)

    def _alloc_scratch_row(self, src_width):
        if self._is_rgb565:
            scratch = array.array('H', bytearray(src_width * 2))
        else:
            scratch = array.array('B', bytearray(src_width))
        self._scratch = scratch
        return uctypes.addressof(scratch)

    def _prefill_pool(self, pool_addrs, pool_size, src_width, words_per_line, idx_lut_addr, scratch_addr):
        fb_addr = self._fb_addr
        if self._is_rgb565:
            for b in range(pool_size):
                src_offset = b * src_width
                convert_row_565(pool_addrs[b], fb_addr, src_offset, src_width, words_per_line, idx_lut_addr, scratch_addr)
        else:
            lut_addr = uctypes.addressof(self._rgb332_lut)
            for b in range(pool_size):
                src_offset = b * src_width
                convert_row_332(pool_addrs[b], fb_addr, src_offset, src_width, words_per_line, lut_addr, idx_lut_addr, scratch_addr)

    def _build_scanout_table(self, table_len, pool_size, pool_addrs):
        addr_table_bytes = table_len * 4
        ring_size_bits = 0
        while (1 << ring_size_bits) < addr_table_bytes:
            ring_size_bits += 1
        raw = array.array('I', bytearray(table_len * 2 * 4))
        raw_addr = uctypes.addressof(raw)
        aligned_addr = (raw_addr + addr_table_bytes - 1) & ~(addr_table_bytes - 1)
        offset_words = (aligned_addr - raw_addr) // 4
        for i in range(table_len):
            raw[offset_words + i] = pool_addrs[(i * pool_size) // table_len]
        self._raw = raw
        return aligned_addr, ring_size_bits

    def _start_video_pipeline(self, feed, table_addr, table_len, ring_size_bits, pool_addrs, words_per_line):
        H_TOTAL = self.H_SYNC + self.H_BACK_PORCH + self.H_ACTIVE + self.H_FRONT_PORCH
        hsync_prog, hsync_deviation_cycles = make_hsync_prog(
            self.H_SYNC, H_TOTAL - self.H_SYNC, self._pulse_level, self._idle_level,
            max_flat_deviation=self._h_sync_max_deviation)
        self.hsync_deviation_cycles = hsync_deviation_cycles
        hsync_sm = StateMachine(0, hsync_prog, freq=self.PIXEL_CLOCK, set_base=Pin(self._hsync_pin))
        color_prog, color_back_porch_deviation_cycles = make_color_prog(self.H_SYNC, self.H_BACK_PORCH)
        self.color_back_porch_deviation_cycles = color_back_porch_deviation_cycles
        color_sm = StateMachine(1, color_prog, freq=self.PIXEL_CLOCK, out_base=Pin(self._color_base_pin))
        vsync_sm = StateMachine(2, make_vsync_prog(self.V_PULSE - 1, self._pulse_level, self._idle_level), freq=self.PIXEL_CLOCK, sideset_base=Pin(self._vsync_pin))
        self._hsync_sm = hsync_sm
        self._color_sm = color_sm
        self._vsync_sm = vsync_sm
        feed()

        ch_pixel = DMA()
        ch_ctrl = DMA()
        ch_vreset = DMA()
        self._ch_pixel = ch_pixel
        self._ch_ctrl = ch_ctrl
        self._ch_vreset = ch_vreset
        feed()

        ch_pixel_al3_trig_addr = self.DMA_BASE + ch_pixel.channel * self.DMA_CH_STRIDE + self.DMA_AL3_READ_ADDR_TRIG_OFFSET
        ch_ctrl_read_addr_reg = self.DMA_BASE + ch_ctrl.channel * self.DMA_CH_STRIDE + 0x00

        ctrl_pixel = ch_pixel.pack_ctrl(size=2, inc_read=True, inc_write=False,
                                         treq_sel=self.DREQ_PIO0_TX0 + 1,
                                         chain_to=ch_ctrl.channel,
                                         high_pri=True)
        ctrl_ctrl = ch_ctrl.pack_ctrl(size=2, inc_read=True, inc_write=False,
                                       treq_sel=0x3F,
                                       chain_to=ch_ctrl.channel,
                                       ring_sel=False, ring_size=ring_size_bits,
                                       high_pri=True)
        ctrl_vreset = ch_vreset.pack_ctrl(size=2, inc_read=False, inc_write=False,
                                           treq_sel=self.DREQ_PIO0_RX0 + 2,
                                           chain_to=ch_vreset.channel,
                                           high_pri=True)

        ch_pixel.config(read=pool_addrs[0], write=color_sm, count=words_per_line, ctrl=ctrl_pixel, trigger=False)
        ch_ctrl.config(read=table_addr, write=ch_pixel_al3_trig_addr, count=1, ctrl=ctrl_ctrl, trigger=False)
        feed()

        color_sm.active(1)
        color_sm.put(words_per_line - 1)
        feed()

        unconditional_line_advances_before_active = self.V_PULSE + self.V_BACK_PORCH
        start_idx_landing_on_0_at_active = (-unconditional_line_advances_before_active) % table_len
        vsync_sm.active(1)
        vsync_sm.put(table_addr + start_idx_landing_on_0_at_active * 4)
        vsync_sm.put(self.V_IDLE - 1)
        feed()

        ch_vreset.config(read=vsync_sm, write=ch_ctrl_read_addr_reg, count=10_000_000, ctrl=ctrl_vreset, trigger=True)
        feed()
        ch_ctrl.active(1)
        hsync_sm.active(1)
        feed()

        ch_ctrl_reg_addr = self.DMA_BASE + ch_ctrl.channel * self.DMA_CH_STRIDE + 0x00
        ch_pixel_reg_addr = self.DMA_BASE + ch_pixel.channel * self.DMA_CH_STRIDE + 0x00
        return ch_ctrl_reg_addr, ch_pixel_reg_addr

    def _alloc_diagnostics(self, pool_size):
        log_len = 64
        self.frame_log = array.array('i', bytearray(log_len * 2 * 4))
        tail_log_len = 40
        tail_threshold = 450
        self.tail_log = array.array('i', bytearray(tail_log_len * 5 * 4))
        self.row_correctness = array.array('i', bytearray((pool_size + 10) * 4))
        pattern_len = 400
        self.pattern_log = array.array('i', bytearray(pattern_len * 4 * 4))
        return log_len, tail_log_len, tail_threshold, pattern_len

    def _start_core1_thread(self, pool_addr_arr, ch_ctrl_reg_addr, table_addr, table_len, pool_size,
                             src_width, src_height, active_start_offset, ch_pixel_reg_addr,
                             pool_base_addr, buf_stride_bytes, log_len, tail_log_len, tail_threshold,
                             idx_lut_addr, scratch_addr, pattern_len):
        row_correctness_addr = uctypes.addressof(self.row_correctness)
        pattern_log_addr = uctypes.addressof(self.pattern_log)
        common_args = (
            self._core1_state, self._core1_done,
            pool_addr_arr, self._framebuffer,
            ch_ctrl_reg_addr, table_addr, table_len,
            pool_size, src_width, src_height,
            active_start_offset, self.V_ACTIVE,
            self.SIO_GPIO_IN, self.VSYNC_PIN_MASK,
            self.frame_log, log_len,
            ch_pixel_reg_addr, pool_base_addr, buf_stride_bytes,
            self.MARGIN,
            self.tail_log, tail_log_len, tail_threshold,
        )
        if self._is_rgb565:
            _thread.start_new_thread(core1_loop_viper_565, common_args + (
                idx_lut_addr, scratch_addr,
                row_correctness_addr,
                pattern_log_addr, pattern_len,
            ))
        else:
            _thread.start_new_thread(core1_loop_viper_332, common_args + (
                uctypes.addressof(self._rgb332_lut), idx_lut_addr, scratch_addr,
                row_correctness_addr,
                pattern_log_addr, pattern_len,
            ))

    def start(self, wdt=None):
        if self._started:
            return
        self._started = True

        assert machine.freq() == 240_000_000

        def feed():
            if wdt is not None:
                wdt.feed()

        POOL_SIZE = self.POOL_SIZE
        SRC_WIDTH = self.width
        SRC_HEIGHT = self.height
        assert self.H_ACTIVE % 4 == 0
        WORDS_PER_LINE = self.H_ACTIVE // 4
        self._words_per_line = WORDS_PER_LINE
        assert SRC_HEIGHT % POOL_SIZE == 0, (
            'SRC_HEIGHT must be a multiple of POOL_SIZE - the pool of '
            'scanline buffers cycles through the whole framebuffer height '
            'in fixed POOL_SIZE-row groups')

        TABLE_LEN = self._compute_table_len(POOL_SIZE, SRC_HEIGHT)
        feed()

        pool_addrs, pool_addr_arr = self._alloc_scanline_pool(POOL_SIZE, WORDS_PER_LINE)
        feed()

        idx_lut_addr = self._build_index_lut(SRC_WIDTH, WORDS_PER_LINE)
        feed()

        scratch_addr = self._alloc_scratch_row(SRC_WIDTH)
        feed()

        self._prefill_pool(pool_addrs, POOL_SIZE, SRC_WIDTH, WORDS_PER_LINE, idx_lut_addr, scratch_addr)
        feed()

        table_addr, ring_size_bits = self._build_scanout_table(TABLE_LEN, POOL_SIZE, pool_addrs)
        feed()

        ch_ctrl_reg_addr, ch_pixel_reg_addr = self._start_video_pipeline(
            feed, table_addr, TABLE_LEN, ring_size_bits, pool_addrs, WORDS_PER_LINE)

        buf_stride_bytes = WORDS_PER_LINE * 4
        active_start_offset = self.V_PULSE + self.V_BACK_PORCH

        LOG_LEN, TAIL_LOG_LEN, TAIL_THRESHOLD, PATTERN_LEN = self._alloc_diagnostics(POOL_SIZE)
        feed()

        self._start_core1_thread(
            pool_addr_arr, ch_ctrl_reg_addr, table_addr, TABLE_LEN, POOL_SIZE, SRC_WIDTH, SRC_HEIGHT,
            active_start_offset, ch_pixel_reg_addr, pool_addrs[0], buf_stride_bytes,
            LOG_LEN, TAIL_LOG_LEN, TAIL_THRESHOLD, idx_lut_addr, scratch_addr, PATTERN_LEN)
        feed()

    def render(self, fb, width, height, bbox):
        pass

    def get_bounds(self):
        return (self.width, self.height)

    def set_backlight(self, brightness):
        pass

    def stop(self):
        if not self._started:
            return
        self._core1_state[1] = 1
        stop_wait_start = time.ticks_ms()
        while self._core1_done[0] == 0 and time.ticks_diff(time.ticks_ms(), stop_wait_start) < 2000:
            time.sleep_ms(10)
        self._hsync_sm.active(0)
        self._color_sm.active(0)
        self._vsync_sm.active(0)
        CHAN_ABORT = self.DMA_BASE + 0x444
        abort_mask = (1 << self._ch_pixel.channel) | (1 << self._ch_ctrl.channel) | (1 << self._ch_vreset.channel)
        machine.mem32[CHAN_ABORT] = abort_mask
        self._ch_ctrl.active(0)
        self._ch_pixel.active(0)
        self._ch_vreset.active(0)
        self._started = False
