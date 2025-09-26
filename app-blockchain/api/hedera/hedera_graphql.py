from exchange.blockchain.api.hedera.hedera_mirrornode import MirrorNodeHederaValidator, \
    MirrorNodeHederaResponseParser, MirrorNodeHederaApi
from decimal import Decimal
from exchange.blockchain.utils import BlockchainUtilsMixin


class GraphqlHederaValidator(MirrorNodeHederaValidator):

    @classmethod
    def validate_balance_response(cls, balance_response) -> bool:
        if not balance_response.get('account'):
            return False
        if not balance_response.get('balance'):
            return False
        if balance_response.get('balance').get('balance') is None:
            return False
        return True


class GraphqlHederaResponseParser(MirrorNodeHederaResponseParser):
    validator = GraphqlHederaValidator

    @classmethod
    def parse_balance_response(cls, balance_response) -> Decimal:
        if cls.validator.validate_balance_response(balance_response):
            return BlockchainUtilsMixin.from_unit(balance_response.get('balance').get('balance'), cls.precision)
        return Decimal(0)


class GraphqlHederaApi(MirrorNodeHederaApi):
    parser = GraphqlHederaResponseParser
    """
        coins: hbar
        Explorer: https://hederaexplorer.io/
    """
    instance = None
    _base_url = 'https://mainnet.graphql.hederaexplorer.io/'
    testnet_url = 'https://testnet.graphql.hederaexplorer.io/'
    supported_requests = {
        'get_balance': 'data/accounts/{address}?limit=1',
        'get_address_txs': 'data/accounts/{address}?limit=25&order=desc',
        'get_tx_details': 'data/transactions/{tx_hash}'
    }
    USE_PROXY = False
    symbol = 'HBAR'

