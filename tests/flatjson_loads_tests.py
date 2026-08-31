import os
import sys
import json
import random
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../libraries')))
from flatjson import loads


def _b(s):
    return s.encode('utf-8')


class TestLoadsBasics(unittest.TestCase):

    def test_basic_types(self):
        self.assertEqual(loads(_b('true')), True)
        self.assertEqual(loads(_b('false')), False)
        self.assertEqual(loads(_b('null')), None)
        self.assertEqual(loads(_b('123')), 123)
        self.assertEqual(loads(_b('-45.6')), -45.6)
        self.assertEqual(loads(_b('"hello"')), "hello")

    def test_object_and_array(self):
        payload = _b('{"a": [1, 2], "b": {"c": true}}')
        self.assertEqual(loads(payload), {"a": [1, 2], "b": {"c": True}})

    def test_ignore_keys(self):
        payload = _b('{"ignore1": [1,2,{"x":3}], "keep": 42, "ignore2": "skipped"}')
        self.assertEqual(loads(payload, ignore_keys={"ignore1", "ignore2"}), {"keep": 42})

    def test_string_with_escapes(self):
        payload = _b('{"text": "Line 1\\nLine 2", "quote": "\\""}')
        self.assertEqual(loads(payload), {"text": "Line 1\nLine 2", "quote": "\""})

    def test_unicode_escape(self):
        self.assertEqual(loads(_b('["\\u00A9"]')), ["©"])

    def test_empty_object_and_array(self):
        self.assertEqual(loads(_b('{}')), {})
        self.assertEqual(loads(_b('[]')), [])

    def test_whitespace_handling(self):
        payload = _b(' \n { \t "a" \r : \n 1 \t } \n ')
        self.assertEqual(loads(payload), {"a": 1})

    def test_bytes_input(self):
        self.assertEqual(loads(b'{"a": 1}'), {"a": 1})

    def test_bytearray_input(self):
        self.assertEqual(loads(bytearray(b'{"a": 1}')), {"a": 1})

    def test_skip_container_with_braces_inside_string(self):
        payload = _b('{"ignore": {"name": "Office {Test} }} weird {{{ value"}, "keep": 1}')
        self.assertEqual(loads(payload, ignore_keys={"ignore"}), {"keep": 1})

    def test_invalid_json_raises(self):
        with self.assertRaises(ValueError):
            loads(_b('{"a": 1]'))

    def test_unterminated_string_raises(self):
        with self.assertRaises(ValueError):
            loads(_b('{"a": "unterminated'))


def _random_json_value(depth, rand):
    if depth <= 0:
        choice = rand.randrange(4)
    else:
        choice = rand.randrange(6)

    if choice == 0:
        return rand.choice([True, False, None])
    if choice == 1:
        return rand.randint(-100000, 100000)
    if choice == 2:
        return round(rand.uniform(-1000, 1000), rand.randint(0, 6))
    if choice == 3:
        length = rand.randint(0, 12)
        alphabet = 'abcdefgh ij\\"kl\nmno\tpq_.:{}[]0123456789'
        return ''.join(rand.choice(alphabet) for _ in range(length))
    if choice == 4:
        return [_random_json_value(depth - 1, rand) for _ in range(rand.randint(0, 4))]
    return {
        'key%d' % i: _random_json_value(depth - 1, rand)
        for i in range(rand.randint(0, 4))
    }


class TestLoadsFuzzAgainstRealJson(unittest.TestCase):

    def test_random_payloads_match_stdlib_json(self):
        rand = random.Random(1234)
        for trial in range(200):
            value = {'root%d' % trial: _random_json_value(3, rand)}
            payload = json.dumps(value)
            expected = json.loads(payload)
            with self.subTest(trial=trial, payload=payload):
                self.assertEqual(loads(_b(payload)), expected)

    def test_random_payloads_with_ignored_keys_match_stdlib_json(self):
        rand = random.Random(5678)
        for trial in range(200):
            full_value = {'k%d' % i: _random_json_value(3, rand) for i in range(rand.randint(1, 6))}
            payload = json.dumps(full_value)
            ignored_keys = {k for k in full_value if rand.randrange(2) == 0}
            expected = {k: v for k, v in json.loads(payload).items() if k not in ignored_keys}
            with self.subTest(trial=trial, payload=payload, ignored_keys=ignored_keys):
                self.assertEqual(loads(_b(payload), ignore_keys=ignored_keys), expected)


if __name__ == '__main__':
    unittest.main()
