from decimal import Decimal

import requests
from django.conf import settings
from exchange.base.connections import TrxClient
from exchange.base.logging import log_event, report_event, report_exception
from exchange.base.models import Currencies
from exchange.blockchain.api.trx.tron_full_node import TronFullNodeAPI
from exchange.blockchain.api.trx.tron_solidity_node import TronSolidityNodeAPI
from exchange.blockchain.api.trx.trongrid import TrongridAPI
from exchange.blockchain.api.trx.tronscan import TronscanAPI
from exchange.blockchain.bep20 import Bep20BlockchainInspector
from exchange.blockchain.contracts_conf import TRC20_contract_info
from exchange.blockchain.erc20 import Erc20BlockchainInspector
from exchange.blockchain.metrics import metric_incr
from exchange.blockchain.models import Transaction
from exchange.blockchain.one_erc20 import OneERC20BlockchainInspector
from exchange.blockchain.opera_ftm import OperaFTMBlockchainInspector
from exchange.blockchain.polygon_erc20 import PolygonERC20BlockchainInspector
from exchange.blockchain.utils import AddressNotExist, APIError, BadGateway, GatewayTimeOut, InternalServerError


class TetherBlockchainInspector(Erc20BlockchainInspector, Bep20BlockchainInspector, OperaFTMBlockchainInspector,
                                PolygonERC20BlockchainInspector,
                                OneERC20BlockchainInspector):
    """ Based on: etherscan.io
        Rate limit: ? requests/sec
    """
    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS else 'mainnet'
    currency = Currencies.usdt
    currency_list = [Currencies.usdt]
    ignore_network_list = ['OMNI']

    # Key bellow must be same as CURRENCY_INFO in coins_info.py
    get_balance_method = {
        'TRX': 'get_wallets_balance_trx',
        'ETH': 'get_wallets_balance_eth',
        'OMNI': 'get_wallets_balance_omni',
        'BSC': 'get_wallets_balance_bsc',
        'ZTRX': 'get_wallets_balance_ztrx',
        'FTM': 'get_wallets_balance_ftm',
        'MATIC': 'get_wallets_balance_polygon',
        'ONE': 'get_wallets_balance_one',
        'AVAX': 'get_wallets_balance_avax',
    }
    get_transactions_method = {
        'TRX': 'get_wallet_transactions_trx',
        'ETH': 'get_wallet_transactions_eth',
        'OMNI': 'get_wallet_transactions_omni',
        'BSC': 'get_wallet_transactions_bsc',
        'FTM': 'get_wallet_transactions_ftm',
        'MATIC': 'get_wallet_transactions_polygon',
        'AVAX': 'get_wallet_transactions_avax',
        'ONE': 'get_wallet_transactions_one',
    }
    get_transaction_details_method = {
        'ETH': 'get_transaction_details_eth',
        'BSC': 'get_transaction_details_bsc',
    }

    @classmethod
    def get_wallets_balance_trx(cls, address_list, raise_error=False):
        balances = []
        api = TronFullNodeAPI.get_api()
        for address in address_list:
            try:
                response = api.get_token_balance(address, {
                    Currencies.usdt: TRC20_contract_info.get('mainnet').get(Currencies.usdt)})
                balance = response.get(Currencies.usdt, {}).get('amount', 0)
            except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut) as error:
                metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
                if raise_error:
                    raise error
                report_exception()
                continue
            balances.append({
                'address': address,
                'received': balance,
                'sent': Decimal('0'),
                'rewarded': Decimal('0'),
                'balance': balance,
            })
        return balances

    @classmethod
    def get_wallet_transactions_trx(cls, address):
        return cls.get_wallet_transactions_trx_trongrid(address)

    @classmethod
    def get_wallet_transactions_trx_solidity(cls, address, raise_error=False):
        api = TronSolidityNodeAPI.get_api()
        try:
            txs = api.get_txs(tx_type='trc20', address=address)
            transactions = []
            for tx_info in txs:
                value = tx_info.get('amount')

                # Process transaction types
                if tx_info.get('direction') == 'outgoing':
                    # Transaction is from this address, so it is a withdraw
                    value = -value

                if tx_info.get('from_address') == 'TM9RwJndZHmDVLSZcY6J76ci22AzPp2krj':
                    value = Decimal(0)

                transactions.append(Transaction(
                    address=address,
                    from_address=[tx_info.get('from_address')],
                    hash=tx_info.get('hash'),
                    timestamp=tx_info.get('date'),
                    value=value,
                    confirmations=int(tx_info.get('confirmations') or 1),
                    is_double_spend=False,  # TODO: check for double spends for TRX
                    details=tx_info,
                ))
            return transactions
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut) as error:
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            if raise_error:
                raise error
            report_exception()
            return []

    @classmethod
    def get_wallet_transactions_trx_trongrid(cls, address, raise_error=False):
        api = TrongridAPI.get_api()
        try:
            txs = api.get_token_txs(contract_address='TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t',
                                                      address=address)
            transactions = []
            for tx_info in txs:
                value = tx_info.get('amount')

                # Process transaction types
                if tx_info.get('direction') == 'outgoing' and value > Decimal('0'):
                    # Transaction is from this address, so it is a withdraw
                    value = -value

                if tx_info.get('from_address') == 'TM9RwJndZHmDVLSZcY6J76ci22AzPp2krj':
                    value = Decimal(0)

                transactions.append(Transaction(
                    address=address,
                    from_address=[tx_info.get('from_address')],
                    hash=tx_info.get('hash'),
                    timestamp=tx_info.get('date'),
                    value=value,
                    confirmations=int(tx_info.get('confirmations') or 1),
                    is_double_spend=False,  # TODO: check for double spends for TRX
                    details=tx_info,
                ))
            return transactions
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut,
                requests.exceptions.Timeout, requests.exceptions.Timeout) as error:
            if raise_error:
                raise error
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            report_exception()
            return []

    @classmethod
    def get_wallet_transactions_trx_tronscan(cls, address):
        try:
            txs = TronscanAPI.get_api().get_token_txs(address=address, currency=cls.currency)
            transactions = []
            for tx_info in txs:
                transactions.append(Transaction(
                    address=address,
                    from_address=[tx_info.get('from_address')],
                    hash=tx_info.get('hash'),
                    block=tx_info.get('block'),
                    timestamp=tx_info.get('date'),
                    value=tx_info.get('amount'),
                    confirmations=int(tx_info.get('confirmations') or 1),
                    is_double_spend=False,
                    details=tx_info,
                ))
            return transactions
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut,
                requests.exceptions.Timeout, requests.exceptions.Timeout) as error:
            report_exception()
            return []

    @classmethod
    def get_wallets_balance_ztrx(cls, address_list):
        return cls.get_wallets_balance_ztrx_hotwallet(address_list)


    @classmethod
    def get_wallets_balance_ztrx_hotwallet(cls, address_list, raise_error=False):
        trx_hotwallet = TrxClient.get_client()
        balances = []
        for address in address_list:
            try:
                params = [{
                    'z_address': address,
                }]

                response = trx_hotwallet.request(
                    method="get_rcm_values",
                    params=params,
                    rpc_id="curltext",
                )
                if response.get('status') != 'success':
                    m = f"{response.get('code')}: {response.get('message')}"
                    print(m)
                    # report_event(m)

                balance = Decimal('0.0')
                for value in response.get('rcm_values'):
                    balance += Decimal(str(value))

                balances.append({
                    'address': address,
                    'received': balance,
                    'sent': Decimal('0'),
                    'rewarded': Decimal('0'),
                    'balance': balance,
                })

            except Exception as e:
                if raise_error:
                    raise e
                msg = '[Exception] {}'.format(str(e))
                print(msg)
                report_exception()

        return balances
