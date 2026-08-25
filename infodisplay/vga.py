import array
import uctypes
import micropython
from collections import namedtuple
import machine
import _thread
import time
from machine import Pin
from micropython import const
from rp2 import PIO, StateMachine, DMA, asm_pio

_VSR_CH_CTRL_READ_ADDR_REGISTER = const(0)
_VSR_RESET_TARGET_TABLE_ADDR = const(1)
_VSR_RESET_LINE_IDX = const(2)
_VSR_LINE_IDX = const(3)
_VSR_V_TOTAL = const(4)
_VSR_HANDLER_CALL_COUNT = const(5)
_VSR_RESET_WRITE_COUNT = const(6)
_VSR_LINE_IDX_AT_VSYNC = const(7)
_VSR_LINE_IDX_AT_VSYNC_MAX_ABS = const(8)
_VSR_EDGE_PROBE_COUNT = const(9)
_VSR_VSYNC_PIN_MASK = const(10)
_VSR_VSYNC_ASSERTED_HIGH = const(11)
_VSR_LAST_VSYNC_ASSERTED = const(12)
_VSR_RESET_DONE_THIS_FRAME = const(13)
_VSR_REANCHOR_COUNT = const(14)

_SIO_GPIO_IN_ADDR = const(0xd0000004)

_vsync_reset_shared = array.array('i', [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
_vsync_reset_shared_addr = uctypes.addressof(_vsync_reset_shared)


@micropython.viper
def _vsync_reset_irq_handler(dma_obj):
    shared = ptr32(int(_vsync_reset_shared_addr))
    shared[_VSR_HANDLER_CALL_COUNT] += 1
    gpio_in = ptr32(int(_SIO_GPIO_IN_ADDR))
    vsync_level = 1 if (gpio_in[0] & shared[_VSR_VSYNC_PIN_MASK]) != 0 else 0
    vsync_asserted = 1 if vsync_level == shared[_VSR_VSYNC_ASSERTED_HIGH] else 0
    if shared[_VSR_LAST_VSYNC_ASSERTED] == 0 and vsync_asserted == 1:
        shared[_VSR_LAST_VSYNC_ASSERTED] = 1
        line_idx = 0
        shared[_VSR_RESET_DONE_THIS_FRAME] = 0
        shared[_VSR_REANCHOR_COUNT] += 1
    else:
        shared[_VSR_LAST_VSYNC_ASSERTED] = vsync_asserted
        line_idx = shared[_VSR_LINE_IDX] + 1
        if line_idx >= shared[_VSR_V_TOTAL]:
            line_idx = 0
    shared[_VSR_LINE_IDX] = line_idx

    ctrl_reg = ptr32(shared[_VSR_CH_CTRL_READ_ADDR_REGISTER])
    if line_idx == shared[_VSR_RESET_LINE_IDX] and shared[_VSR_RESET_DONE_THIS_FRAME] == 0:
        ctrl_reg[0] = shared[_VSR_RESET_TARGET_TABLE_ADDR]
        shared[_VSR_RESET_WRITE_COUNT] += 1
        shared[_VSR_RESET_DONE_THIS_FRAME] = 1


_CS_REFILL_CALL_COUNT = const(0)
_CS_STOP_REQUESTED = const(1)
_CS_VSYNC_EDGE_COUNT = const(2)
_CS_MIN_REFILL_MARGIN_BUFFERS = const(3)
_CS_REFILL_TARGET_COLLISION_COUNT = const(4)
_CS_DISPLAYING_BUFFER_OUT_OF_RANGE_COUNT = const(5)
_CS_MIN_REFILL_MARGIN_LINES_INTO_ACTIVE = const(6)
_CS_PREFILL_BURST_INCOMPLETE_COUNT = const(7)
_CS_TABLE_ADVANCE_JUMP_COUNT = const(8)
_CS_MAX_TABLE_ADVANCE = const(9)
_CS_CATCH_UP_COUNT = const(10)

_CORE1_STATE_INITIAL = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
_CORE1_STATE_INITIAL[_CS_MIN_REFILL_MARGIN_LINES_INTO_ACTIVE] = -1

_RC_MISMATCH_COUNT = const(0)
_RC_CHECKED_COUNT = const(1)
_RC_FIRST_MISMATCH_SEEN = const(2)
_RC_FIRST_MISMATCH_LINES_INTO_ACTIVE = const(3)
_RC_FIRST_MISMATCH_CURRENT_ROW = const(4)
_RC_FIRST_MISMATCH_DISPLAYING_BUFFER = const(5)
_RC_FIRST_MISMATCH_STORED_ROW = const(6)
_RC_FIRST_MISMATCH_TABLE_IDX = const(7)
_RC_MAX_ABS_ROW_DELTA = const(8)
_RC_LARGE_ROW_DELTA_COUNT = const(9)

_JUMP_ADVANCE_HIST_LEN = const(8)


@micropython.viper
def convert_row_565(dst: ptr32, source: ptr16, src_row_offset: int, out_words: int, h_dup: int):
    s = src_row_offset
    d = 0
    n = out_words
    if h_dup == 2:
        while n >= 4:
            p = int(source[s]); v = (p >> 11) | (p & 0x7C0) | ((p & 0x1F) << 11)
            dst[d] = v | (v << 16)
            p = int(source[s + 1]); v = (p >> 11) | (p & 0x7C0) | ((p & 0x1F) << 11)
            dst[d + 1] = v | (v << 16)
            p = int(source[s + 2]); v = (p >> 11) | (p & 0x7C0) | ((p & 0x1F) << 11)
            dst[d + 2] = v | (v << 16)
            p = int(source[s + 3]); v = (p >> 11) | (p & 0x7C0) | ((p & 0x1F) << 11)
            dst[d + 3] = v | (v << 16)
            s += 4; d += 4; n -= 4
        while n:
            p = int(source[s]); v = (p >> 11) | (p & 0x7C0) | ((p & 0x1F) << 11)
            dst[d] = v | (v << 16)
            s += 1; d += 1; n -= 1
    elif h_dup == 4:
        while n >= 4:
            p = int(source[s]); v = (p >> 11) | (p & 0x7C0) | ((p & 0x1F) << 11)
            dst[d] = v | (v << 16); dst[d + 1] = v | (v << 16)
            p = int(source[s + 1]); v = (p >> 11) | (p & 0x7C0) | ((p & 0x1F) << 11)
            dst[d + 2] = v | (v << 16); dst[d + 3] = v | (v << 16)
            s += 2; d += 4; n -= 4
        while n >= 2:
            p = int(source[s]); v = (p >> 11) | (p & 0x7C0) | ((p & 0x1F) << 11)
            dst[d] = v | (v << 16); dst[d + 1] = v | (v << 16)
            s += 1; d += 2; n -= 2
    else:
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
def convert_row_332(dst: ptr32, source: ptr8, src_row_offset: int, out_words: int, lut: ptr16, h_dup: int):
    s = src_row_offset
    d = 0
    n = out_words
    if h_dup == 2:
        while n >= 4:
            v = int(lut[source[s]]); dst[d] = v | (v << 16)
            v = int(lut[source[s + 1]]); dst[d + 1] = v | (v << 16)
            v = int(lut[source[s + 2]]); dst[d + 2] = v | (v << 16)
            v = int(lut[source[s + 3]]); dst[d + 3] = v | (v << 16)
            s += 4; d += 4; n -= 4
        while n:
            v = int(lut[source[s]]); dst[d] = v | (v << 16)
            s += 1; d += 1; n -= 1
    elif h_dup == 4:
        while n >= 4:
            v = int(lut[source[s]]); dst[d] = v | (v << 16); dst[d + 1] = v | (v << 16)
            v = int(lut[source[s + 1]]); dst[d + 2] = v | (v << 16); dst[d + 3] = v | (v << 16)
            s += 2; d += 4; n -= 4
        while n >= 2:
            v = int(lut[source[s]]); dst[d] = v | (v << 16); dst[d + 1] = v | (v << 16)
            s += 1; d += 2; n -= 2
    else:
        while n >= 4:
            dst[d] = int(lut[source[s]]) | (int(lut[source[s + 1]]) << 16)
            dst[d + 1] = int(lut[source[s + 2]]) | (int(lut[source[s + 3]]) << 16)
            dst[d + 2] = int(lut[source[s + 4]]) | (int(lut[source[s + 5]]) << 16)
            dst[d + 3] = int(lut[source[s + 6]]) | (int(lut[source[s + 7]]) << 16)
            s += 8; d += 4; n -= 4
        while n:
            dst[d] = int(lut[source[s]]) | (int(lut[source[s + 1]]) << 16)
            s += 2; d += 1; n -= 1


@micropython.viper
def core1_loop_viper_565(state: ptr32, done: ptr32,
                      pool_addr_tbl: ptr32, fb: ptr16,
                      ch_ctrl_reg_addr: int, table_addr: int, table_len: int,
                      pool_size: int, src_width: int, src_height: int,
                      active_start_offset: int, v_active: int,
                      sio_gpio_in_addr: int, vsync_pin_mask: int,
                      frame_log: ptr32, log_len: int,
                      ch_pixel_reg_addr: int, pool_base_addr: int, buffer_stride_bytes: int,
                      margin_target: int,
                      tail_log: ptr32, tail_log_len: int, tail_threshold: int,
                      h_dup: int,
                      row_correctness: ptr32,
                      pattern_log: ptr32, pattern_len: int,
                      irq_shared: ptr32,
                      jump_advance_hist: ptr32):
    gpio_in = ptr32(sio_gpio_in_addr)
    ctrl_reg = ptr32(ch_ctrl_reg_addr)
    pixel_reg = ptr32(ch_pixel_reg_addr)
    last_table_idx = -1
    last_vsync_high = 1
    last_lines_since_vsync = irq_shared[_VSR_LINE_IDX]
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
    exact_ratio = 1 if entries_per_buffer * src_height == v_active else 0
    settle_threshold = table_len * 2
    pattern_pos = 0
    jump_count = 0
    max_table_advance = 0
    catch_up_count = 0
    prev_safe_buffer = -1
    content_words = (buffer_stride_bytes >> 2) - int(COLOR_PROG_LINE_COUNT_WORDS)
    while state[_CS_STOP_REQUESTED] == 0:
        vsync_high = 1 if (gpio_in[0] & vsync_pin_mask) != 0 else 0
        if last_vsync_high == 1 and vsync_high == 0:
            edge_reset_count += 1
            state[_CS_VSYNC_EDGE_COUNT] = edge_reset_count
            probe_li = irq_shared[_VSR_LINE_IDX]
            irq_shared[_VSR_LINE_IDX_AT_VSYNC] = probe_li
            vt = irq_shared[_VSR_V_TOTAL]
            probe_dev = probe_li if probe_li < vt - probe_li else vt - probe_li
            if probe_dev > irq_shared[_VSR_LINE_IDX_AT_VSYNC_MAX_ABS]:
                irq_shared[_VSR_LINE_IDX_AT_VSYNC_MAX_ABS] = probe_dev
            irq_shared[_VSR_EDGE_PROBE_COUNT] += 1
        last_vsync_high = vsync_high

        next_table_idx = (ctrl_reg[0] - table_addr) >> 2
        displaying_table_idx = (next_table_idx - 1) % table_len

        lines_since_vsync = irq_shared[_VSR_LINE_IDX]
        if lines_since_vsync < last_lines_since_vsync:
            need_log = 1
            prefill_next = 0
        last_lines_since_vsync = lines_since_vsync

        if displaying_table_idx == last_table_idx:
            continue
        prev_table_idx = last_table_idx
        last_table_idx = displaying_table_idx

        lines_into_active = lines_since_vsync - active_start_offset
        if lines_into_active < 0:
            if prefill_next < pool_size and (displaying_table_idx * pool_size) // table_len != prefill_next:
                pf_dst_addr = pool_addr_tbl[prefill_next]
                convert_row_565(ptr32(pf_dst_addr + int(COLOR_PROG_LINE_COUNT_WORDS) * 4), fb, prefill_next * src_width, content_words, h_dup)
                row_correctness[prefill_next] = prefill_next
                prefill_next += 1
            prev_safe_buffer = -1
            continue
        if lines_into_active >= v_active:
            prev_safe_buffer = -1
            continue

        if prev_table_idx >= 0:
            table_advance = (displaying_table_idx - prev_table_idx) % table_len
            if table_advance < _JUMP_ADVANCE_HIST_LEN:
                jump_advance_hist[table_advance] += 1
            if table_advance > 1:
                jump_count += 1
                state[_CS_TABLE_ADVANCE_JUMP_COUNT] = jump_count
            if table_advance > max_table_advance:
                max_table_advance = table_advance
                state[_CS_MAX_TABLE_ADVANCE] = max_table_advance

        if need_log == 1:
            if prefill_next < pool_size:
                prefill_incomplete_count += 1
                state[_CS_PREFILL_BURST_INCOMPLETE_COUNT] = prefill_incomplete_count
            frame_log[(frame_count % log_len) * 2] = lines_into_active
            frame_log[(frame_count % log_len) * 2 + 1] = displaying_table_idx
            frame_count += 1
            need_log = 0

        current_row = (lines_into_active * src_height) // v_active
        displaying_buffer = (displaying_table_idx * pool_size) // table_len
        if lines_into_active >= settle_threshold:
            row_correctness[pool_size + _RC_CHECKED_COUNT] += 1
            row_delta = current_row - row_correctness[displaying_buffer]
            if pattern_pos < pattern_len:
                slot = pattern_pos * 4
                pattern_log[slot] = lines_into_active
                pattern_log[slot + 1] = current_row
                pattern_log[slot + 2] = displaying_buffer
                pattern_log[slot + 3] = row_correctness[displaying_buffer]
                pattern_pos += 1
            if row_delta != 0:
                row_correctness[pool_size + _RC_MISMATCH_COUNT] += 1
                if row_delta < 0:
                    row_delta = -row_delta
                if row_delta > row_correctness[pool_size + _RC_MAX_ABS_ROW_DELTA]:
                    row_correctness[pool_size + _RC_MAX_ABS_ROW_DELTA] = row_delta
                if row_delta > 2:
                    row_correctness[pool_size + _RC_LARGE_ROW_DELTA_COUNT] += 1
                if row_correctness[pool_size + _RC_FIRST_MISMATCH_SEEN] == 0:
                    row_correctness[pool_size + _RC_FIRST_MISMATCH_SEEN] = 1
                    row_correctness[pool_size + _RC_FIRST_MISMATCH_LINES_INTO_ACTIVE] = lines_into_active
                    row_correctness[pool_size + _RC_FIRST_MISMATCH_CURRENT_ROW] = current_row
                    row_correctness[pool_size + _RC_FIRST_MISMATCH_DISPLAYING_BUFFER] = displaying_buffer
                    row_correctness[pool_size + _RC_FIRST_MISMATCH_STORED_ROW] = row_correctness[displaying_buffer]
                    row_correctness[pool_size + _RC_FIRST_MISMATCH_TABLE_IDX] = displaying_table_idx
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
        actual_buffer = (pixel_read_addr - pool_base_addr) // buffer_stride_bytes
        if actual_buffer < 0 or actual_buffer >= pool_size:
            out_of_range_count += 1
        else:
            margin = (actual_buffer - safe_buffer) % pool_size
            if margin < min_margin:
                min_margin = margin
                state[_CS_MIN_REFILL_MARGIN_LINES_INTO_ACTIVE] = lines_into_active
            if margin == 0:
                collision_count += 1
        state[_CS_MIN_REFILL_MARGIN_BUFFERS] = min_margin
        state[_CS_REFILL_TARGET_COLLISION_COUNT] = collision_count
        state[_CS_DISPLAYING_BUFFER_OUT_OF_RANGE_COUNT] = out_of_range_count

        if actual_buffer != safe_buffer:
            src_offset = target_row * src_width
            dst_addr = pool_addr_tbl[safe_buffer]
            convert_row_565(ptr32(dst_addr + int(COLOR_PROG_LINE_COUNT_WORDS) * 4), fb, src_offset, content_words, h_dup)
            row_correctness[safe_buffer] = target_row

        if prev_safe_buffer >= 0:
            missed_safe_gap = (safe_buffer - prev_safe_buffer) % pool_size
            if missed_safe_gap > 1:
                catch_up_buffer = (prev_safe_buffer + 1) % pool_size
                if catch_up_buffer != actual_buffer:
                    if exact_ratio:
                        catch_up_target_row = current_row + (catch_up_buffer - current_row) % pool_size
                    else:
                        catch_up_table_idx_start = catch_up_buffer * entries_per_buffer
                        catch_up_steps = (catch_up_table_idx_start - displaying_table_idx) % table_len
                        catch_up_future = lines_into_active + catch_up_steps
                        catch_up_target_row = (catch_up_future * src_height) // v_active
                    if catch_up_target_row >= src_height:
                        catch_up_target_row = src_height - 1
                    catch_up_src_offset = catch_up_target_row * src_width
                    catch_up_dst_addr = pool_addr_tbl[catch_up_buffer]
                    convert_row_565(ptr32(catch_up_dst_addr + int(COLOR_PROG_LINE_COUNT_WORDS) * 4), fb, catch_up_src_offset, content_words, h_dup)
                    row_correctness[catch_up_buffer] = catch_up_target_row
                    catch_up_count += 1
                    state[_CS_CATCH_UP_COUNT] = catch_up_count
        prev_safe_buffer = safe_buffer

        call_count += 1
        state[_CS_REFILL_CALL_COUNT] = call_count
    done[0] = 1


@micropython.viper
def core1_loop_viper_332(state: ptr32, done: ptr32,
                      pool_addr_tbl: ptr32, fb: ptr8,
                      ch_ctrl_reg_addr: int, table_addr: int, table_len: int,
                      pool_size: int, src_width: int, src_height: int,
                      active_start_offset: int, v_active: int,
                      sio_gpio_in_addr: int, vsync_pin_mask: int,
                      frame_log: ptr32, log_len: int,
                      ch_pixel_reg_addr: int, pool_base_addr: int, buffer_stride_bytes: int,
                      margin_target: int,
                      tail_log: ptr32, tail_log_len: int, tail_threshold: int,
                      h_dup: int,
                      lut: ptr16,
                      row_correctness: ptr32,
                      pattern_log: ptr32, pattern_len: int,
                      irq_shared: ptr32,
                      jump_advance_hist: ptr32):
    gpio_in = ptr32(sio_gpio_in_addr)
    ctrl_reg = ptr32(ch_ctrl_reg_addr)
    pixel_reg = ptr32(ch_pixel_reg_addr)
    last_table_idx = -1
    last_vsync_high = 1
    last_lines_since_vsync = irq_shared[_VSR_LINE_IDX]
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
    exact_ratio = 1 if entries_per_buffer * src_height == v_active else 0
    settle_threshold = table_len * 2
    pattern_pos = 0
    jump_count = 0
    max_table_advance = 0
    catch_up_count = 0
    prev_safe_buffer = -1
    content_words = (buffer_stride_bytes >> 2) - int(COLOR_PROG_LINE_COUNT_WORDS)
    while state[_CS_STOP_REQUESTED] == 0:
        vsync_high = 1 if (gpio_in[0] & vsync_pin_mask) != 0 else 0
        if last_vsync_high == 1 and vsync_high == 0:
            edge_reset_count += 1
            state[_CS_VSYNC_EDGE_COUNT] = edge_reset_count
            probe_li = irq_shared[_VSR_LINE_IDX]
            irq_shared[_VSR_LINE_IDX_AT_VSYNC] = probe_li
            vt = irq_shared[_VSR_V_TOTAL]
            probe_dev = probe_li if probe_li < vt - probe_li else vt - probe_li
            if probe_dev > irq_shared[_VSR_LINE_IDX_AT_VSYNC_MAX_ABS]:
                irq_shared[_VSR_LINE_IDX_AT_VSYNC_MAX_ABS] = probe_dev
            irq_shared[_VSR_EDGE_PROBE_COUNT] += 1
        last_vsync_high = vsync_high

        next_table_idx = (ctrl_reg[0] - table_addr) >> 2
        displaying_table_idx = (next_table_idx - 1) % table_len

        lines_since_vsync = irq_shared[_VSR_LINE_IDX]
        if lines_since_vsync < last_lines_since_vsync:
            need_log = 1
            prefill_next = 0
        last_lines_since_vsync = lines_since_vsync

        if displaying_table_idx == last_table_idx:
            continue
        prev_table_idx = last_table_idx
        last_table_idx = displaying_table_idx

        lines_into_active = lines_since_vsync - active_start_offset
        if lines_into_active < 0:
            if prefill_next < pool_size and (displaying_table_idx * pool_size) // table_len != prefill_next:
                pf_dst_addr = pool_addr_tbl[prefill_next]
                convert_row_332(ptr32(pf_dst_addr + int(COLOR_PROG_LINE_COUNT_WORDS) * 4), fb, prefill_next * src_width, content_words, lut, h_dup)
                row_correctness[prefill_next] = prefill_next
                prefill_next += 1
            prev_safe_buffer = -1
            continue
        if lines_into_active >= v_active:
            prev_safe_buffer = -1
            continue

        if prev_table_idx >= 0:
            table_advance = (displaying_table_idx - prev_table_idx) % table_len
            if table_advance < _JUMP_ADVANCE_HIST_LEN:
                jump_advance_hist[table_advance] += 1
            if table_advance > 1:
                jump_count += 1
                state[_CS_TABLE_ADVANCE_JUMP_COUNT] = jump_count
            if table_advance > max_table_advance:
                max_table_advance = table_advance
                state[_CS_MAX_TABLE_ADVANCE] = max_table_advance

        if need_log == 1:
            if prefill_next < pool_size:
                prefill_incomplete_count += 1
                state[_CS_PREFILL_BURST_INCOMPLETE_COUNT] = prefill_incomplete_count
            frame_log[(frame_count % log_len) * 2] = lines_into_active
            frame_log[(frame_count % log_len) * 2 + 1] = displaying_table_idx
            frame_count += 1
            need_log = 0

        current_row = (lines_into_active * src_height) // v_active
        displaying_buffer = (displaying_table_idx * pool_size) // table_len
        if lines_into_active >= settle_threshold:
            row_correctness[pool_size + _RC_CHECKED_COUNT] += 1
            row_delta = current_row - row_correctness[displaying_buffer]
            if pattern_pos < pattern_len:
                slot = pattern_pos * 4
                pattern_log[slot] = lines_into_active
                pattern_log[slot + 1] = current_row
                pattern_log[slot + 2] = displaying_buffer
                pattern_log[slot + 3] = row_correctness[displaying_buffer]
                pattern_pos += 1
            if row_delta != 0:
                row_correctness[pool_size + _RC_MISMATCH_COUNT] += 1
                if row_delta < 0:
                    row_delta = -row_delta
                if row_delta > row_correctness[pool_size + _RC_MAX_ABS_ROW_DELTA]:
                    row_correctness[pool_size + _RC_MAX_ABS_ROW_DELTA] = row_delta
                if row_delta > 2:
                    row_correctness[pool_size + _RC_LARGE_ROW_DELTA_COUNT] += 1
                if row_correctness[pool_size + _RC_FIRST_MISMATCH_SEEN] == 0:
                    row_correctness[pool_size + _RC_FIRST_MISMATCH_SEEN] = 1
                    row_correctness[pool_size + _RC_FIRST_MISMATCH_LINES_INTO_ACTIVE] = lines_into_active
                    row_correctness[pool_size + _RC_FIRST_MISMATCH_CURRENT_ROW] = current_row
                    row_correctness[pool_size + _RC_FIRST_MISMATCH_DISPLAYING_BUFFER] = displaying_buffer
                    row_correctness[pool_size + _RC_FIRST_MISMATCH_STORED_ROW] = row_correctness[displaying_buffer]
                    row_correctness[pool_size + _RC_FIRST_MISMATCH_TABLE_IDX] = displaying_table_idx
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
        actual_buffer = (pixel_read_addr - pool_base_addr) // buffer_stride_bytes
        if actual_buffer < 0 or actual_buffer >= pool_size:
            out_of_range_count += 1
        else:
            margin = (actual_buffer - safe_buffer) % pool_size
            if margin < min_margin:
                min_margin = margin
                state[_CS_MIN_REFILL_MARGIN_LINES_INTO_ACTIVE] = lines_into_active
            if margin == 0:
                collision_count += 1
        state[_CS_MIN_REFILL_MARGIN_BUFFERS] = min_margin
        state[_CS_REFILL_TARGET_COLLISION_COUNT] = collision_count
        state[_CS_DISPLAYING_BUFFER_OUT_OF_RANGE_COUNT] = out_of_range_count

        if actual_buffer != safe_buffer:
            src_offset = target_row * src_width
            dst_addr = pool_addr_tbl[safe_buffer]
            convert_row_332(ptr32(dst_addr + int(COLOR_PROG_LINE_COUNT_WORDS) * 4), fb, src_offset, content_words, lut, h_dup)
            row_correctness[safe_buffer] = target_row

        if prev_safe_buffer >= 0:
            missed_safe_gap = (safe_buffer - prev_safe_buffer) % pool_size
            if missed_safe_gap > 1:
                catch_up_buffer = (prev_safe_buffer + 1) % pool_size
                if catch_up_buffer != actual_buffer:
                    if exact_ratio:
                        catch_up_target_row = current_row + (catch_up_buffer - current_row) % pool_size
                    else:
                        catch_up_table_idx_start = catch_up_buffer * entries_per_buffer
                        catch_up_steps = (catch_up_table_idx_start - displaying_table_idx) % table_len
                        catch_up_future = lines_into_active + catch_up_steps
                        catch_up_target_row = (catch_up_future * src_height) // v_active
                    if catch_up_target_row >= src_height:
                        catch_up_target_row = src_height - 1
                    catch_up_src_offset = catch_up_target_row * src_width
                    catch_up_dst_addr = pool_addr_tbl[catch_up_buffer]
                    convert_row_332(ptr32(catch_up_dst_addr + int(COLOR_PROG_LINE_COUNT_WORDS) * 4), fb, catch_up_src_offset, content_words, lut, h_dup)
                    row_correctness[catch_up_buffer] = catch_up_target_row
                    catch_up_count += 1
                    state[_CS_CATCH_UP_COUNT] = catch_up_count
        prev_safe_buffer = safe_buffer

        call_count += 1
        state[_CS_REFILL_CALL_COUNT] = call_count
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


HSYNC_PROG_LOOP_HEAD_IRQ_CYCLES = 2


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


COLOR_PROG_BACK_PORCH_PIPELINE_LATENCY_CYCLES = 8
COLOR_PROG_LINE_COUNT_WORDS = const(1)


def make_color_prog(h_sync, h_back_porch, max_flat_deviation=4):
    back_porch_loop_target = h_sync + h_back_porch - COLOR_PROG_BACK_PORCH_PIPELINE_LATENCY_CYCLES
    kind, params, deviation = solve_color_back_porch(back_porch_loop_target, max_flat_deviation)

    if kind == 'flat':
        bx, bd = params

        @asm_pio(out_init=(PIO.OUT_LOW,) * 16, out_shiftdir=PIO.SHIFT_RIGHT, autopull=True, pull_thresh=32)
        def color_prog():
            wrap_target()

            wait(1, irq, 0)
            set(x, bx)
            label("a_p1")
            jmp(x_dec, "a_p1")          [bd]

            out(x, 32)
            label("pxloop")
            out(pins, 16)
            jmp(x_dec, "pxloop")

            mov(pins, null)

            wrap()
        return color_prog, deviation

    box, bod, bix, bid = params

    @asm_pio(out_init=(PIO.OUT_LOW,) * 16, out_shiftdir=PIO.SHIFT_RIGHT, autopull=True, pull_thresh=32)
    def color_prog():
        wrap_target()

        wait(1, irq, 0)
        set(x, box)
        label("a_p1_outer")
        set(y, bix)
        label("a_p1_inner")
        jmp(y_dec, "a_p1_inner")    [bid]
        jmp(x_dec, "a_p1_outer")    [bod]

        out(x, 32)
        label("pxloop")
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

        wrap_target()

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


VgaTiming = namedtuple('VgaTiming', ('name', 'pixel_clock', 'h_sync', 'h_back_porch', 'h_active', 'h_front_porch', 'v_pulse', 'v_back_porch', 'v_active', 'v_front_porch', 'h_sync_positive', 'v_sync_positive', 'h_border_left', 'h_border_right', 'v_border_top', 'v_border_bottom'))

VGA_STATS_FIELDS = (
    'refill_call_count', 'vsync_edge_count',
    'pixel_clock', 'h_active', 'v_pulse', 'v_back_porch', 'prefill_window_lines',
    'src_width', 'src_height', 'v_active', 'table_len', 'entries_per_buffer', 'exact_row_ratio',
    'pool_size', 'refill_margin_target_buffers',
    'min_refill_margin_buffers', 'min_refill_margin_lines_into_active',
    'refill_target_collision_count', 'displaying_buffer_out_of_range_count',
    'prefill_burst_incomplete_count', 'row_correctness_checked_count',
    'row_correctness_mismatch_count', 'row_correctness_max_abs_row_delta',
    'row_correctness_large_row_delta_count', 'row_correctness_first_mismatch_seen',
    'row_correctness_first_mismatch_lines_into_active', 'row_correctness_first_mismatch_current_row',
    'row_correctness_first_mismatch_displaying_buffer', 'row_correctness_first_mismatch_stored_row',
    'row_correctness_first_mismatch_table_idx',
    'vsync_reset_handler_call_count', 'vsync_reset_write_count',
    'line_idx_at_last_vsync', 'line_idx_at_vsync_max_abs', 'vsync_edge_probe_count',
    'vsync_reanchor_count',
    'table_advance_jump_count', 'max_table_advance', 'catch_up_count',
)
VgaStats = namedtuple('VgaStats', VGA_STATS_FIELDS)

_TIMINGS = (
    VgaTiming(name='640x350@85', pixel_clock=31_500_000, h_sync=64, h_back_porch=96, h_active=640, h_front_porch=32, v_pulse=3, v_back_porch=60, v_active=350, v_front_porch=32, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='640x400@85', pixel_clock=31_500_000, h_sync=64, h_back_porch=96, h_active=640, h_front_porch=32, v_pulse=3, v_back_porch=41, v_active=400, v_front_porch=1, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='640x480', pixel_clock=25_175_000, h_sync=96, h_back_porch=40, h_active=640, h_front_porch=8, v_pulse=2, v_back_porch=25, v_active=480, v_front_porch=2, h_sync_positive=False, v_sync_positive=False, h_border_left=8, h_border_right=8, v_border_top=8, v_border_bottom=8),
    VgaTiming(name='640x480@72', pixel_clock=31_500_000, h_sync=40, h_back_porch=120, h_active=640, h_front_porch=16, v_pulse=3, v_back_porch=20, v_active=480, v_front_porch=1, h_sync_positive=False, v_sync_positive=False, h_border_left=8, h_border_right=8, v_border_top=8, v_border_bottom=8),
    VgaTiming(name='640x480@75', pixel_clock=31_500_000, h_sync=64, h_back_porch=120, h_active=640, h_front_porch=16, v_pulse=3, v_back_porch=16, v_active=480, v_front_porch=1, h_sync_positive=False, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='640x480@85', pixel_clock=36_000_000, h_sync=56, h_back_porch=80, h_active=640, h_front_porch=56, v_pulse=3, v_back_porch=25, v_active=480, v_front_porch=1, h_sync_positive=False, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='720x400@85', pixel_clock=35_500_000, h_sync=72, h_back_porch=108, h_active=720, h_front_porch=36, v_pulse=3, v_back_porch=42, v_active=400, v_front_porch=1, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='800x600@56', pixel_clock=36_000_000, h_sync=72, h_back_porch=128, h_active=800, h_front_porch=24, v_pulse=2, v_back_porch=22, v_active=600, v_front_porch=1, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='800x600', pixel_clock=40_000_000, h_sync=128, h_back_porch=88, h_active=800, h_front_porch=40, v_pulse=4, v_back_porch=23, v_active=600, v_front_porch=1, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='800x600@72', pixel_clock=50_000_000, h_sync=120, h_back_porch=64, h_active=800, h_front_porch=56, v_pulse=6, v_back_porch=23, v_active=600, v_front_porch=37, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='800x600@75', pixel_clock=49_500_000, h_sync=80, h_back_porch=160, h_active=800, h_front_porch=16, v_pulse=3, v_back_porch=21, v_active=600, v_front_porch=1, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='800x600@85', pixel_clock=56_250_000, h_sync=64, h_back_porch=152, h_active=800, h_front_porch=32, v_pulse=3, v_back_porch=27, v_active=600, v_front_porch=1, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='800x600@120RB', pixel_clock=73_250_000, h_sync=32, h_back_porch=80, h_active=800, h_front_porch=48, v_pulse=4, v_back_porch=29, v_active=600, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='848x480', pixel_clock=33_750_000, h_sync=112, h_back_porch=112, h_active=848, h_front_porch=16, v_pulse=8, v_back_porch=23, v_active=480, v_front_porch=6, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1024x768@43', pixel_clock=44_900_000, h_sync=176, h_back_porch=56, h_active=1024, h_front_porch=8, v_pulse=4, v_back_porch=20, v_active=768, v_front_porch=0, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1024x768', pixel_clock=65_000_000, h_sync=136, h_back_porch=160, h_active=1024, h_front_porch=24, v_pulse=6, v_back_porch=29, v_active=768, v_front_porch=3, h_sync_positive=False, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1024x768@70', pixel_clock=75_000_000, h_sync=136, h_back_porch=144, h_active=1024, h_front_porch=24, v_pulse=6, v_back_porch=29, v_active=768, v_front_porch=3, h_sync_positive=False, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1024x768@75', pixel_clock=78_750_000, h_sync=96, h_back_porch=176, h_active=1024, h_front_porch=16, v_pulse=3, v_back_porch=28, v_active=768, v_front_porch=1, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1024x768@85', pixel_clock=94_500_000, h_sync=96, h_back_porch=208, h_active=1024, h_front_porch=48, v_pulse=3, v_back_porch=36, v_active=768, v_front_porch=1, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1024x768@120RB', pixel_clock=115_500_000, h_sync=32, h_back_porch=80, h_active=1024, h_front_porch=48, v_pulse=4, v_back_porch=38, v_active=768, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1152x864@75', pixel_clock=108_000_000, h_sync=128, h_back_porch=256, h_active=1152, h_front_porch=64, v_pulse=3, v_back_porch=32, v_active=864, v_front_porch=1, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1280x720', pixel_clock=74_250_000, h_sync=40, h_back_porch=220, h_active=1280, h_front_porch=110, v_pulse=5, v_back_porch=20, v_active=720, v_front_porch=5, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1280x768', pixel_clock=79_500_000, h_sync=128, h_back_porch=192, h_active=1280, h_front_porch=64, v_pulse=7, v_back_porch=20, v_active=768, v_front_porch=3, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1280x768@60RB', pixel_clock=68_250_000, h_sync=32, h_back_porch=80, h_active=1280, h_front_porch=48, v_pulse=7, v_back_porch=12, v_active=768, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1280x768@75', pixel_clock=102_250_000, h_sync=128, h_back_porch=208, h_active=1280, h_front_porch=80, v_pulse=7, v_back_porch=27, v_active=768, v_front_porch=3, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1280x768@85', pixel_clock=117_500_000, h_sync=136, h_back_porch=216, h_active=1280, h_front_porch=80, v_pulse=7, v_back_porch=31, v_active=768, v_front_porch=3, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1280x768@120RB', pixel_clock=140_250_000, h_sync=32, h_back_porch=80, h_active=1280, h_front_porch=48, v_pulse=7, v_back_porch=35, v_active=768, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1280x800', pixel_clock=83_500_000, h_sync=128, h_back_porch=200, h_active=1280, h_front_porch=72, v_pulse=6, v_back_porch=22, v_active=800, v_front_porch=3, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1280x800@60RB', pixel_clock=71_000_000, h_sync=32, h_back_porch=80, h_active=1280, h_front_porch=48, v_pulse=6, v_back_porch=14, v_active=800, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1280x800@75', pixel_clock=106_500_000, h_sync=128, h_back_porch=208, h_active=1280, h_front_porch=80, v_pulse=6, v_back_porch=29, v_active=800, v_front_porch=3, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1280x800@85', pixel_clock=122_500_000, h_sync=136, h_back_porch=216, h_active=1280, h_front_porch=80, v_pulse=6, v_back_porch=34, v_active=800, v_front_porch=3, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1280x800@120RB', pixel_clock=146_250_000, h_sync=32, h_back_porch=80, h_active=1280, h_front_porch=48, v_pulse=6, v_back_porch=38, v_active=800, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1280x960', pixel_clock=108_000_000, h_sync=112, h_back_porch=312, h_active=1280, h_front_porch=96, v_pulse=3, v_back_porch=36, v_active=960, v_front_porch=1, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1280x960@85', pixel_clock=148_500_000, h_sync=160, h_back_porch=224, h_active=1280, h_front_porch=64, v_pulse=3, v_back_porch=47, v_active=960, v_front_porch=1, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1280x960@120RB', pixel_clock=175_500_000, h_sync=32, h_back_porch=80, h_active=1280, h_front_porch=48, v_pulse=4, v_back_porch=50, v_active=960, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1280x1024', pixel_clock=108_000_000, h_sync=112, h_back_porch=248, h_active=1280, h_front_porch=48, v_pulse=3, v_back_porch=38, v_active=1024, v_front_porch=1, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1280x1024@75', pixel_clock=135_000_000, h_sync=144, h_back_porch=248, h_active=1280, h_front_porch=16, v_pulse=3, v_back_porch=38, v_active=1024, v_front_porch=1, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1280x1024@85', pixel_clock=157_500_000, h_sync=160, h_back_porch=224, h_active=1280, h_front_porch=64, v_pulse=3, v_back_porch=44, v_active=1024, v_front_porch=1, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1280x1024@120RB', pixel_clock=187_250_000, h_sync=32, h_back_porch=80, h_active=1280, h_front_porch=48, v_pulse=7, v_back_porch=50, v_active=1024, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1360x768', pixel_clock=85_500_000, h_sync=112, h_back_porch=256, h_active=1360, h_front_porch=64, v_pulse=6, v_back_porch=18, v_active=768, v_front_porch=3, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1360x768@120RB', pixel_clock=148_250_000, h_sync=32, h_back_porch=80, h_active=1360, h_front_porch=48, v_pulse=5, v_back_porch=37, v_active=768, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1366x768@60', pixel_clock=85_500_000, h_sync=143, h_back_porch=213, h_active=1366, h_front_porch=70, v_pulse=3, v_back_porch=24, v_active=768, v_front_porch=3, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1366x768@60RB', pixel_clock=72_000_000, h_sync=56, h_back_porch=64, h_active=1366, h_front_porch=14, v_pulse=3, v_back_porch=28, v_active=768, v_front_porch=1, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1400x1050', pixel_clock=121_750_000, h_sync=144, h_back_porch=232, h_active=1400, h_front_porch=88, v_pulse=4, v_back_porch=32, v_active=1050, v_front_porch=3, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1400x1050@60RB', pixel_clock=101_000_000, h_sync=32, h_back_porch=80, h_active=1400, h_front_porch=48, v_pulse=4, v_back_porch=23, v_active=1050, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1400x1050@75', pixel_clock=156_000_000, h_sync=144, h_back_porch=248, h_active=1400, h_front_porch=104, v_pulse=4, v_back_porch=42, v_active=1050, v_front_porch=3, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1400x1050@85', pixel_clock=179_500_000, h_sync=152, h_back_porch=256, h_active=1400, h_front_porch=104, v_pulse=4, v_back_porch=48, v_active=1050, v_front_porch=3, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1400x1050@120RB', pixel_clock=208_000_000, h_sync=32, h_back_porch=80, h_active=1400, h_front_porch=48, v_pulse=4, v_back_porch=55, v_active=1050, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1440x900', pixel_clock=106_500_000, h_sync=152, h_back_porch=232, h_active=1440, h_front_porch=80, v_pulse=6, v_back_porch=25, v_active=900, v_front_porch=3, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1440x900@60RB', pixel_clock=88_750_000, h_sync=32, h_back_porch=80, h_active=1440, h_front_porch=48, v_pulse=6, v_back_porch=17, v_active=900, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1440x900@75', pixel_clock=136_750_000, h_sync=152, h_back_porch=248, h_active=1440, h_front_porch=96, v_pulse=6, v_back_porch=33, v_active=900, v_front_porch=3, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1440x900@85', pixel_clock=157_000_000, h_sync=152, h_back_porch=256, h_active=1440, h_front_porch=104, v_pulse=6, v_back_porch=39, v_active=900, v_front_porch=3, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1440x900@120RB', pixel_clock=182_750_000, h_sync=32, h_back_porch=80, h_active=1440, h_front_porch=48, v_pulse=6, v_back_porch=44, v_active=900, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1600x900@60RB', pixel_clock=108_000_000, h_sync=80, h_back_porch=96, h_active=1600, h_front_porch=24, v_pulse=3, v_back_porch=96, v_active=900, v_front_porch=1, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1600x1200@60', pixel_clock=162_000_000, h_sync=192, h_back_porch=304, h_active=1600, h_front_porch=64, v_pulse=3, v_back_porch=46, v_active=1200, v_front_porch=1, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1600x1200@65', pixel_clock=175_500_000, h_sync=192, h_back_porch=304, h_active=1600, h_front_porch=64, v_pulse=3, v_back_porch=46, v_active=1200, v_front_porch=1, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1600x1200@70', pixel_clock=189_000_000, h_sync=192, h_back_porch=304, h_active=1600, h_front_porch=64, v_pulse=3, v_back_porch=46, v_active=1200, v_front_porch=1, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1600x1200@75', pixel_clock=202_500_000, h_sync=192, h_back_porch=304, h_active=1600, h_front_porch=64, v_pulse=3, v_back_porch=46, v_active=1200, v_front_porch=1, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1600x1200@85', pixel_clock=229_500_000, h_sync=192, h_back_porch=304, h_active=1600, h_front_porch=64, v_pulse=3, v_back_porch=46, v_active=1200, v_front_porch=1, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1600x1200@120RB', pixel_clock=268_250_000, h_sync=32, h_back_porch=80, h_active=1600, h_front_porch=48, v_pulse=4, v_back_porch=64, v_active=1200, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1680x1050', pixel_clock=146_250_000, h_sync=176, h_back_porch=280, h_active=1680, h_front_porch=104, v_pulse=6, v_back_porch=30, v_active=1050, v_front_porch=3, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1680x1050@60RB', pixel_clock=119_000_000, h_sync=32, h_back_porch=80, h_active=1680, h_front_porch=48, v_pulse=6, v_back_porch=21, v_active=1050, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1680x1050@75', pixel_clock=187_000_000, h_sync=176, h_back_porch=296, h_active=1680, h_front_porch=120, v_pulse=6, v_back_porch=40, v_active=1050, v_front_porch=3, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1680x1050@85', pixel_clock=214_750_000, h_sync=176, h_back_porch=304, h_active=1680, h_front_porch=128, v_pulse=6, v_back_porch=46, v_active=1050, v_front_porch=3, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1680x1050@120RB', pixel_clock=245_500_000, h_sync=32, h_back_porch=80, h_active=1680, h_front_porch=48, v_pulse=6, v_back_porch=53, v_active=1050, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1792x1344@60', pixel_clock=204_750_000, h_sync=200, h_back_porch=328, h_active=1792, h_front_porch=128, v_pulse=3, v_back_porch=46, v_active=1344, v_front_porch=1, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1792x1344@75', pixel_clock=261_000_000, h_sync=216, h_back_porch=352, h_active=1792, h_front_porch=96, v_pulse=3, v_back_porch=69, v_active=1344, v_front_porch=1, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1792x1344@120RB', pixel_clock=333_250_000, h_sync=32, h_back_porch=80, h_active=1792, h_front_porch=48, v_pulse=4, v_back_porch=72, v_active=1344, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1856x1392@60', pixel_clock=218_250_000, h_sync=224, h_back_porch=352, h_active=1856, h_front_porch=96, v_pulse=3, v_back_porch=43, v_active=1392, v_front_porch=1, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1856x1392@75', pixel_clock=288_000_000, h_sync=224, h_back_porch=352, h_active=1856, h_front_porch=128, v_pulse=3, v_back_porch=104, v_active=1392, v_front_porch=1, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1856x1392@120RB', pixel_clock=356_500_000, h_sync=32, h_back_porch=80, h_active=1856, h_front_porch=48, v_pulse=4, v_back_porch=75, v_active=1392, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1920x1080', pixel_clock=148_500_000, h_sync=44, h_back_porch=148, h_active=1920, h_front_porch=88, v_pulse=5, v_back_porch=36, v_active=1080, v_front_porch=4, h_sync_positive=True, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1920x1200@60RB', pixel_clock=154_000_000, h_sync=32, h_back_porch=80, h_active=1920, h_front_porch=48, v_pulse=6, v_back_porch=26, v_active=1200, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1920x1200@60', pixel_clock=193_250_000, h_sync=200, h_back_porch=336, h_active=1920, h_front_porch=136, v_pulse=6, v_back_porch=36, v_active=1200, v_front_porch=3, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1920x1200@75', pixel_clock=245_250_000, h_sync=208, h_back_porch=344, h_active=1920, h_front_porch=136, v_pulse=6, v_back_porch=46, v_active=1200, v_front_porch=3, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1920x1200@85', pixel_clock=281_250_000, h_sync=208, h_back_porch=352, h_active=1920, h_front_porch=144, v_pulse=6, v_back_porch=53, v_active=1200, v_front_porch=3, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1920x1200@120RB', pixel_clock=317_000_000, h_sync=32, h_back_porch=80, h_active=1920, h_front_porch=48, v_pulse=6, v_back_porch=62, v_active=1200, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1920x1440@60', pixel_clock=234_000_000, h_sync=208, h_back_porch=344, h_active=1920, h_front_porch=128, v_pulse=3, v_back_porch=56, v_active=1440, v_front_porch=1, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1920x1440@75', pixel_clock=297_000_000, h_sync=224, h_back_porch=352, h_active=1920, h_front_porch=144, v_pulse=3, v_back_porch=56, v_active=1440, v_front_porch=1, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='1920x1440@120RB', pixel_clock=380_500_000, h_sync=32, h_back_porch=80, h_active=1920, h_front_porch=48, v_pulse=4, v_back_porch=78, v_active=1440, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='2048x1152@60RB', pixel_clock=162_000_000, h_sync=80, h_back_porch=96, h_active=2048, h_front_porch=26, v_pulse=3, v_back_porch=44, v_active=1152, v_front_porch=1, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='2560x1600@60RB', pixel_clock=268_500_000, h_sync=32, h_back_porch=80, h_active=2560, h_front_porch=48, v_pulse=6, v_back_porch=37, v_active=1600, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='2560x1600@60', pixel_clock=348_500_000, h_sync=280, h_back_porch=472, h_active=2560, h_front_porch=192, v_pulse=6, v_back_porch=49, v_active=1600, v_front_porch=3, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='2560x1600@75', pixel_clock=443_250_000, h_sync=280, h_back_porch=488, h_active=2560, h_front_porch=208, v_pulse=6, v_back_porch=63, v_active=1600, v_front_porch=3, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='2560x1600@85', pixel_clock=505_250_000, h_sync=280, h_back_porch=488, h_active=2560, h_front_porch=208, v_pulse=6, v_back_porch=73, v_active=1600, v_front_porch=3, h_sync_positive=False, v_sync_positive=True, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
    VgaTiming(name='2560x1600@120RB', pixel_clock=552_750_000, h_sync=32, h_back_porch=80, h_active=2560, h_front_porch=48, v_pulse=6, v_back_porch=85, v_active=1600, v_front_porch=3, h_sync_positive=True, v_sync_positive=False, h_border_left=0, h_border_right=0, v_border_top=0, v_border_bottom=0),
)

VGA_TIMING_NAMES = tuple(entry.name for entry in _TIMINGS)

def _timing_preset(name):
    for entry in _TIMINGS:
        if entry.name == name:
            preset = {
                'pixel_clock': entry.pixel_clock,
                'h_sync': entry.h_sync,
                'h_front_porch': entry.h_front_porch,
                'h_back_porch': entry.h_back_porch,
                'h_active': entry.h_active,
                'v_pulse': entry.v_pulse,
                'v_front_porch': entry.v_front_porch,
                'v_back_porch': entry.v_back_porch,
                'v_active': entry.v_active,
            }
            if entry.h_sync_positive == entry.v_sync_positive:
                preset['sync_positive'] = entry.h_sync_positive
            else:
                preset['h_sync_positive'] = entry.h_sync_positive
                preset['v_sync_positive'] = entry.v_sync_positive
            if entry.h_border_left:
                preset['h_border_left'] = entry.h_border_left
                preset['h_border_right'] = entry.h_border_right
            if entry.v_border_top:
                preset['v_border_top'] = entry.v_border_top
                preset['v_border_bottom'] = entry.v_border_bottom
            return preset
    raise ValueError('unknown timing preset %r - known: %s' % (name, sorted(e.name for e in _TIMINGS)))


def _resolve_timing(timing=None,
                     pixel_clock=None, h_sync=None, h_back_porch=None, h_active=None, h_front_porch=None,
                     v_pulse=None, v_back_porch=None, v_active=None, v_front_porch=None,
                     h_border_left=None, h_border_right=None, v_border_top=None, v_border_bottom=None,
                     sync_positive=None, h_sync_positive=None, v_sync_positive=None, h_sync_max_deviation=None):
    if timing is not None:
        preset = _timing_preset(timing)
        if pixel_clock is None: pixel_clock = preset.get('pixel_clock')
        if h_sync is None: h_sync = preset.get('h_sync')
        if h_back_porch is None: h_back_porch = preset.get('h_back_porch')
        if h_active is None: h_active = preset.get('h_active')
        if h_front_porch is None: h_front_porch = preset.get('h_front_porch')
        if v_pulse is None: v_pulse = preset.get('v_pulse')
        if v_back_porch is None: v_back_porch = preset.get('v_back_porch')
        if v_active is None: v_active = preset.get('v_active')
        if v_front_porch is None: v_front_porch = preset.get('v_front_porch')
        if h_border_left is None: h_border_left = preset.get('h_border_left')
        if h_border_right is None: h_border_right = preset.get('h_border_right')
        if v_border_top is None: v_border_top = preset.get('v_border_top')
        if v_border_bottom is None: v_border_bottom = preset.get('v_border_bottom')
        if h_sync_positive is None: h_sync_positive = preset.get('h_sync_positive')
        if v_sync_positive is None: v_sync_positive = preset.get('v_sync_positive')
        if sync_positive is None: sync_positive = preset.get('sync_positive')
        if h_sync_max_deviation is None: h_sync_max_deviation = preset.get('h_sync_max_deviation')
    if h_sync_positive is None: h_sync_positive = sync_positive
    if v_sync_positive is None: v_sync_positive = sync_positive
    if h_sync_positive is None: h_sync_positive = False
    if v_sync_positive is None: v_sync_positive = False
    if h_sync_max_deviation is None: h_sync_max_deviation = 0
    if h_border_left or h_border_right or v_border_top or v_border_bottom:
        h_back_porch = (h_back_porch or 0) + (h_border_left or 0)
        h_front_porch = (h_front_porch or 0) + (h_border_right or 0)
        v_back_porch = (v_back_porch or 0) + (v_border_top or 0)
        v_front_porch = (v_front_porch or 0) + (v_border_bottom or 0)
    return {
        'pixel_clock': pixel_clock, 'h_sync': h_sync, 'h_back_porch': h_back_porch,
        'h_active': h_active, 'h_front_porch': h_front_porch,
        'v_pulse': v_pulse, 'v_back_porch': v_back_porch, 'v_active': v_active, 'v_front_porch': v_front_porch,
        'h_sync_positive': h_sync_positive, 'v_sync_positive': v_sync_positive,
        'h_sync_max_deviation': h_sync_max_deviation,
    }



class VGA:
    SIO_GPIO_IN = _SIO_GPIO_IN_ADDR
    DREQ_PIO0_TX0 = 0
    DMA_BASE = 0x50000000
    DMA_CH_STRIDE = 0x40
    DMA_AL3_READ_ADDR_TRIG_OFFSET = 0x3C
    POOL_SIZE = 8
    REFILL_MARGIN_BUFFERS = POOL_SIZE // 2
    JUMP_ADVANCE_HIST_LEN = _JUMP_ADVANCE_HIST_LEN
    DMA_READ_ADDR_WRITE_LATENCY_LINES = 1
    IRQ_DISPATCH_JITTER_MARGIN_LINES = 1
    RESET_ANCHOR_LEAD_LINES = DMA_READ_ADDR_WRITE_LATENCY_LINES + IRQ_DISPATCH_JITTER_MARGIN_LINES

    _dt = _timing_preset('640x480')
    PIXEL_CLOCK = _dt['pixel_clock']
    H_SYNC = _dt['h_sync']
    H_BACK_PORCH = _dt['h_back_porch'] + _dt.get('h_border_left', 0)
    H_ACTIVE = _dt['h_active']
    H_FRONT_PORCH = _dt['h_front_porch'] + _dt.get('h_border_right', 0)
    V_PULSE = _dt['v_pulse']
    V_BACK_PORCH = _dt['v_back_porch'] + _dt.get('v_border_top', 0)
    V_ACTIVE = _dt['v_active']
    V_FRONT_PORCH = _dt['v_front_porch'] + _dt.get('v_border_bottom', 0)
    del _dt

    def __init__(self, framebuffer, width, height, hsync_pin=16, color_base_pin=0, vsync_pin=17,
                 source_color_mode='RGB565', timing=None,
                 pixel_clock=None, h_sync=None, h_back_porch=None, h_active=None, h_front_porch=None,
                 v_pulse=None, v_back_porch=None, v_active=None, v_front_porch=None,
                 h_border_left=None, h_border_right=None, v_border_top=None, v_border_bottom=None,
                 sync_positive=None, h_sync_positive=None, v_sync_positive=None, h_sync_max_deviation=None):
        self.timing_name = timing
        resolved = _resolve_timing(
            timing=timing,
            pixel_clock=pixel_clock, h_sync=h_sync, h_back_porch=h_back_porch, h_active=h_active, h_front_porch=h_front_porch,
            v_pulse=v_pulse, v_back_porch=v_back_porch, v_active=v_active, v_front_porch=v_front_porch,
            h_border_left=h_border_left, h_border_right=h_border_right, v_border_top=v_border_top, v_border_bottom=v_border_bottom,
            sync_positive=sync_positive, h_sync_positive=h_sync_positive, v_sync_positive=v_sync_positive,
            h_sync_max_deviation=h_sync_max_deviation)
        self.width = width
        self.height = height
        self._bounds = (self.width, self.height)
        self.source_color_mode = source_color_mode
        self._is_rgb565 = source_color_mode == 'RGB565'
        self.bytes_per_pixel = 2 if self._is_rgb565 else 1
        self._framebuffer = framebuffer
        self._fb_addr = uctypes.addressof(framebuffer)

        self._core1_state = array.array('i', [0, 0, 0, 0, 0, 0, -1, 0, 0, 0, 0])
        self._core1_done = array.array('i', [0])
        self._started = False

        self._hsync_pin = hsync_pin
        self._color_base_pin = color_base_pin
        self._vsync_pin = vsync_pin
        self.VSYNC_PIN_MASK = 1 << vsync_pin

        self._apply_timing(resolved)

        if not self._is_rgb565:
            self._rgb332_lut = array.array('H', bytearray(256 * 2))
            build_rgb332_dac_lut_into(self._rgb332_lut)

    def _apply_timing(self, resolved):
        if resolved['pixel_clock'] is not None: self.PIXEL_CLOCK = resolved['pixel_clock']
        if resolved['h_sync'] is not None: self.H_SYNC = resolved['h_sync']
        if resolved['h_back_porch'] is not None: self.H_BACK_PORCH = resolved['h_back_porch']
        if resolved['h_active'] is not None: self.H_ACTIVE = resolved['h_active']
        if resolved['h_front_porch'] is not None: self.H_FRONT_PORCH = resolved['h_front_porch']
        if resolved['v_pulse'] is not None: self.V_PULSE = resolved['v_pulse']
        if resolved['v_back_porch'] is not None: self.V_BACK_PORCH = resolved['v_back_porch']
        if resolved['v_active'] is not None: self.V_ACTIVE = resolved['v_active']
        if resolved['v_front_porch'] is not None: self.V_FRONT_PORCH = resolved['v_front_porch']
        self.V_TOTAL = self.V_PULSE + self.V_BACK_PORCH + self.V_ACTIVE + self.V_FRONT_PORCH
        self.V_IDLE = self.V_TOTAL - self.V_PULSE
        self._h_sync_max_deviation = resolved['h_sync_max_deviation']
        self._h_pulse_level = 1 if resolved['h_sync_positive'] else 0
        self._h_idle_level = 0 if resolved['h_sync_positive'] else 1
        self._v_pulse_level = 1 if resolved['v_sync_positive'] else 0
        self._v_idle_level = 0 if resolved['v_sync_positive'] else 1

    def set_timing(self, timing):
        resolved = _resolve_timing(timing=timing)
        if resolved['h_active'] % 4 != 0:
            raise ValueError('h_active must be a multiple of 4 - timing %r has h_active=%d' % (timing, resolved['h_active']))

        was_started = self._started
        previous_timing = self.timing_name
        if was_started:
            self.stop()

        self._apply_timing(resolved)
        self.timing_name = timing

        if was_started:
            try:
                self.start()
            except Exception as e:
                self._apply_timing(_resolve_timing(timing=previous_timing))
                self.timing_name = previous_timing
                self.start()
                raise ValueError('switch to %r failed (%s), reverted to %r' % (timing, e, previous_timing))

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
        stride_words = words_per_line + COLOR_PROG_LINE_COUNT_WORDS
        pool = array.array('I', bytearray(pool_size * stride_words * 4))
        pool_addr = uctypes.addressof(pool)
        pool_addrs = [pool_addr + b * stride_words * 4 for b in range(pool_size)]
        count_word = 2 * words_per_line - 1
        for b in range(pool_size):
            pool[b * stride_words] = count_word
        pool_addr_arr = array.array('I', pool_addrs)
        self._pool = pool
        return pool_addrs, pool_addr_arr

    def _alloc_black_buffer(self, words_per_line):
        stride_words = words_per_line + COLOR_PROG_LINE_COUNT_WORDS
        black = array.array('I', bytearray(stride_words * 4))
        black[0] = 2 * words_per_line - 1
        self._black_buffer = black
        return uctypes.addressof(black)

    def _prefill_pool(self, pool_addrs, pool_size, src_width, words_per_line):
        fb_addr = self._fb_addr
        h_dup = self._h_dup
        if self._is_rgb565:
            for b in range(pool_size):
                src_offset = b * src_width
                convert_row_565(pool_addrs[b] + COLOR_PROG_LINE_COUNT_WORDS * 4, fb_addr, src_offset, words_per_line, h_dup)
        else:
            lut_addr = uctypes.addressof(self._rgb332_lut)
            for b in range(pool_size):
                src_offset = b * src_width
                convert_row_332(pool_addrs[b] + COLOR_PROG_LINE_COUNT_WORDS * 4, fb_addr, src_offset, words_per_line, lut_addr, h_dup)

    def _build_scanout_table(self, table_len, pool_size, pool_addrs, v_active, v_total, black_buffer_addr):
        physical_len = 1
        while physical_len < v_total:
            physical_len *= 2
        addr_table_bytes = physical_len * 4
        ring_size_bits = 0
        while (1 << ring_size_bits) < addr_table_bytes:
            ring_size_bits += 1
        raw = array.array('I', bytearray(physical_len * 2 * 4))
        raw_addr = uctypes.addressof(raw)
        aligned_addr = (raw_addr + addr_table_bytes - 1) & ~(addr_table_bytes - 1)
        offset_words = (aligned_addr - raw_addr) // 4
        for i in range(v_active):
            phase = i % table_len
            raw[offset_words + i] = pool_addrs[(phase * pool_size) // table_len]
        for i in range(v_active, physical_len):
            raw[offset_words + i] = black_buffer_addr
        self._raw = raw
        return aligned_addr, ring_size_bits

    def _prepare_buffers(self, pool_size, src_width, src_height, words_per_line, table_len):
        native_pixels = words_per_line * 2
        if src_width == native_pixels:
            h_dup = 1
        elif src_width * 2 == native_pixels:
            h_dup = 2
        elif src_width * 4 == native_pixels:
            h_dup = 4
        else:
            raise ValueError(
                'framebuffer width %d must be h_active/2 (%d), h_active/4, or h_active/8 for timing %s '
                '(non-integer horizontal scale needs the slow path, which is disabled)' % (
                    src_width, native_pixels, self.timing_name))
        self._h_dup = h_dup
        signature = (src_width, src_height, pool_size, words_per_line, table_len, self.V_ACTIVE, self.V_TOTAL)
        if getattr(self, '_alloc_signature', None) != signature:
            self._alloc_signature = None
            self._pool = None
            self._black_buffer = None
            self._raw = None
            pool_addrs, pool_addr_arr = self._alloc_scanline_pool(pool_size, words_per_line)
            black_buffer_addr = self._alloc_black_buffer(words_per_line)
            table_addr, ring_size_bits = self._build_scanout_table(
                table_len, pool_size, pool_addrs, self.V_ACTIVE, self.V_TOTAL, black_buffer_addr)
            self._pool_addrs = pool_addrs
            self._pool_addr_arr = pool_addr_arr
            self._black_buffer_addr = black_buffer_addr
            self._table_addr = table_addr
            self._ring_size_bits = ring_size_bits
            self._alloc_signature = signature
        else:
            pool_addrs = self._pool_addrs
            pool_addr_arr = self._pool_addr_arr
            table_addr = self._table_addr
            ring_size_bits = self._ring_size_bits
        return pool_addrs, pool_addr_arr, table_addr, ring_size_bits

    def _start_video_pipeline(self, table_addr, table_len, ring_size_bits, pool_addrs, words_per_line):
        H_TOTAL = self.H_SYNC + self.H_BACK_PORCH + self.H_ACTIVE + self.H_FRONT_PORCH
        hsync_prog, hsync_deviation_cycles = make_hsync_prog(
            self.H_SYNC, H_TOTAL - self.H_SYNC - HSYNC_PROG_LOOP_HEAD_IRQ_CYCLES, self._h_pulse_level, self._h_idle_level,
            max_flat_deviation=self._h_sync_max_deviation)
        self.hsync_deviation_cycles = hsync_deviation_cycles
        hsync_sm = StateMachine(0, hsync_prog, freq=self.PIXEL_CLOCK, set_base=Pin(self._hsync_pin))
        color_prog, color_back_porch_deviation_cycles = make_color_prog(self.H_SYNC, self.H_BACK_PORCH, max_flat_deviation=0)
        self.color_back_porch_deviation_cycles = color_back_porch_deviation_cycles
        color_sm = StateMachine(1, color_prog, freq=self.PIXEL_CLOCK, out_base=Pin(self._color_base_pin))
        vsync_sm = StateMachine(2, make_vsync_prog(self.V_PULSE - 1, self._v_pulse_level, self._v_idle_level), freq=self.PIXEL_CLOCK, sideset_base=Pin(self._vsync_pin))
        self._hsync_sm = hsync_sm
        self._color_sm = color_sm
        self._vsync_sm = vsync_sm

        ch_pixel = DMA()
        ch_ctrl = DMA()
        self._ch_pixel = ch_pixel
        self._ch_ctrl = ch_ctrl

        ch_pixel_al3_trig_addr = self.DMA_BASE + ch_pixel.channel * self.DMA_CH_STRIDE + self.DMA_AL3_READ_ADDR_TRIG_OFFSET
        ch_ctrl_reg_addr = self.DMA_BASE + ch_ctrl.channel * self.DMA_CH_STRIDE + 0x00

        ctrl_pixel = ch_pixel.pack_ctrl(size=2, inc_read=True, inc_write=False,
                                         treq_sel=self.DREQ_PIO0_TX0 + 1,
                                         chain_to=ch_ctrl.channel,
                                         high_pri=True)
        ctrl_ctrl = ch_ctrl.pack_ctrl(size=2, inc_read=True, inc_write=False,
                                       treq_sel=0x3F,
                                       chain_to=ch_ctrl.channel,
                                       ring_sel=False, ring_size=ring_size_bits,
                                       high_pri=True, irq_quiet=False)

        ch_pixel.config(read=pool_addrs[0], write=color_sm, count=words_per_line + COLOR_PROG_LINE_COUNT_WORDS, ctrl=ctrl_pixel, trigger=False)
        ch_ctrl.config(read=table_addr, write=ch_pixel_al3_trig_addr, count=1, ctrl=ctrl_ctrl, trigger=False)

        color_sm.active(1)

        reset_line_idx = (self.V_PULSE + self.V_BACK_PORCH - self.RESET_ANCHOR_LEAD_LINES) % self.V_TOTAL
        _vsync_reset_shared[_VSR_CH_CTRL_READ_ADDR_REGISTER] = ch_ctrl_reg_addr
        _vsync_reset_shared[_VSR_RESET_TARGET_TABLE_ADDR] = table_addr
        _vsync_reset_shared[_VSR_RESET_LINE_IDX] = reset_line_idx
        _vsync_reset_shared[_VSR_LINE_IDX] = -1
        _vsync_reset_shared[_VSR_V_TOTAL] = self.V_TOTAL
        _vsync_reset_shared[_VSR_HANDLER_CALL_COUNT] = 0
        _vsync_reset_shared[_VSR_RESET_WRITE_COUNT] = 0
        _vsync_reset_shared[_VSR_LINE_IDX_AT_VSYNC] = 0
        _vsync_reset_shared[_VSR_LINE_IDX_AT_VSYNC_MAX_ABS] = 0
        _vsync_reset_shared[_VSR_EDGE_PROBE_COUNT] = 0
        _vsync_reset_shared[_VSR_VSYNC_PIN_MASK] = self.VSYNC_PIN_MASK
        _vsync_reset_shared[_VSR_VSYNC_ASSERTED_HIGH] = self._v_pulse_level
        _vsync_reset_shared[_VSR_LAST_VSYNC_ASSERTED] = 0
        _vsync_reset_shared[_VSR_RESET_DONE_THIS_FRAME] = 0
        _vsync_reset_shared[_VSR_REANCHOR_COUNT] = 0
        ch_ctrl.irq(handler=_vsync_reset_irq_handler, hard=True)
        vsync_sm.active(1)
        vsync_sm.put(self.V_IDLE - 1)

        ch_ctrl.active(1)
        hsync_sm.active(1)

        ch_pixel_reg_addr = self.DMA_BASE + ch_pixel.channel * self.DMA_CH_STRIDE + 0x00
        return ch_ctrl_reg_addr, ch_pixel_reg_addr

    def _clear_array(self, arr):
        for i in range(len(arr)):
            arr[i] = 0

    def _alloc_diagnostics(self, pool_size, table_len):
        log_len = 64
        tail_log_len = 64
        tail_threshold = 0
        pattern_len = 64
        if hasattr(self, 'frame_log'):
            self._clear_array(self.frame_log)
            self._clear_array(self.tail_log)
            self._clear_array(self.row_correctness)
            self._clear_array(self.pattern_log)
            self._clear_array(self.jump_advance_hist)
        else:
            self.frame_log = array.array('i', bytearray(log_len * 2 * 4))
            self.tail_log = array.array('i', bytearray(tail_log_len * 5 * 4))
            self.row_correctness = array.array('i', bytearray((pool_size + 10) * 4))
            self.pattern_log = array.array('i', bytearray(pattern_len * 4 * 4))
            self.jump_advance_hist = array.array('i', bytearray(_JUMP_ADVANCE_HIST_LEN * 4))
        return log_len, tail_log_len, tail_threshold, pattern_len

    def _start_core1_thread(self, pool_addr_arr, ch_ctrl_reg_addr, table_addr, table_len, pool_size,
                             src_width, src_height, active_start_offset, ch_pixel_reg_addr,
                             pool_base_addr, buffer_stride_bytes, log_len, tail_log_len, tail_threshold,
                             pattern_len):
        row_correctness_addr = uctypes.addressof(self.row_correctness)
        pattern_log_addr = uctypes.addressof(self.pattern_log)
        jump_advance_hist_addr = uctypes.addressof(self.jump_advance_hist)
        common_args = (
            self._core1_state, self._core1_done,
            pool_addr_arr, self._framebuffer,
            ch_ctrl_reg_addr, table_addr, table_len,
            pool_size, src_width, src_height,
            active_start_offset, self.V_ACTIVE,
            self.SIO_GPIO_IN, self.VSYNC_PIN_MASK,
            self.frame_log, log_len,
            ch_pixel_reg_addr, pool_base_addr, buffer_stride_bytes,
            self.REFILL_MARGIN_BUFFERS,
            self.tail_log, tail_log_len, tail_threshold,
            self._h_dup,
        )
        if self._is_rgb565:
            _thread.start_new_thread(core1_loop_viper_565, common_args + (
                row_correctness_addr,
                pattern_log_addr, pattern_len,
                _vsync_reset_shared_addr,
                jump_advance_hist_addr,
            ))
        else:
            _thread.start_new_thread(core1_loop_viper_332, common_args + (
                uctypes.addressof(self._rgb332_lut),
                row_correctness_addr,
                pattern_log_addr, pattern_len,
                _vsync_reset_shared_addr,
                jump_advance_hist_addr,
            ))

    def start(self):
        if self._started:
            return

        if hasattr(self, '_core1_state'):
            for i, value in enumerate(_CORE1_STATE_INITIAL):
                self._core1_state[i] = value
            self._core1_done[0] = 0
        else:
            self._core1_state = array.array('i', _CORE1_STATE_INITIAL)
            self._core1_done = array.array('i', [0])

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
        self._table_len = TABLE_LEN

        pool_addrs, pool_addr_arr, table_addr, ring_size_bits = \
            self._prepare_buffers(POOL_SIZE, SRC_WIDTH, SRC_HEIGHT, WORDS_PER_LINE, TABLE_LEN)

        self._prefill_pool(pool_addrs, POOL_SIZE, SRC_WIDTH, WORDS_PER_LINE)

        buffer_stride_bytes = (WORDS_PER_LINE + COLOR_PROG_LINE_COUNT_WORDS) * 4
        active_start_offset = self.V_PULSE + self.V_BACK_PORCH

        LOG_LEN, TAIL_LOG_LEN, TAIL_THRESHOLD, PATTERN_LEN = self._alloc_diagnostics(POOL_SIZE, TABLE_LEN)

        ch_ctrl_reg_addr, ch_pixel_reg_addr = self._start_video_pipeline(
            table_addr, TABLE_LEN, ring_size_bits, pool_addrs, WORDS_PER_LINE)

        self._start_core1_thread(
            pool_addr_arr, ch_ctrl_reg_addr, table_addr, TABLE_LEN, POOL_SIZE, SRC_WIDTH, SRC_HEIGHT,
            active_start_offset, ch_pixel_reg_addr, pool_addrs[0], buffer_stride_bytes,
            LOG_LEN, TAIL_LOG_LEN, TAIL_THRESHOLD, PATTERN_LEN)

        self._started = True

    def render(self, fb, width, height, bbox):
        pass

    def get_bounds(self):
        return self._bounds

    def set_backlight(self, brightness):
        if brightness <= 0:
            self.stop()
        else:
            self.start()

    def stop(self):
        if not self._started:
            return
        self._core1_state[_CS_STOP_REQUESTED] = 1
        stop_wait_start = time.ticks_ms()
        while self._core1_done[0] == 0 and time.ticks_diff(time.ticks_ms(), stop_wait_start) < 2000:
            time.sleep_ms(10)
        self._hsync_sm.active(0)
        self._color_sm.active(0)
        self._vsync_sm.active(0)
        self._ch_ctrl.close()
        self._ch_pixel.close()
        PIO(0).remove_program()
        self._started = False

    def stats(self):
        if not self._started:
            return None
        state = self._core1_state
        row_correctness = self.row_correctness
        pool_size = self.POOL_SIZE
        table_len = self._table_len
        entries_per_buffer = table_len // pool_size
        exact_row_ratio = 1 if entries_per_buffer * self.height == self.V_ACTIVE else 0
        return VgaStats(
            refill_call_count=state[_CS_REFILL_CALL_COUNT],
            vsync_edge_count=state[_CS_VSYNC_EDGE_COUNT],
            pixel_clock=self.PIXEL_CLOCK,
            h_active=self.H_ACTIVE,
            v_pulse=self.V_PULSE,
            v_back_porch=self.V_BACK_PORCH,
            prefill_window_lines=self.V_PULSE + self.V_BACK_PORCH,
            src_width=self.width,
            src_height=self.height,
            v_active=self.V_ACTIVE,
            table_len=table_len,
            entries_per_buffer=entries_per_buffer,
            exact_row_ratio=exact_row_ratio,
            pool_size=pool_size,
            refill_margin_target_buffers=self.REFILL_MARGIN_BUFFERS,
            min_refill_margin_buffers=state[_CS_MIN_REFILL_MARGIN_BUFFERS],
            min_refill_margin_lines_into_active=state[_CS_MIN_REFILL_MARGIN_LINES_INTO_ACTIVE],
            refill_target_collision_count=state[_CS_REFILL_TARGET_COLLISION_COUNT],
            displaying_buffer_out_of_range_count=state[_CS_DISPLAYING_BUFFER_OUT_OF_RANGE_COUNT],
            prefill_burst_incomplete_count=state[_CS_PREFILL_BURST_INCOMPLETE_COUNT],
            row_correctness_checked_count=row_correctness[pool_size + _RC_CHECKED_COUNT],
            row_correctness_mismatch_count=row_correctness[pool_size + _RC_MISMATCH_COUNT],
            row_correctness_max_abs_row_delta=row_correctness[pool_size + _RC_MAX_ABS_ROW_DELTA],
            row_correctness_large_row_delta_count=row_correctness[pool_size + _RC_LARGE_ROW_DELTA_COUNT],
            row_correctness_first_mismatch_seen=row_correctness[pool_size + _RC_FIRST_MISMATCH_SEEN],
            row_correctness_first_mismatch_lines_into_active=row_correctness[pool_size + _RC_FIRST_MISMATCH_LINES_INTO_ACTIVE],
            row_correctness_first_mismatch_current_row=row_correctness[pool_size + _RC_FIRST_MISMATCH_CURRENT_ROW],
            row_correctness_first_mismatch_displaying_buffer=row_correctness[pool_size + _RC_FIRST_MISMATCH_DISPLAYING_BUFFER],
            row_correctness_first_mismatch_stored_row=row_correctness[pool_size + _RC_FIRST_MISMATCH_STORED_ROW],
            row_correctness_first_mismatch_table_idx=row_correctness[pool_size + _RC_FIRST_MISMATCH_TABLE_IDX],
            vsync_reset_handler_call_count=_vsync_reset_shared[_VSR_HANDLER_CALL_COUNT],
            vsync_reset_write_count=_vsync_reset_shared[_VSR_RESET_WRITE_COUNT],
            line_idx_at_last_vsync=_vsync_reset_shared[_VSR_LINE_IDX_AT_VSYNC],
            line_idx_at_vsync_max_abs=_vsync_reset_shared[_VSR_LINE_IDX_AT_VSYNC_MAX_ABS],
            vsync_edge_probe_count=_vsync_reset_shared[_VSR_EDGE_PROBE_COUNT],
            vsync_reanchor_count=_vsync_reset_shared[_VSR_REANCHOR_COUNT],
            table_advance_jump_count=state[_CS_TABLE_ADVANCE_JUMP_COUNT],
            max_table_advance=state[_CS_MAX_TABLE_ADVANCE],
            catch_up_count=state[_CS_CATCH_UP_COUNT],
        )
