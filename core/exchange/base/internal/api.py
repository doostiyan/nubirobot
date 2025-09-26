from exchange.base.api import InternalAPIError


class MissingToken(InternalAPIError):
    pass


class InvalidToken(InternalAPIError):
    pass


class InvalidIp(InternalAPIError):
    pass


class PermissionDenied(InternalAPIError):
    pass

