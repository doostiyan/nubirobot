from exchange.explorer.utils.exception import NotFoundException


class TransactionNotFoundException(NotFoundException):
    message_code = 'transaction_not_found'


