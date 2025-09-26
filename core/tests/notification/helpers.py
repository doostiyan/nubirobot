class Request:
    def __init__(self, output: dict = None):
        sample_output = {
            'TokenKey': '14256',
            'IsSuccessful': True,
            'VerificationCodeId': 12456,
            'BatchKey': 1235,
            'ids': [{'id': 14425}],
        }

        self.output = output or sample_output

    def raise_for_status(self):
        pass

    def json(self):
        return self.output
