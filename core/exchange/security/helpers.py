from enum import Enum


class AddressBookNotificationType(Enum):
    NEW_ADDRESS = "NewAddress"
    DEACTIVATED = "Deactivated"

    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_


class AddressBookRestrictionType(Enum):
    DISABLE_WHITELIST_MODE = "DeactivateWhitelist"
    NEW_ADDRESS = "NewAddress"

    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_
