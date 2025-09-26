from enum import Enum


class ValidatorStatus(str, Enum):
    JAILED = 'Jailed'
    ACTIVE = 'Active'
    IN_ACTIVE = 'InActive'
