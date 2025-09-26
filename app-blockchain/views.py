try:
    from ratelimit.decorators import ratelimit
except ImportError:
    from django_ratelimit.decorators import ratelimit

from exchange.base.api import public_post_api
from exchange.base.coins_info import CURRENCY_INFO
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.base.parsers import parse_currency, parse_choices
from exchange.blockchain.inspector import BlockchainInspector
from exchange.blockchain.utils import ParseError


@ratelimit(key='ip', rate='1000/m', block=True)
@public_post_api
def get_balance(request):
    """ POST /blockchain/get-balance
        Fetch current balance of the given addresses from blockchain
    """
    currency = parse_currency(request.g('currency', '').lower(), required=True)
    address = request.g('address')
    if not address:
        addresses = []
    else:
        addresses = address.split(',')

    balances = BlockchainInspector.get_wallets_balance(addresses, currency)

    return {
        'status': 'ok',
        'balances': balances,
    }


@ratelimit(key='ip', rate='1000/m', block=True)
@public_post_api
def get_transaction_details(request):
    """ POST /blockchain/get-balance
        Fetch current balance of the given addresses from blockchain
    """
    currency = parse_currency(request.g('currency', '').lower(), required=True)
    tx_hash = request.g('hash')
    network = request.g('network')
    if network is not None:
        network = str(network).upper()
    try:
        network = parse_choices(CurrenciesNetworkName, network) or CURRENCY_INFO[currency]['default_network']
    except ParseError:
        return {
            'status': 'failed',
            'code': 'NetworkInvalid',
            'message': 'Network is invalid'
        }
    if not tx_hash:
        return {
            'status': 'failed',
            'code': 'HashInvalid',
            'message': 'Transaction hash is empty'
        }

    result = BlockchainInspector.get_transaction_details(tx_hash=tx_hash, currency=currency, network=network)

    return {
        'status': 'ok',
        'result': result,
    }
