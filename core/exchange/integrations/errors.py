from typing import Optional


class ConnectionFailedException(Exception):
    def __init__(self, actual_exception: Optional[str] = None):
        self.actual_exception = actual_exception


class APICallException(Exception):
    """
    API returned a result we cannot undrestand
    """

    def __init__(self, status_code: Optional[int] = None, response_body: Optional[str] = None):
        self.status_code = status_code
        self.response_body = response_body


class APICallProviderError(Exception):
    pass


class APIResponseCodeError(Exception):
    def __init__(self, track_id: Optional[int] = None, message: Optional[str] = None):
        self.track_id = track_id
        self.message = message
