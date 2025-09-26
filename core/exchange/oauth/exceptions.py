class OauthException(Exception):
    pass


class AuthorizationException(OauthException):
    code: str
    message: str

    def __init__(self, code='InvalidRequest', message='invalid request'):
        self.code = code
        self.message = message


class InactiveUser(OauthException):
    code: str
    message: str

    def __init__(self, code='UnavailableUser', message='Cannot receive authorization for this user.'):
        self.code = code
        self.message = message
