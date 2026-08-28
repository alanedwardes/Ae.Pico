import asyncio
from vga import VGA, VGA_STATS_FIELDS, VGA_TIMING_NAMES
from drawing import Drawing
from management import parse_form

DEFAULT_WIDTH = 320
DEFAULT_HEIGHT = 240


class VGADisplay:
    def __init__(self, vga, drawing):
        self.vga = vga
        self.drawing = drawing

    def create(provider):
        config = provider['config'].get('display', {})

        width = config.get('width', DEFAULT_WIDTH)
        height = config.get('height', DEFAULT_HEIGHT)
        mode = config.get('mode', 'RGB565')
        hsync_pin = config.get('hsync_pin', 16)
        color_base_pin = config.get('color_base_pin', 0)
        vsync_pin = config.get('vsync_pin', 17)

        framebuffer = config.get('framebuffer')
        drawing = Drawing(width, height, color_mode=mode, framebuffer=framebuffer)

        vga = VGA(
            drawing.framebuffer,
            width,
            height,
            hsync_pin=hsync_pin,
            color_base_pin=color_base_pin,
            vsync_pin=vsync_pin,
            source_color_mode=mode,
            timing=config.get('timing'),
            pixel_clock=config.get('pixel_clock'),
            h_sync=config.get('h_sync'),
            h_back_porch=config.get('h_back_porch'),
            h_active=config.get('h_active'),
            h_front_porch=config.get('h_front_porch'),
            v_pulse=config.get('v_pulse'),
            v_back_porch=config.get('v_back_porch'),
            v_active=config.get('v_active'),
            v_front_porch=config.get('v_front_porch'),
            sync_positive=config.get('sync_positive'),
            h_sync_max_deviation=config.get('h_sync_max_deviation'),
        )
        vga.start()
        drawing.set_driver(vga)

        provider['display'] = drawing
        return VGADisplay(vga, drawing)

    async def start(self):
        await asyncio.Event().wait()


