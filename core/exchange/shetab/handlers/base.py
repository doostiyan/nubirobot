"""Base class for handling all shetab gateways"""


class BaseShetabHandler:
    @classmethod
    def send_token_request(cls, deposit, request):
        return {}

    @classmethod
    def send_verify_request(cls, deposit):
        return {'amount': 0}

    @classmethod
    def sync(cls, deposit, request, **kwargs):
        return

    @classmethod
    def get_user_card_number(cls, deposit, retries=0):
        return None

    @classmethod
    def get_api_redirect_url(cls, deposit):
        return deposit.gateway_redirect_url or '#'
