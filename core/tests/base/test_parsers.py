import unittest
import pytest

from exchange.base.api import ParseError
from exchange.base.parsers import parse_limited_length_string


class ParsersTest(unittest.TestCase):
    def test_parse_limited_length_string(self):
        assert parse_limited_length_string('', 2) == ''
        assert parse_limited_length_string('a', 2) == 'a'
        assert parse_limited_length_string('ab', 2) == 'ab'
        pytest.raises(ParseError, parse_limited_length_string, 'abc', 2)
        pytest.raises(ParseError, parse_limited_length_string, None, 2)

    # TODO: Add unit tests for other parser functions.
