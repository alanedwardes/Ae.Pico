import os
import sys
import json
import random
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../libraries')))
from flatjson import load


class MockAsyncIterable:
    def __init__(self, data_str, chunk_size=5):
        self.data_str = data_str
        self.chunk_size = chunk_size
        self.pos = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.pos >= len(self.data_str):
            raise StopAsyncIteration
        chunk = self.data_str[self.pos:self.pos + self.chunk_size]
        self.pos += len(chunk)
        return chunk


class TestTruncatedStream(unittest.IsolatedAsyncioTestCase):

    async def test_stream_ends_mid_string_does_not_raise(self):
        payload = '{"a":"this string never gets a closing quote'
        result = await load(MockAsyncIterable(payload, 3))
        self.assertEqual(result, {'a': 'this string never gets a closing quote'})

    async def test_stream_ends_immediately_after_opening_quote(self):
        payload = '{"a":"'
        result = await load(MockAsyncIterable(payload, 3))
        self.assertEqual(result, {'a': ''})

    async def test_stream_ends_mid_escape_sequence(self):
        payload = '{"a":"abc\\'
        result = await load(MockAsyncIterable(payload, 3))
        self.assertEqual(result, {'a': 'abc'})

    async def test_stream_ends_mid_number(self):
        payload = '{"a":123.4'
        result = await load(MockAsyncIterable(payload, 3))
        self.assertEqual(result, {'a': 123.4})


class TestLargeStringsCrossThePiecesFlushThreshold(unittest.IsolatedAsyncioTestCase):

    async def test_string_over_1024_bytes_matches_expected(self):
        for chunk_size in (7, 64, 4096):
            with self.subTest(chunk_size=chunk_size):
                long_string = 'x' * 3000
                payload = json.dumps({'a': long_string})
                result = await load(MockAsyncIterable(payload, chunk_size))
                self.assertEqual(result, {'a': long_string})

    async def test_string_with_escapes_straddling_the_flush_threshold(self):
        for chunk_size in (7, 64, 4096):
            with self.subTest(chunk_size=chunk_size):
                pieces = ['y' * 1020, '\\"', 'z' * 2000]
                expected = 'y' * 1020 + '"' + 'z' * 2000
                payload = '{"a":"' + ''.join(pieces) + '"}'
                result = await load(MockAsyncIterable(payload, chunk_size))
                self.assertEqual(result, {'a': expected})

    async def test_ignored_string_over_1024_bytes_is_skipped_correctly(self):
        for chunk_size in (7, 64, 4096):
            with self.subTest(chunk_size=chunk_size):
                payload = json.dumps({'ignore': 'x' * 3000, 'keep': 1})
                result = await load(MockAsyncIterable(payload, chunk_size), ignore_keys={'ignore'})
                self.assertEqual(result, {'keep': 1})


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


class TestFuzzAgainstRealJson(unittest.IsolatedAsyncioTestCase):

    async def test_random_payloads_match_stdlib_json_across_chunk_sizes(self):
        rand = random.Random(1234)
        chunk_sizes = (1, 2, 3, 7, 17, 64, 4096)

        for trial in range(60):
            value = {'root%d' % trial: _random_json_value(3, rand)}
            payload = json.dumps(value)
            expected = json.loads(payload)

            for chunk_size in chunk_sizes:
                with self.subTest(trial=trial, chunk_size=chunk_size, payload=payload):
                    result = await load(MockAsyncIterable(payload, chunk_size))
                    self.assertEqual(result, expected)

    async def test_random_payloads_with_ignored_keys_match_stdlib_json(self):
        rand = random.Random(5678)
        chunk_sizes = (1, 2, 3, 7, 17, 64, 4096)

        for trial in range(60):
            full_value = {'k%d' % i: _random_json_value(3, rand) for i in range(rand.randint(1, 6))}
            payload = json.dumps(full_value)
            ignored_keys = {k for k in full_value if rand.randrange(2) == 0}
            expected = {k: v for k, v in json.loads(payload).items() if k not in ignored_keys}

            for chunk_size in chunk_sizes:
                with self.subTest(trial=trial, chunk_size=chunk_size, payload=payload, ignored_keys=ignored_keys):
                    result = await load(MockAsyncIterable(payload, chunk_size), ignore_keys=ignored_keys)
                    self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
