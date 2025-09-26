from unittest.mock import patch


class faketime:
    def sleep(_):
        return None

patcher = patch('exchange.accounts.views.auth.time', faketime)
patcher.start()