class VgaStatsController:
    def __init__(self, vga):
        self.vga = vga

    CREATION_PRIORITY = 1
    def create(provider):
        vga_display = provider.get('vgadisplay.VGADisplay')
        management = provider.get('management.ManagementServer')
        if vga_display is None or management is None:
            return

        controller = VgaStatsController(vga_display.vga)
        management.controllers.append(controller)
        return controller

    async def start(self):
        await asyncio.Event().wait()

    def route(self, method, path):
        return path == b'/vgastats'

    def widget(self):
        return b' <a href="vgastats">VGA Stats</a>'

    def _write_timing_form(self, writer):
        writer.write(b'<form method="post" action="vgastats"><select name="timing">')
        current = self.vga.timing_name
        for name in VGA_TIMING_NAMES:
            selected = b' selected' if name == current else b''
            encoded_name = name.encode('utf-8')
            writer.write(b'<option value="%s"%s>%s</option>' % (encoded_name, selected, encoded_name))
        writer.write(b'</select> <button>Apply</button></form>')

    def _write_power_form(self, writer, stats):
        running = stats is not None
        status = b'Started' if running else b'Stopped'
        status_class = b'' if running else b' class="bad"'
        stop_disabled = b' disabled' if not running else b''
        start_disabled = b' disabled' if running else b''
        writer.write(b'<form method="post" action="vgastats"><p%s>Signal: %s</p>'
                     b'<button name="power" value="stop"%s>Stop</button> '
                     b'<button name="power" value="start"%s>Start</button></form>'
                     % (status_class, status, stop_disabled, start_disabled))

    def _write_expected_actual_row(self, writer, label, expected, actual, ok):
        css_class = b'' if ok else b' class="bad"'
        writer.write(b'<tr%s><td>%s</td><td>%i</td><td>%i</td></tr>' % (css_class, label, expected, actual))

    def _write_expected_actual_table(self, writer, stats):
        writer.write(b'<p>%i Hz pixel clock, %i active columns, %i-line prefill window (%i pulse + %i back porch).</p>' % (
            stats.pixel_clock, stats.h_active, stats.prefill_window_lines, stats.v_pulse, stats.v_back_porch))
        writer.write(b'<p>%ix%i source scaled to %i active lines: %i table entries, %i output lines per buffer (%s ratio).</p>' % (
            stats.src_width, stats.src_height, stats.v_active, stats.table_len, stats.entries_per_buffer,
            b'exact' if stats.exact_row_ratio else b'approximate'))

        writer.write(b'<h2>Refill Timing</h2>')
        writer.write(b'<table><thead><tr><th></th><th>Expected</th><th>Actual</th></tr></thead><tbody>')
        self._write_expected_actual_row(
            writer, b'Refill margin (buffers)',
            stats.refill_margin_target_buffers, stats.min_refill_margin_buffers,
            stats.min_refill_margin_buffers >= stats.refill_margin_target_buffers)
        self._write_expected_actual_row(
            writer, b'Refill target collisions',
            0, stats.refill_target_collision_count,
            stats.refill_target_collision_count == 0)
        self._write_expected_actual_row(
            writer, b'Out-of-range buffer reads',
            0, stats.displaying_buffer_out_of_range_count,
            stats.displaying_buffer_out_of_range_count == 0)
        self._write_expected_actual_row(
            writer, b'Incomplete prefill bursts',
            0, stats.prefill_burst_incomplete_count,
            stats.prefill_burst_incomplete_count == 0)
        writer.write(b'</tbody></table>')
        writer.write(b'<p>Worst margin observed %i lines into active video.</p>' % stats.min_refill_margin_lines_into_active)

        writer.write(b'<h2>Row Correctness</h2>')
        writer.write(b'<table><thead><tr><th></th><th>Expected</th><th>Actual</th></tr></thead><tbody>')
        self._write_expected_actual_row(
            writer, b'Mismatches',
            0, stats.row_correctness_mismatch_count,
            stats.row_correctness_mismatch_count == 0)
        self._write_expected_actual_row(
            writer, b'Max |row delta|',
            0, stats.row_correctness_max_abs_row_delta,
            stats.row_correctness_max_abs_row_delta == 0)
        if stats.row_correctness_first_mismatch_seen:
            self._write_expected_actual_row(
                writer, b'First mismatch: row shown vs. row stored',
                stats.row_correctness_first_mismatch_current_row, stats.row_correctness_first_mismatch_stored_row,
                False)
        writer.write(b'</tbody></table>')
        mismatch_rate = (100.0 * stats.row_correctness_mismatch_count / stats.row_correctness_checked_count) \
            if stats.row_correctness_checked_count else 0.0
        writer.write(b'<p>%i / %i rows checked (%.3f%% mismatched).</p>' % (
            stats.row_correctness_mismatch_count, stats.row_correctness_checked_count, mismatch_rate))

    def _write_table_advance_diagnostics(self, writer, stats):
        if not hasattr(self.vga, 'jump_advance_hist'):
            return
        vga = self.vga
        jump_advance_hist = vga.jump_advance_hist
        hist_len = vga.JUMP_ADVANCE_HIST_LEN

        writer.write(b'<h2>Table Advance Histogram</h2>')
        writer.write(b'<p>Each pass core1 polls the DMA table position. advance=1 means it kept up '
                     b'(one new entry since last poll); advance=N means N-1 entries passed unread, '
                     b'so a buffer can skip refill and display stale content. If the jumps total '
                     b'matches the large-row-delta count, the missed-refill cause is confirmed.</p>')
        writer.write(b'<table><thead><tr><th>advance</th><th>count</th></tr></thead><tbody>')
        for i in range(1, hist_len):
            count = jump_advance_hist[i]
            if count:
                writer.write(b'<tr><td>%i</td><td>%i</td></tr>' % (i, count))
        writer.write(b'</tbody></table>')

        frames = stats.vsync_edge_count
        jump_per_frame = (stats.table_advance_jump_count / frames) if frames else 0.0
        catch_up_per_frame = (stats.catch_up_count / frames) if frames else 0.0
        large_per_frame = (stats.row_correctness_large_row_delta_count / frames) if frames else 0.0
        writer.write(b'<p>Table-advance jumps (advance&gt;1): %i (max advance %i). '
                     b'Catch-up refills: %i. Large row deltas: %i.</p>' % (
                         stats.table_advance_jump_count, stats.max_table_advance,
                         stats.catch_up_count, stats.row_correctness_large_row_delta_count))
        writer.write(b'<p>Per frame: jumps %.4f, catch-ups %.4f, large deltas %.4f.</p>' % (
            jump_per_frame, catch_up_per_frame, large_per_frame))

    async def serve(self, method, path, headers, reader, writer):
        error = None
        if method == b'POST':
            content_length = int(headers.get(b'content-length', '0'))
            form = parse_form(await reader.readexactly(content_length))
            timing = form.get(b'timing')
            if timing:
                try:
                    self.vga.set_timing(timing.decode('utf-8'))
                except ValueError as e:
                    error = str(e)
            power = form.get(b'power')
            if power in (b'stop', b'start'):
                try:
                    if power == b'stop':
                        self.vga.stop()
                    else:
                        self.vga.start()
                except Exception as e:
                    error = str(e)

        stats = self.vga.stats()

        writer.write(b'HTTP/1.0 200 OK\r\n')
        writer.write(b'Content-Type: text/html; charset=utf-8\r\n')
        writer.write(b'Cache-Control: no-cache\r\n')
        writer.write(b'Connection: close\r\n')
        writer.write(b'\r\n')
        writer.write(b'<style>form{display:inline;}body{background-color:Canvas;color:CanvasText;color-scheme:light dark;font-family:sans-serif;}.bad{color:#c00;font-weight:bold;}</style>')
        writer.write(b'<h1>VGA Stats</h1>')
        self._write_timing_form(writer)
        self._write_power_form(writer, stats)
        if error:
            writer.write(b'<p class="bad">%s</p>' % error.encode('utf-8'))

        if stats is None:
            writer.write(b'<p>VGA has not started.</p>')
        else:
            self._write_expected_actual_table(writer, stats)
            self._write_table_advance_diagnostics(writer, stats)

            writer.write(b'<h2>Raw Counters</h2>')
            writer.write(b'<table><tbody>')
            for name, value in zip(VGA_STATS_FIELDS, stats):
                writer.write(b'<tr><td>%s</td><td>%i</td></tr>' % (name.encode('utf-8'), value))
            writer.write(b'</tbody></table>')

        writer.write(b'<p><a href="/">Back</a></p>')
        await writer.drain()
        writer.close()
        await writer.wait_closed()
