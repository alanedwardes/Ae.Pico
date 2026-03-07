import sys
import asyncio
import unittest

sys.path.insert(1, '../libraries')
from flatjson import load, load_array, loads

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
        
        chunk = self.data_str[self.pos:self.pos+self.chunk_size]
        self.pos += self.chunk_size
        return chunk


class TestAsyncIterableJsonParser(unittest.IsolatedAsyncioTestCase):

    async def test_parse_empty_dict_empty_result(self):
        # Emulates Home Assistant empty dict response
        payload = '{"id": 2, "type": "result", "success": true, "result": {}}'
        result = await load(MockAsyncIterable(payload, 2))
        self.assertEqual(result, {"id": 2, "type": "result", "success": True, "result": {}})

    async def test_parse_empty_array_result(self):
        # Emulates Home Assistant empty array response (which caused the error)
        payload = '{"id": 2, "type": "result", "success": true, "result": []}'
        result = await load(MockAsyncIterable(payload, 2))
        self.assertEqual(result, {"id": 2, "type": "result", "success": True, "result": []})
        
    async def test_parse_negative_number(self):
        payload = '{"id": -1, "type": "result", "success": false}'
        result = await load(MockAsyncIterable(payload, 2))
        self.assertEqual(result, {"id": -1, "type": "result", "success": False})

    async def test_parse_nested_array(self):
        payload = '{"a": [1, 2, [3, 4]]}'
        result = await load(MockAsyncIterable(payload, 2))
        self.assertEqual(result, {"a": [1, 2, [3, 4]]})

    async def test_parse_fast_skip_nested_array(self):
        # The fast skip implementation must correctly handle closing brackets
        payload = '{"id": 2, "ignore": [{"nested": [1, [2]]}], "keep": true}'
        result = await load(MockAsyncIterable(payload, 2), ignore_keys={"ignore"})
        self.assertEqual(result, {"id": 2, "keep": True})

    async def test_empty_string_number(self):
        # Test strict trailing missing values evaluate to ValueError
        payload = '{"bad": }'
        with self.assertRaises(ValueError):
             await load(MockAsyncIterable(payload, 2))

    async def test_parse_true(self):
        payload = '{"value": true}'
        result = await load(MockAsyncIterable(payload, 2))
        self.assertEqual(result, {"value": True})

    async def test_parse_false(self):
        payload = '{"value": false}'
        result = await load(MockAsyncIterable(payload, 2))
        self.assertEqual(result, {"value": False})

    async def test_parse_null(self):
        payload = '{"value": null}'
        result = await load(MockAsyncIterable(payload, 2))
        self.assertEqual(result, {"value": None})

    async def test_parse_float(self):
        payload = '{"value": 1.23, "value2": -4.56, "value3": 1e-5}'
        result = await load(MockAsyncIterable(payload, 2))
        self.assertEqual(result, {"value": 1.23, "value2": -4.56, "value3": 1e-5})

    async def test_parse_string_with_escapes(self):
        payload = '{"text": "Line 1\\nLine 2", "quote": "\\""}'
        result = await load(MockAsyncIterable(payload, 2))
        self.assertEqual(result, {"text": "Line 1\nLine 2", "quote": "\""})

    async def test_fast_skip_string_with_escapes(self):
        payload = '{"ignore": "skip \\" this", "keep": 1}'
        result = await load(MockAsyncIterable(payload, 2), ignore_keys={"ignore"})
        self.assertEqual(result, {"keep": 1})

    async def test_fast_skip_array_with_nested_objects(self):
        payload = '{"ignore": [{"a": 1}, {"b": 2}], "keep": 1}'
        result = await load(MockAsyncIterable(payload, 2), ignore_keys={"ignore"})
        self.assertEqual(result, {"keep": 1})

    async def test_fast_skip_multikey(self):
        payload = '{"i1": 1, "keep": 2, "i2": {"x": 3}}'
        result = await load(MockAsyncIterable(payload, 2), ignore_keys={"i1", "i2"})
        self.assertEqual(result, {"keep": 2})

    async def test_whitespace_handling(self):
        payload = ' \n { \t "a" \r : \n 1 \t } \n '
        result = await load(MockAsyncIterable(payload, 2))
        self.assertEqual(result, {"a": 1})

    async def test_chunk_size_1(self):
        # Stresses the buffer boundary logic
        payload = '{"a": [{"b": 1}], "c": "test", "d": true, "e": 1.23}'
        result = await load(MockAsyncIterable(payload, 1))
        self.assertEqual(result, {"a": [{"b": 1}], "c": "test", "d": True, "e": 1.23})

    async def test_invalid_json_unexpected_char(self):
        payload = '{"a": 1]'
        with self.assertRaises(ValueError):
            await load(MockAsyncIterable(payload, 2))

    async def test_unexpected_object_char(self):
        payload = '{"a": 1, ]}'
        with self.assertRaises(ValueError):
            await load(MockAsyncIterable(payload, 2))

    async def test_parse_complex_object(self):
        payload = '{"user": {"id": 101, "name": "Alice", "active": true, "roles": ["admin", "user"], "stats": {"logins": 42, "last_login": null}}, "metadata": {"version": 1.0}}'
        result = await load(MockAsyncIterable(payload, 5))
        self.assertEqual(result, {
            "user": {
                "id": 101,
                "name": "Alice",
                "active": True,
                "roles": ["admin", "user"],
                "stats": {
                    "logins": 42,
                    "last_login": None
                }
            },
            "metadata": {"version": 1.0}
        })

    async def test_parse_deeply_nested_structures(self):
        payload = '{"level1": {"level2": {"level3": {"level4": [1, [2, {"level5": true}]]}}}}'
        result = await load(MockAsyncIterable(payload, 3))
        self.assertEqual(result, {
            "level1": {"level2": {"level3": {"level4": [1, [2, {"level5": True}]]}}}
        })

    async def test_parse_complex_object_with_whitespace(self):
        payload = '''
        {
            "widget": {
                "debug": "on",
                "window": {
                    "title": "Sample Konfabulator Widget",
                    "name": "main_window",
                    "width": 500,
                    "height": 500
                },
                "image": { 
                    "src": "Images/Sun.png",
                    "name": "sun1",
                    "hOffset": 250,
                    "vOffset": 250,
                    "alignment": "center"
                },
                "text": {
                    "data": "Click Here",
                    "size": 36,
                    "style": "bold",
                    "name": "text1",
                    "hOffset": 250,
                    "vOffset": 100,
                    "alignment": "center",
                    "onMouseUp": "sun1.opacity = (sun1.opacity / 100) * 90;"
                }
            }
        }
        '''
        expected = {
            "widget": {
                "debug": "on",
                "window": {
                    "title": "Sample Konfabulator Widget",
                    "name": "main_window",
                    "width": 500,
                    "height": 500
                },
                "image": { 
                    "src": "Images/Sun.png",
                    "name": "sun1",
                    "hOffset": 250,
                    "vOffset": 250,
                    "alignment": "center"
                },
                "text": {
                    "data": "Click Here",
                    "size": 36,
                    "style": "bold",
                    "name": "text1",
                    "hOffset": 250,
                    "vOffset": 100,
                    "alignment": "center",
                    "onMouseUp": "sun1.opacity = (sun1.opacity / 100) * 90;"
                }
            }
        }
        result = await load(MockAsyncIterable(payload, 10))
        self.assertEqual(result, expected)


