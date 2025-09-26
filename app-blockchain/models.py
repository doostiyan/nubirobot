import inspect
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, Union

import requests
from django.conf import settings
from model_utils import Choices

from exchange.base.coins_info import CURRENCY_INFO

# because blockchain submodule exists under both core and cold projects
if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold':
    from wallet.models import CURRENCIES as Currencies  # if you are working on cold project
else:
    from exchange.base.models import Currencies  # if you are working on core project


class NobitexInspectorError(Exception):
    pass


class Transaction:
    def __init__(
            self,
            address: Optional[str] = None,
            from_address: Optional[Union[str, list]] = None,
            hash: Optional[str] = None,  # noqa: A002
            block: Optional[int] = None,
            timestamp: Optional[datetime] = None,
            value: Optional[Decimal] = None,
            confirmations: Optional[int] = None,
            is_double_spend: Optional[bool] = None,
            details: Optional[dict] = None,
            tag: Optional[str] = None,
            huge: bool = False,
            invoice: Optional[str] = None,
            contract_address: Optional[str] = None,
    ) -> None:
        self.contract_address = contract_address
        self.address = address
        self.from_address = from_address or []
        self.hash = hash
        self.block = block or None
        self.timestamp = timestamp
        self.value = value
        self.confirmations = confirmations
        self.is_double_spend = is_double_spend
        self.details = details or {}
        self.tag = tag
        self.huge = huge
        self.invoice = invoice

    def __getitem__(self, key: Any) -> Any:  # noqa: ANN401
        return self.details.get(key)

    def __str__(self) -> str:
        return f'BlockchainTransaction #{self.hash}'

    def __lt__(self, other) -> bool:  # noqa: ANN001
        return self.timestamp < other.timestamp


# ruff: noqa
class BaseBlockchainInspector:
    api_sessions = {}
    USE_PROXY = False if settings.IS_PROD and settings.NO_INTERNET and not settings.IS_VIP else False
    TESTNET_ENABLED = False
    FAKE_USER_AGENT = False

    currency = None
    ignore_network_list = []
    get_balance_method = {}
    get_transactions_method = {}
    get_transaction_details_method = {}

    @classmethod
    def get_session(cls, use_proxy=False):
        """ Get a common requests.Session object for sending API requests
        """
        session_key = 'proxied' if use_proxy else 'default'
        api_session = cls.api_sessions.get(session_key)
        if api_session is None:
            api_session = requests.Session()
            if cls.USE_PROXY or use_proxy:
                if settings.DEFAULT_PROXY:
                    api_session.proxies.update(settings.DEFAULT_PROXY)
            if cls.FAKE_USER_AGENT:
                api_session.headers['User-Agent'] = (
                    'Mozilla/5.0 (X11; Linux x86_64; rv:75.0) Gecko/20100101 Firefox/75.0' if not settings.IS_VIP else
                    'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/109.0')
            cls.api_sessions[session_key] = api_session
        return api_session

    @classmethod
    def get_explorer_url(cls):
        raise NobitexInspectorError('This should be overridden by the child')

    @classmethod
    def get_wallets_balance(cls, address_list_per_network):
        res_balances = defaultdict(list)
        for network in address_list_per_network:
            if network in cls.ignore_network_list:
                continue
            address_list = address_list_per_network.get(network)
            balances = getattr(cls, cls.get_balance_method.get(network))(address_list) or {}
            if isinstance(balances, list):
                balances = {cls.currency: balances}
            for currency_list in (res_balances, balances):
                for currency, currency_balances in currency_list.items():
                    res_balances[currency].extend(currency_balances)
        return res_balances

    @classmethod
    def get_wallet_transactions(cls, address, network=None):
        if network in cls.ignore_network_list:
            return []
        transactions = defaultdict(list)
        network_txs = getattr(cls, cls.get_transactions_method.get(network))(address) or {}
        if isinstance(network_txs, list):
            network_txs = {cls.currency: network_txs}
        for currency_list in (transactions, network_txs):
            for currency, currency_balances in currency_list.items():
                transactions[currency].extend(currency_balances)
        return transactions

    @classmethod
    def get_transaction_details(cls, tx_hash, network=None):
        network_txs = getattr(cls, cls.get_transaction_details_method.get(network))(tx_hash=tx_hash)
        return network_txs


