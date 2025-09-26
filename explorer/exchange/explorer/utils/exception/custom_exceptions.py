class CustomException(Exception):
    code = 500
    message_code = 'custom_exception'

    def __init__(self, detail=''):
        self.detail = detail

    def __str__(self):
        return self.message_code


class NotFoundException(CustomException):
    code = 404
    message_code = 'not_found'


class NetworkNotFoundException(NotFoundException):
    message_code = 'network_not_found'


class CurrencyNotFoundException(NotFoundException):
    message_code = 'currency_not_found'


class ProviderNotFoundException(NotFoundException):
    message_code = 'provider_not_found'


class URLNotFoundException(NotFoundException):
    message_code = 'url_not_found'


class BadRequestException(CustomException):
    code = 400
    message_code = 'bad_request'


class QueryParamMissingException(BadRequestException):

    def __init__(self, missing_params=None):
        missing_params = missing_params or []
        self.detail = 'missing query params: {}'.format(','.join(missing_params))