class MockAsyncReader:
    def __init__(self, data_bytes, chunk_size=5):
        self.data_bytes = data_bytes
        self.chunk_size = chunk_size
        self.pos = 0

    async def read(self, n):
        if self.pos >= len(self.data_bytes):
            return b""
        size = min(n, self.chunk_size)
        chunk = self.data_bytes[self.pos:self.pos+size]
        self.pos += size
        return chunk


class TestFlatJsonParser(unittest.IsolatedAsyncioTestCase):
    async def test_parse_flat_array(self):
        payload = b' [ 1, "text", true , false, null, 1.23, -42, "escaped\\"quote" ] '
        reader = MockAsyncReader(payload, 3)
        parser = load_array(reader)
        
        results = []
        async for item in parser:
            results.append(item)
            
        self.assertEqual(results, [1, "text", True, False, None, 1.23, -42, 'escaped"quote'])

    async def test_parse_unicode_escape(self):
        payload = b'["\\u00A9"]' # Copyright symbol
        reader = MockAsyncReader(payload, 2)
        parser = load_array(reader)
        results = [item async for item in parser]
        self.assertEqual(results, ["\u00A9"]) # The parser returns string "\u00A9"


class TestStringJsonParser(unittest.TestCase):
    def test_parse_basic_types(self):
        self.assertEqual(loads('true'), True)
        self.assertEqual(loads('false'), False)
        self.assertEqual(loads('null'), None)
        self.assertEqual(loads('123'), 123)
        self.assertEqual(loads('-45.6'), -45.6)
        self.assertEqual(loads('"hello"'), "hello")

    def test_parse_object_and_array(self):
        payload = '{"a": [1, 2], "b": {"c": true}}'
        self.assertEqual(loads(payload), {"a": [1, 2], "b": {"c": True}})

    def test_fast_skip_object_keys(self):
        payload = '{"ignore1": [1,2,{"x":3}], "keep": 42, "ignore2": "skipped"}'
        self.assertEqual(loads(payload, ignore_keys={"ignore1", "ignore2"}), {"keep": 42})

    def test_parse_complex_nested_structure(self):
        payload = '{"status": "ok", "data": [{"id": 1, "value": [true, false, null, {"a": 1, "b": "str", "c": [1.1, 2.2]}]}, {"id": -2, "value": []}]}'
        expected = {
            "status": "ok", 
            "data": [
                {
                    "id": 1, 
                    "value": [True, False, None, {"a": 1, "b": "str", "c": [1.1, 2.2]}]
                }, 
                {
                    "id": -2, 
                    "value": []
                }
            ]
        }
        self.assertEqual(loads(payload), expected)

    def test_parse_complex_arrays(self):
        # Arrays containing mixed types and nested arrays/objects
        payload = '[1, "two", {"three": 3}, [4, 5, {"six": 6}], null, true]'
        expected = [1, "two", {"three": 3}, [4, 5, {"six": 6}], None, True]
        self.assertEqual(loads(payload), expected)

if __name__ == "__main__":
    unittest.main()
