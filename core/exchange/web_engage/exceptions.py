class UnsupportedRequestVersion(Exception):
    pass


class InvalidPhoneNumber(Exception):
    pass


class RecipientBlackListed(Exception):
    pass


class RecipientAddressNotExist(Exception):
    pass


class ESPSendMessageException(Exception):
    def __init__(self, status_code, status_code_message, http_status_code):
        self.status_code = status_code
        self.status_code_message = status_code_message
        self.http_status_code = http_status_code

        super(ESPSendMessageException, self).__init__(f'status_code: {status_code},'
                                                      f' status_code_message: {status_code_message},'
                                                      f' http_status_code: {http_status_code}')

    def __reduce__(self):
        return ESPSendMessageException, (self.status_code, self.status_code_message, self.http_status_code)
