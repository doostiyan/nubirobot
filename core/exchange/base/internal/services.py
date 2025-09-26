from enum import Enum


class Services(str, Enum):
    ABC = 'abc'
    ADMIN = 'admin'
    CORE = 'core'

    @classmethod
    def choices(cls):
        return [(item.value, item.name) for item in cls]
