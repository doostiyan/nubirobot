from ...utils.exception import NotFoundException


class AddressNotFoundException(NotFoundException):
    message_code = 'address_not_found'


