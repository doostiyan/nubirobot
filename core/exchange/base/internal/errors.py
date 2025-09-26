from enum import Enum


class Errors(str, Enum):
    NOT_AN_INTERNAL_SERVER = 'NotAnInternalServer'
    UNAUTHORIZED_IP = 'UnauthorizedIP'
    MISSING_TOKEN = 'MissingToken'
    INVALID_TOKEN_FORMAT = 'InvalidTokenFormat'
    INVALID_TOKEN_SIGNATURE = 'InvalidToken'
    BLACKLISTED_TOKEN = 'BlacklistedToken'
    TOKEN_WITHOUT_SERVICE = 'TokenWithoutService'
    INVALID_SERVICE = 'InvalidService'
    UNKNOWN_TOKEN = 'UnknownToken'
