class InvalidResponseError(Exception):
    def __init__(self, response: any) -> None:
        super().__init__(str(response))
