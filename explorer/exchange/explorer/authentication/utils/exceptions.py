from ...utils.exception import NotFoundException


class APIKeyNotProvidedException(NotFoundException):
    code = 403
    message_code = 'api_key_not_provided'


class APIKeyNotFoundException(NotFoundException):
    code = 404
    message_code = 'api_key_not_found'
