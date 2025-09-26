from exchange.blockchain.models import Currencies
from exchange.blockchain.api.commons.blockscan import BlockScanResponseParser, BlockScanResponseValidator
from exchange.blockchain.api.general.jsonrpc import JSONRPCClientMixin


class FlareAnkrValidator(BlockScanResponseValidator):
    pass


class FlareAnkrParser(BlockScanResponseParser):
    validator = FlareAnkrValidator
    symbol = 'FLR'
    currency = Currencies.flr


class FlareAnkrApi(JSONRPCClientMixin):
    symbol = 'FLR'
    _base_url: str = 'https://rpc.ankr.com/flare'
    supported_requests: dict = {
        'get_block_head': '',
        'get_block_txs': '',
        'get_tx_details': '',
        'get_tx_receipt': '',
    }
    parser = FlareAnkrParser
    cache_key = 'flr'

    @classmethod
    def get_block_txs(cls, block_height):
        return cls.request(request_method='get_block_txs', height=hex(block_height), apikey=cls.get_api_key(),
                           headers=cls.get_headers(), body=cls.get_block_txs_body(hex(block_height)))