def get_token_code(currency_code: str, token_type: str) -> int:
    if currency_code == 'inch':
        currency_code = '1inch'
    if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold':
        return getattr(Currencies, f'{currency_code.lower()}_{token_type}')
    return getattr(Currencies, currency_code)


class CurrenciesNetworkName:
    ADA = 'ADA'
    ALGO = 'ALGO'
    APT = 'APT'
    ARB = 'ARB'
    AVAX = 'AVAX'
    ATOM = 'ATOM'
    BASE = 'BASE'
    BCH = 'BCH'
    BNB = 'BNB'
    BSC = 'BSC'
    BTC = 'BTC'
    DASH = 'DASH'
    DOGE = 'DOGE'
    DOT = 'DOT'
    EOS = 'EOS'
    EGLD = 'EGLD'
    ENJ = 'ENJ'
    ETC = 'ETC'
    ETH = 'ETH'
    FIL = 'FIL'
    FLOW = 'FLOW'
    FLR = 'FLR'
    FTM = 'FTM'
    HBAR = 'HBAR'
    IOTA = 'IOTA'
    LUNA = 'LUNA'
    LTC = 'LTC'
    MATIC = 'MATIC'
    NEAR = 'NEAR'
    NEO = 'NEO'
    OMNI = 'OMNI'
    ONE = 'ONE'
    PMN = 'PMN'
    QTUM = 'QTUM'
    SONIC = 'SONIC'
    SOL = 'SOL'
    SUI = 'SUI'
    TON = 'TON'
    TRX = 'TRX'
    XEM = 'XEM'
    XLM = 'XLM'
    XMR = 'XMR'
    XRP = 'XRP'
    XTZ = 'XTZ'
    ZEC = 'ZEC'
    ZTRX = 'ZTRX'
    FIAT_MONEY = 'FIAT_MONEY'

    NETWORKS_NATIVE_CURRENCY = {
        'ADA': Currencies.ada,
        'ALGO': Currencies.algo,
        'APT': Currencies.apt,
        'ARB': Currencies.eth,
        'AVAX': Currencies.avax,
        'ATOM': Currencies.atom,
        'BASE': Currencies.eth,
        'BCH': Currencies.bch,
        'BNB': Currencies.bnb,
        'BSC': Currencies.bnb,
        'BTC': Currencies.btc,
        'DASH': Currencies.dash,
        'DOGE': Currencies.doge,
        'DOT': Currencies.dot,
        'EOS': Currencies.eos,
        'EGLD': Currencies.egld,
        'ENJ': Currencies.enj,
        'ETC': Currencies.etc,
        'ETH': Currencies.eth,
        'FIL': Currencies.fil,
        'FLOW': Currencies.flow,
        'FLR': Currencies.flr,
        'FTM': Currencies.ftm,
        'HBAR': Currencies.hbar,
        'IOTA': Currencies.iota,
        'LUNA': Currencies.luna,
        'LTC': Currencies.ltc,
        'MATIC': Currencies.pol,
        'NEAR': Currencies.near,
        'NEO': Currencies.neo,
        'OMNI': Currencies.usdt,
        'ONE': Currencies.one,
        'PMN': Currencies.pmn,
        'QTUM': Currencies.qtum,
        'SONIC': Currencies.s,
        'SOL': Currencies.sol,
        'TON': Currencies.ton,
        'TRX': Currencies.trx,
        'XEM': Currencies.xem,
        'XLM': Currencies.xlm,
        'XMR': Currencies.xmr,
        'XRP': Currencies.xrp,
        'XTZ': Currencies.xtz,
        'ZTRX': Currencies.usdt,
    }

    PSEUDO_NETWORKS_CONTRACTS = {
        '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2': {
            'title': 'WETH-ETH',
            'real_network': ETH,
            'destination_currency': Currencies.eth,
            'info': {
                'address': '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2',
                'decimals': 18,
                'symbol': 'ETH',
            },
        },
        '0x82af49447d8a07e3bd95bd0d56f35241523fbab1': {
            'title': 'WETH-ARB',
            'real_network': ARB,
            'destination_currency': Currencies.eth,
            'info': {
                'address': '0x82af49447d8a07e3bd95bd0d56f35241523fbab1',
                'decimals': 18,
                'symbol': 'ETH',
            },
        },
        '0xaf88d065e77c8cc2239327c5edb3a432268e5831': {
            'title': 'USDC-ARB',
            'real_network': ARB,
            'destination_currency': Currencies.usdc,
            'info': {
                'address': '0xaf88d065e77c8cc2239327c5edb3a432268e5831',
                'decimals': 6,
                'symbol': 'USDC',
            },
        },
        '0x3c499c542cef5e3811e1192ce70d8cc03d5c3359': {
            'title': 'USDC-MATIC',
            'real_network': MATIC,
            'destination_currency': Currencies.usdc,
            'info': {
                'address': '0x3c499c542cef5e3811e1192ce70d8cc03d5c3359',
                'decimals': 6,
                'symbol': 'USDC',
            },
        },
    }

    CURRENCIES_PSEUDO_NETWORKS = {
        Currencies.eth: {
            'WETH-ETH': '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2',
            'WETH-ARB': '0x82af49447d8a07e3bd95bd0d56f35241523fbab1',
        },
        Currencies.usdc: {
            'USDC-ARB': '0xaf88d065e77c8cc2239327c5edb3a432268e5831',
            'USDC-MATIC': '0x3c499c542cef5e3811e1192ce70d8cc03d5c3359',
        },
    }

    @classmethod
    def array(cls) -> list:
        return cls.get_class_attributes()

    @classmethod
    def get_class_attributes(cls) -> list:
        not_included_keys = ['NETWORKS_NATIVE_CURRENCY', 'CURRENCIES_PSEUDO_NETWORKS', 'PSEUDO_NETWORKS_CONTRACTS']
        return [item for item in inspect.getmembers(cls) if
                not item[0].startswith('__') and not inspect.ismethod(item[1]) and item[0] not in not_included_keys]

    @classmethod
    def binance_to_nobitex(cls, network: str) -> Optional[str]:
        # AVAX is x-chain in binance
        if network == 'AVAX':
            return None
        if network == 'SEGWITBTC':
            return None
        if network == 'AVAXC':
            network = 'AVAX'
        elif network == 'ARBITRUM':
            network = 'ARB'

        return getattr(cls, network, None)

    @classmethod
    def nobitex_to_binance(cls, network: str) -> str:
        # AVAX is c-chain in nobitex
        if network == 'AVAX':
            return 'AVAXC'
        if network == 'ARB':
            return 'ARBITRUM'
        return getattr(cls, network)

    @classmethod
    def get_pseudo_network_names(cls) -> list:
        return [v['title'] for v in cls.PSEUDO_NETWORKS_CONTRACTS.values()]

    @classmethod
    def parse_pseudo_network(cls, currency: Currencies, network_title: str) -> tuple:
        """
            outputs contract address and network for pseudo_networks (both of type string)
        """
        contract_address = cls.CURRENCIES_PSEUDO_NETWORKS.get(currency, {}).get(network_title)
        if contract_address:
            return contract_address, cls.PSEUDO_NETWORKS_CONTRACTS.get(contract_address).get('real_network')
        return None, None

    @classmethod
    def is_pseudo_network(cls, network_title: str) -> bool:
        return any(v['title'] == network_title for v in cls.PSEUDO_NETWORKS_CONTRACTS.values())

    @classmethod
    def pseudo_network_support_coin(cls, network_title: str, currency: Currencies) -> bool:
        return network_title in cls.CURRENCIES_PSEUDO_NETWORKS.get(currency, {})

    @classmethod
    def is_pseudo_network_beta(cls, currency: Currencies, network_title: str) -> bool:
        """ Deprecated method. Use AssetNetworkInfo.is_beta instead."""
        contract_address = cls.CURRENCIES_PSEUDO_NETWORKS.get(currency).get(network_title)
        network = cls.PSEUDO_NETWORKS_CONTRACTS.get(contract_address).get('real_network')
        return CURRENCY_INFO.get(currency).get('network_list').get(network).get('contract_addresses').get(
            contract_address).get('beta', False)

    @classmethod
    def get_network_from_pseudo_network(cls, network_title: str) -> str:
        return network_title.split('-')[-1]

    @classmethod
    def get_pseudo_network_from_network(cls, network: str, contract_address: str) -> str:
        """Returns pseudo network from (network, contract_address)

        Currently, network parameter is useless. However, the struct of this must be change.
        Args:
            network: This parameter needed because there is an option which contract address in
            different networks are equals. Like 1inch.
            contract_address: Unique address in each network
        """
        if contract_address is None:
            return network
        return cls.PSEUDO_NETWORKS_CONTRACTS.get(contract_address, {}).get('title') or network


