from typing import Dict, List, Type, Union
from unittest import TestCase


class BaseTestCase(TestCase):

    def assert_schema(self, got_value: Union[Dict, List], schema: Dict[str, Union[Type, Dict]], route: str = ''):
        # if value is of type List validating schema on all elements
        if isinstance(got_value, List):
            for value in got_value:
                self.assert_schema(value, schema, route)
            return
        # if value is of type Dict validating schema recursively
        for name, typ in schema.items():
            current_route = name if route == '' else route + '.' + name
            assert name in got_value, route
            if isinstance(typ, dict):
                self.assert_schema(got_value[name], typ, current_route)
            else:
                assert isinstance(got_value[name], typ), current_route
