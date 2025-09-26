from exchange.blockchain.api.elrond.gateway_elrond import GatewayElrondApi, GatewayElrondValidator, \
    ElrondGatewayResponseParser


class MultiversxApiValidator(GatewayElrondValidator):
    @classmethod
    def validate_general_response(cls, response):
        if response.get('code') != cls.successful_code:
            return False
        if response.get('data') is None:
            return False
        return True


class MultiversxApiResponseParser(ElrondGatewayResponseParser):
    validator = MultiversxApiValidator


class MultiversxApi(GatewayElrondApi):
    _base_url = 'https://api.multiversx.com'
    parser = MultiversxApiResponseParser
    USE_PROXY = False
    instance = None
