from exchange.blockchain.api.elrond.gateway_elrond import GatewayElrondApi, GatewayElrondValidator, \
    ElrondGatewayResponseParser


class ElrondApiValidator(GatewayElrondValidator):
    @classmethod
    def validate_general_response(cls, response):
        if response.get('code') != cls.successful_code:
            return False
        if response.get('data') is None:
            return False
        return True


class ElrondApiResponseParser(ElrondGatewayResponseParser):
    validator = ElrondApiValidator


class ElrondApi(GatewayElrondApi):
    _base_url = 'https://api.elrond.com'
    parser = ElrondApiResponseParser
    USE_PROXY = False
    instance = None
