from ...utils.exception import NotFoundException


class UserNotFoundException(NotFoundException):
    message_code = 'user_not_found'
