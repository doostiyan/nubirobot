from html.parser import incomplete

from django.utils.translation import gettext_lazy as _

from exchange.base.models import Currencies
from exchange.base.parsers import ParseError, parse_currency
from exchange.blockchain.explorer import BlockchainExplorer as BE

from .exception import NotFoundException
from ..networkproviders.models import Operation

network_main_currencies = {
    'matic': 'pol',
    'bsc': 'bnb',
    'base': 'eth',
}

def get_currency2parse(currency, network):
    network = network.lower()
    currency = (currency or '').lower()

    if currency:
        return currency
    if network in network_main_currencies:
        return network_main_currencies[network]
    return network


def is_main_currency_of_network(currency, network):
    network = network.lower()
    currency = (currency or '').lower()

    if currency == network:
        return True

    return network_main_currencies.get(network) == currency


def get_currency_symbol_from_currency_code(currency_code):
    for k, v in Currencies._identifier_map.items():
        if v == currency_code:
            return k.upper()


def parse_currency2code_and_symbol(currency2parse):
    if currency2parse in ('bsc', 'polygon'):
        return None, currency2parse
    try:
        return parse_currency(currency2parse, required=True), currency2parse
    except ParseError:
        for c in Currencies:
            if c[1].lower() == currency2parse:
                return c[0], get_currency_symbol_from_currency_code(c[0])
        raise NotFoundException(_('Network or currency parameters not found'))


def parse_currency2code(currency2parse):
    try:
        return parse_currency(currency2parse)
    except ParseError:
        raise NotFoundException(_('Network or currency parameters not found'))


ready_networks = {
    Operation.TX_DETAILS: [*BE.TX_DETAILS_TESTING_NETWORKS, *BE.TX_DETAILS_TESTED_NETWORKS,
                           'ADA', 'ALGO', 'APT', 'AVAX', 'BNB', 'BSC', 'DOT', 'ETH', 'FIL','FLOW', 'ONE', 'TON', 'TRX', 'XTZ', 'ENJ'],
    Operation.BLOCK_TXS: [*BE.BLOCK_TXS_TESTING_NETWORKS, *BE.BLOCK_TXS_TESTED_NETWORKS],
    Operation.BLOCK_HEAD: [*BE.BLOCK_TXS_TESTING_NETWORKS, *BE.BLOCK_TXS_TESTED_NETWORKS],
    Operation.ADDRESS_TXS: [*BE.WALLET_TXS_TESTING_NETWORKS, *BE.WALLET_TXS_TESTED_NETWORKS,
                            'BCH', 'BTC', 'DOT', 'EGLD', 'ENJ', 'EOS','ETC', 'ETH', 'FLOW', 'TON', 'XTZ'],
    Operation.BALANCE: [*BE.BALANCE_TESTING_NETWORKS, *BE.BALANCE_TESTED_NETWORKS],
}

tagged_networks = ['ATOM', 'TON']
incomplete_block_txs_networks = ['ARB']
high_transaction_networks = ['SOL']

def is_network_ready(network, service):
    if network in ready_networks.get(service):
        return True
    return False


def is_network_address_txs_double_checkable(network):
    if network in [*tagged_networks, *incomplete_block_txs_networks]:
        return False
    return True