UTXO_BASED_NETWORKS = []

ETHEREUM_LIKE_NETWORKS = [CurrenciesNetworkName.ETH, CurrenciesNetworkName.BSC, CurrenciesNetworkName.ETC,
                          CurrenciesNetworkName.FTM, CurrenciesNetworkName.MATIC, CurrenciesNetworkName.AVAX,
                          CurrenciesNetworkName.ARB, CurrenciesNetworkName.SONIC, CurrenciesNetworkName.BASE]
CONTRACT_NETWORKS = [*ETHEREUM_LIKE_NETWORKS, CurrenciesNetworkName.TRX, CurrenciesNetworkName.ONE]
CONTRACT_NETWORKS_CHOICES = Choices(*[(network, network) for network in CONTRACT_NETWORKS])

MAIN_TOKEN_CURRENCIES_INFO = {
    f'{Currencies.eth}-{CurrenciesNetworkName.ETH}': {
        'decimals': 18
    },
    f'{Currencies.bnb}-{CurrenciesNetworkName.BSC}': {
        'decimals': 18
    },
    f'{Currencies.trx}-{CurrenciesNetworkName.TRX}': {
        'decimals': 6
    },
    f'{Currencies.etc}-{CurrenciesNetworkName.ETC}': {
        'decimals': 18
    },
    f'{Currencies.ftm}-{CurrenciesNetworkName.FTM}': {
        'decimals': 18
    },
    f'{Currencies.pol}-{CurrenciesNetworkName.MATIC}': {
        'decimals': 18
    },
    f'{Currencies.avax}-{CurrenciesNetworkName.AVAX}': {
        'decimals': 18
    },
    f'{Currencies.one}-{CurrenciesNetworkName.ONE}': {
        'decimals': 18
    },
    f'{Currencies.eth}-{CurrenciesNetworkName.ARB}': {
        'decimals': 18
    },
    f'{Currencies.ton}-{CurrenciesNetworkName.TON}': {
        'decimals': 9
    },
    f'{Currencies.s}-{CurrenciesNetworkName.SONIC}': {
        'decimals': 18
    },
    f'{Currencies.sol}-{CurrenciesNetworkName.SOL}': {
        'decimals': 9
    },
    f'{Currencies.eth}-{CurrenciesNetworkName.BASE}': {
        'decimals': 18
    },
}


def get_decimal_places(currency: int, network: str) -> int:
    """
        NOTE: THIS DECIMAL IS NOT LIKE DECIMALS WE USE IN CONTRACT_INFO  IT IS NOT ABOUT PRECISION.
        This function usage: Some coins on some network, accept only specific number of decimals (in sending a withdraw)
        so system automatically round the values up and then send them in network so value which we find in database
        is a little different from the value in network (as much as system rounded it up) so we have to ignore the
        difference between values if it is less than network decimal places. This function just return the decimal
        places of a specific currency on a specific network
    """
    if currency is None or network is None:
        raise ValueError('Currency and network can not be None')

    if currency == Currencies.eos and network == CurrenciesNetworkName.EOS:
        return 4
    if currency == Currencies.flow and network == CurrenciesNetworkName.FLOW:
        return 5
    if (currency == Currencies.xrp and network == CurrenciesNetworkName.XRP) or \
            (currency == Currencies.ada and network == CurrenciesNetworkName.ADA) or \
            (currency == Currencies.usdt and network == CurrenciesNetworkName.ETH) or \
            (network == CurrenciesNetworkName.TRX):
        return 6
    if currency == Currencies.xlm and network == CurrenciesNetworkName.XLM:
        return 7
    return 8
