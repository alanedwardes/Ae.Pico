import sys
import struct
import asyncio
import unittest
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../infodisplay')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../cpython')))

from bmfont import BMFont, measure_text, measure_extend, _GLYPH_FMT
import textbox

# width, height, xoffset, yoffset, xadvance for each character, chosen so
# every glyph has non-trivial bearings (xoffset/width don't just equal
# xadvance) -- catches bugs that only show up when the tight bounding box
# differs from the advance-based box.
_GLYPHS = {
    ' ': (2, 2, 0, 0, 6),
    'a': (8, 10, 1, 2, 10),
    'b': (9, 14, 1, 0, 11),
    'c': (7, 10, 0, 2, 8),
    'd': (9, 14, 1, 0, 11),
    'e': (8, 10, 1, 2, 9),
    'g': (8, 14, 1, 4, 9),
    'h': (8, 14, 1, 0, 10),
    'i': (3, 14, 1, 0, 5),
    'j': (5, 18, -1, 4, 5),
    'l': (3, 14, 1, 0, 5),
    'm': (13, 10, 1, 2, 15),
    'n': (8, 10, 1, 2, 10),
    'o': (8, 10, 1, 2, 10),
    'p': (9, 14, 1, 4, 11),
    'q': (9, 14, 1, 4, 11),
    'r': (6, 10, 1, 2, 7),
    's': (7, 10, 0, 2, 8),
    't': (5, 12, 0, 1, 6),
    'u': (8, 10, 1, 2, 10),
    'w': (12, 10, 1, 2, 14),
    'x': (8, 10, 0, 2, 8),
    'y': (8, 14, 0, 2, 8),
    'z': (7, 10, 0, 2, 8),
}


def make_font(glyphs=_GLYPHS, line_height=20, kerning=None):
    font = BMFont()
    font.line_height = line_height
    font.scale_w = 256
    font.scale_h = 256
    font._glyph_data = bytearray()
    font.chars = {}
    font.kerning = dict(kerning or {})
    for ch, (width, height, xoffset, yoffset, xadvance) in glyphs.items():
        off = len(font._glyph_data)
        font._glyph_data.extend(struct.pack(_GLYPH_FMT, 0, 0, width, height, xoffset, yoffset, xadvance, 0))
        font.chars[ord(ch)] = off
    return font


class TestMeasureExtend(unittest.TestCase):
    def setUp(self):
        self.font = make_font()

    def test_matches_measure_text_fresh_start(self):
        for text in ('a', 'abc', 'hello world', 'the quick brown fox', 'jjjj'):
            w, _h, _min_x, _min_y = measure_text(self.font, text)
            cx, prev_id, min_left, max_right = measure_extend(self.font, text, 0, None, None, None)
            extend_w = 0 if min_left is None else max_right - min_left
            self.assertEqual(extend_w, w, 'mismatch for %r' % text)

    def test_empty_string(self):
        cx, prev_id, min_left, max_right = measure_extend(self.font, '', 0, None, None, None)
        self.assertEqual(cx, 0)
        self.assertIsNone(prev_id)
        self.assertIsNone(min_left)
        self.assertIsNone(max_right)

    def test_unknown_characters_are_skipped(self):
        w1, _h, _min_x, _min_y = measure_text(self.font, 'abc')
        w2, _h, _min_x, _min_y = measure_text(self.font, 'a\x01b\x02c')
        self.assertEqual(w1, w2)

    def test_resuming_scan_matches_single_pass(self):
        full = 'hello world'
        cx, prev_id, min_left, max_right = measure_extend(self.font, 'hello', 0, None, None, None)
        cx, prev_id, min_left, max_right = measure_extend(
            self.font, ' world', cx, prev_id, min_left, max_right)
        resumed_w = max_right - min_left

        w, _h, _min_x, _min_y = measure_text(self.font, full)
        self.assertEqual(resumed_w, w)

    def test_resuming_scan_matches_single_pass_many_words(self):
        words = ['the', 'quick', 'brown', 'fox', 'jumps', 'over', 'the', 'lazy', 'dog']
        cx, prev_id, min_left, max_right = 0, None, None, None
        for i, word in enumerate(words):
            piece = word if i == 0 else ' ' + word
            cx, prev_id, min_left, max_right = measure_extend(
                self.font, piece, cx, prev_id, min_left, max_right)
        resumed_w = max_right - min_left

        w, _h, _min_x, _min_y = measure_text(self.font, ' '.join(words))
        self.assertEqual(resumed_w, w)

    def test_kerning_applied_when_requested(self):
        font = make_font(kerning={(ord('a'), ord('b')): -3})
        cx_no_k, _p, min_no_k, max_no_k = measure_extend(font, 'ab', 0, None, None, None, kerning=False)
        cx_k, _p, min_k, max_k = measure_extend(font, 'ab', 0, None, None, None, kerning=True)
        self.assertEqual(cx_k, cx_no_k - 3)


class TestWordWrapBmfont(unittest.TestCase):
    def setUp(self):
        self.font = make_font()

    def _wrap(self, text, max_width_pixels, scale=1):
        return asyncio.run(textbox._word_wrap_bmfont(self.font, text, max_width_pixels, scale))

    def test_empty_string(self):
        self.assertEqual(self._wrap('', 100), '')

    def test_single_short_word(self):
        self.assertEqual(self._wrap('cat', 200), 'cat')

    def test_normal_wrap(self):
        self.assertEqual(
            self._wrap('the quick brown fox jumps over the lazy dog', 100),
            'the quick\nbrown fox\njumps over\nthe lazy dog')

    def test_one_very_wide_word(self):
        self.assertEqual(
            self._wrap('supercalifragilisticexpialidocious cat', 60),
            '\nsupercalifragilisticexpialidocious\ncat')

    def test_wide_word_mid_sentence(self):
        self.assertEqual(
            self._wrap('a cat supercalifragilisticexpialidocious dog', 60),
            'a cat\nsupercalifragilisticexpialidocious\ndog')

    def test_tight_width_forces_many_breaks(self):
        self.assertEqual(
            self._wrap('the quick brown fox jumps over the lazy dog', 20),
            '\nthe\nquick\nbrown\nfox\njumps\nover\nthe\nlazy\ndog')

    def test_exact_fit_boundary_width(self):
        # 'cat dog' is exactly 60px wide in this synthetic font.
        self.assertEqual(self._wrap('cat dog', 60), 'cat dog')
        self.assertEqual(self._wrap('cat dog', 59), 'cat\ndog')

    def test_scale_not_one(self):
        self.assertEqual(
            self._wrap('the quick brown fox jumps over the lazy dog', 100, scale=2),
            'the\nquick\nbrown\nfox\njumps\nover\nthe\nlazy\ndog')

    def test_repeated_spaces_collapse_like_split(self):
        self.assertEqual(self._wrap('the   quick    brown fox', 100), 'the quick\nbrown fox')

    def test_many_words_crosses_asyncio_sleep_batch(self):
        text = ' '.join(['word%d' % i for i in range(25)])
        expected = '\n'.join(['word%d' % i for i in range(25)])
        self.assertEqual(self._wrap(text, 80), expected)


if __name__ == '__main__':
    unittest.main()
