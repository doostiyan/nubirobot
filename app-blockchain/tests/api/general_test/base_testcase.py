from typing import Dict, List, Tuple, Type
from unittest import TestCase


class BaseTestCase(TestCase):

    def assertSchema(self, response: Dict, field_types: List[Tuple[str, Type | List]]):
        for field_name, field_type in field_types:
            self.assertIn(field_name, response)
            if isinstance(field_type, type):
                self.assertIsInstance(response[field_name], field_type)
            else:
                self.assertSchema(response[field_name], field_type)
