from typing import Dict, List, Type, Union


class TestApiCallUtils:
    @staticmethod
    def assert_schema(got_value: Union[Dict, List], schema: Dict[str, Union[Type, Dict]], route: str = '') -> None:
        # if value is of type List validating schema on all elements
        if isinstance(got_value, List):
            for value in got_value:
                TestApiCallUtils.assert_schema(value, schema, route)
            return
        # if value is of type Dict validating schema recursively
        for name, typ in schema.items():
            current_route = name if route == '' else route + '.' + name
            assert name in got_value, current_route
            # value is of type dict so check recursively for all elements of dictionary in got_value
            if isinstance(typ, dict):
                TestApiCallUtils.assert_schema(got_value[name], typ, current_route)
            else:
                assert isinstance(got_value[name], typ), current_route
