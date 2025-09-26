import time
from datetime import datetime
from decimal import Decimal

import requests
from django.conf import settings
from exchange.base.connections import get_bnb_external_client
from exchange.base.logging import report_event, report_exception
from exchange.base.models import Currencies
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.bnb.bnb_node import BinanceNodeAPI
from exchange.blockchain.api.bsc.bsc_bitquery import BscBitqueryAPI
from exchange.blockchain.api.bsc.bsc_blockbook import BscBlockbookAPI
from exchange.blockchain.api.bsc.bsc_covalent import BSCCovalenthqAPI
from exchange.blockchain.api.bsc.bscscan import BscScanAPI
from exchange.blockchain.api.bsc.moralis import MoralisAPI
from exchange.blockchain.metrics import metric_incr
from exchange.blockchain.models import BaseBlockchainInspector, Transaction


class BinanceCoinBlockchainInspector(BaseBlockchainInspector):
    """ Based on: https://explorer.binance.org/ """
    USE_PROXY = True
    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS else 'mainnet'
    currency = Currencies.bnb

    USE_EXPLORER_BALANCE_BNB = 'binance'  # Available options: binance, node
    USE_EXPLORER_BALANCE_BSC = 'web3'  # Available options: bscscan, bitquery, blockbook, moralis, web3, covalent
    USE_EXPLORER_TRANSACTION_BSC = 'bscscan'  # Available options: bscscan, blockbook, moralis, covalent

    get_balance_method = {
        'BNB': 'get_wallets_balance_bnb',
        'BSC': 'get_wallets_balance_bsc',
    }

    get_transactions_method = {
        'BNB': 'get_wallet_transactions_bnb',
        'BSC': 'get_wallet_transactions_bsc',
    }

    @classmethod
    def get_wallets_balance_bnb(cls, address_list):
        if cls.USE_EXPLORER_BALANCE_BNB == 'binance':
            return cls.get_wallets_balance_binance(address_list)
        if cls.USE_EXPLORER_BALANCE_BNB == 'node':
            return cls.get_wallets_balance_node(address_list)

    @classmethod
    def get_wallets_balance_node(cls, address_list, raise_error=False):
        balances = []
        api = BinanceNodeAPI.get_api(cls.network)
        for address in address_list:
            try:
                response = api.get_balance(address)
                balance = response.get(Currencies.bnb).get('amount')
                unconfirmed_balance = response.get(Currencies.bnb).get('unconfirmed_amount')
            except Exception as error:
                metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
                if raise_error:
                    raise error
                continue
            balances.append({
                'address': address,
                'received': balance,
                'sent': Decimal('0'),
                'balance': balance,
                'unconfirmed': unconfirmed_balance,
            })
        return balances

    @classmethod
    def get_wallets_balance_binance(cls, address_list, raise_error=False):
        balances = []
        for address in address_list:
            try:
                url = f'https://dex-asiapacific.binance.org/api/v1/account/{address}'
                account_balances = cls.get_session().get(url, timeout=30).json()
            except Exception as e:
                if raise_error:
                    raise e
                msg = f'Failed to get BNB wallet balance from BNB API server: {str(e)}'
                continue
            if not account_balances:
                msg = f'Failed to get BNB wallet balance from BNB api-server: {str(account_balances)}'
                print(msg)
                continue
            for temp_balance in account_balances.get('balances'):
                if temp_balance.get('symbol') == 'BNB':
                    free_balance = temp_balance.get('free')
                    free_balance = Decimal(free_balance)
                    balances.append({
                        'address': address,
                        'received': free_balance,
                        'sent': Decimal('0'),
                        'balance': free_balance,
                        'unconfirmed': Decimal('0'),
                    })
        return balances

    @classmethod
    def get_wallets_balance_bsc(cls, address_list):
        if cls.USE_EXPLORER_BALANCE_BSC == 'bscscan':
            return cls.get_wallets_balance_bsc_bscscan(address_list)
        if cls.USE_EXPLORER_BALANCE_BSC == 'bitquery':
            return cls.get_wallets_balance_bsc_bitquery(address_list)
        if cls.USE_EXPLORER_BALANCE_BSC == 'blockbook':
            return cls.get_wallets_balance_bsc_blockbook(address_list)
        if cls.USE_EXPLORER_BALANCE_BSC == 'moralis':
            return cls.get_wallets_balance_bsc_moralis(address_list)
        if cls.USE_EXPLORER_BALANCE_BSC == 'web3':
            return cls.get_wallets_balance_bsc_web3(address_list)
        if cls.USE_EXPLORER_BALANCE_BSC == 'covalent':
            return cls.get_wallets_balance_bsc_covalent(address_list)

    @classmethod
    def get_wallets_balance_bsc_covalent(cls, address_list, raise_error=False):
        balances = []
        api = BSCCovalenthqAPI.get_api()
        try:
            for address in address_list:
                res = api.get_balance(address)
                response = res.get(cls.currency)
                if not response:
                    continue
                balances.append({
                    'address': response.get('address'),
                    'balance': response.get('amount'),
                    'received': response.get('amount'),
                    'sent': Decimal('0'),
                    'rewarded': Decimal('0'),
                })
        except Exception as error:
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            if raise_error:
                raise error
        return balances

    @classmethod
    def get_wallets_balance_bsc_web3(cls, address_list, raise_error=False):
        from exchange.blockchain.api.bsc.bsc_rpc import BSCRPC
        balances = []
        api = BSCRPC.get_api()
        for address in address_list:
            try:
                response = api.get_balance(address)
                if not response:
                    continue
                balances.append({
                    'address': response.get('address'),
                    'balance': response.get('balance'),
                    'received': response.get('balance'),
                    'sent': Decimal('0'),
                    'rewarded': Decimal('0'),
                })
            except Exception as error:
                metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
                if raise_error:
                    raise error
        return balances

    @classmethod
    def get_wallets_balance_bsc_bscscan(cls, address_list, raise_error=False):
        balances = []
        api = BscScanAPI.get_api(network=cls.network)
        try:
            res = api.get_balances(address_list)
            for response in res:
                balances.append({
                    'address': response.get('address'),
                    'received': response.get('amount'),
                    'sent': Decimal('0'),
                    'rewarded': Decimal('0'),
                    'balance': response.get('amount'),
                })
        except Exception as e:
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            if raise_error:
                raise e
        return balances

    @classmethod
    def get_wallets_balance_bsc_bitquery(cls, address_list, raise_error=False):
        balances = []
        api = BscBitqueryAPI.get_api()
        for address in address_list:
            try:
                res = api.get_balance(address, 'BNB')
                balances.append({
                    'address': address,
                    'received': res.get('amount'),
                    'sent': Decimal('0'),
                    'rewarded': Decimal('0'),
                    'balance': res.get('amount'),
                })
            except Exception as e:
                metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
                if raise_error:
                    raise e
                msg = f'Failed to get BNB wallet balance from API: {str(e)}'
                print(msg)
                continue
        return balances

    @classmethod
    def get_wallets_balance_bsc_blockbook(cls, address_list, raise_error=False):
        balances = []
        api = BscBlockbookAPI.get_api()
        for address in address_list:
            try:
                res = api.get_balance(address)
                balance = res.get(Currencies.bnb)
                balances.append({
                    'address': address,
                    'received': balance.get('amount'),
                    'sent': Decimal('0'),
                    'unconfirmed': balance.get('unconfirmed_amount'),
                    'balance': balance.get('amount'),
                })
            except Exception as e:
                metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
                if raise_error:
                    raise e
                msg = f'Failed to get BNB wallet balance from API: {str(e)}'
                print(msg)
                continue
        return balances

    @classmethod
    def get_wallets_balance_bsc_moralis(cls, address_list, raise_error=False):
        balances = []
        api = MoralisAPI.get_api()
        for address in address_list:
            try:
                res = api.get_balance(address)
                balance = res.get(Currencies.bnb)
                balances.append({
                    'address': address,
                    'received': balance.get('amount'),
                    'sent': Decimal('0'),
                    'unconfirmed': balance.get('unconfirmed_amount'),
                    'balance': balance.get('amount'),
                })
            except Exception as e:
                metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
                if raise_error:
                    raise e
                msg = f'Failed to get BNB wallet balance from API: {str(e)}'
                print(msg)
                continue
        return balances

    @classmethod
    def parse_actions_bnb(cls, records, address):
        transactions = []
        for record in records:
            if record.get('isError'):
                if record.get('isError') != '0':
                    continue
            if record.get('value') == '0':
                continue
            transactions.append(
                Transaction(
                    address=record.get('to'),
                    from_address=record.get('from'),
                    timestamp=datetime.fromtimestamp(int(record.get('timeStamp'))),
                    hash=record.get('hash'),
                    block=int(record.get('blockNumber')),
                    confirmations=int(record.get('confirmations')),
                    value=Decimal(record.get('value')) / Decimal('1e18'),
                    is_double_spend=False,
                )
            )
        return transactions

    @classmethod
    def get_wallet_transactions_bnb(cls, address, start_time=None, end_time=None, raise_error=False):
        from binance_chain.constants import TransactionType

        time.sleep(0.2)
        try:
            # client = get_bnb_external_client()
            # transactions_info = client.get_transactions(
            #     address=address,
            #     tx_type=TransactionType.TRANSFER,
            #     limit=200,
            #     start_time=start_time,
            #     end_time=end_time,
            # )['tx']
            r = requests.get(
                f'https://dex-atlantic.binance.org/api/v1/transactions?address={address}&txType=TRANSFER&offset=0&limit=600',
                proxies=settings.DEFAULT_PROXY)
            transactions_info = r.json().get('tx')
        except Exception as e:
            metric_incr('api_errors_count', labels=['bnb', 'binance_chain'])
            if raise_error:
                raise e
            print('Failed to get BNB wallet transactions from API: {}'.format(str(e)))
            return None
        if not transactions_info:
            return None

        transactions = []
        for tx_info in transactions_info:
            if tx_info.get('txAsset') != 'BNB':
                continue
            if tx_info.get('toAddr') != address and tx_info.get('fromAddr') != address:
                continue
            raw_value = Decimal(tx_info.get('value'))
            if raw_value <= Decimal('0'):
                continue
            if tx_info.get('fromAddr') == address:
                value = -raw_value
            elif tx_info.get('toAddr') == address:
                value = raw_value
            else:
                value = Decimal('0')
            transactions.append(Transaction(
                address=address,
                from_address=[tx_info.get('fromAddr')],
                hash=tx_info.get('txHash'),
                timestamp=parse_iso_date(tx_info.get('timeStamp')),
                value=value,
                confirmations=int(tx_info.get('confirmBlocks')),
                is_double_spend=False,
                details=tx_info,
                tag=tx_info.get('memo'),
            ))
        return transactions

    @classmethod
    def get_wallet_transactions_bsc(cls, address):
        if cls.USE_EXPLORER_TRANSACTION_BSC == 'bscscan':
            return cls.get_wallet_transactions_bsc_bscscan(address)
        if cls.USE_EXPLORER_TRANSACTION_BSC == 'blockbook':
            return cls.get_wallet_transactions_bsc_blockbook(address)
        if cls.USE_EXPLORER_TRANSACTION_BSC == 'moralis':
            return cls.get_wallet_transactions_bsc_moralis(address)
        if cls.USE_EXPLORER_TRANSACTION_BSC == 'covalent':
            return cls.get_wallet_transactions_bsc_covalent(address)

    @classmethod
    def get_wallet_transactions_bsc_covalent(cls, address, raise_error=False):
        transactions = []
        api = BSCCovalenthqAPI.get_api()
        try:
            txs = api.get_txs(address)
            for tx in txs:
                tx = tx.get(Currencies.bnb)
                transactions.append(Transaction(
                    address=address,
                    from_address=tx.get('from_address'),
                    hash=tx.get('hash'),
                    block=tx.get('block'),
                    timestamp=tx.get('date'),
                    value=tx.get('amount'),
                    confirmations=tx.get('confirmations'),
                    is_double_spend=False,
                    details=tx.get('raw'),
                ))
        except Exception as error:
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            if raise_error:
                raise error
        return transactions

    @classmethod
    def get_wallet_transactions_bsc_bscscan(cls, address, raise_error=False):
        api = BscScanAPI.get_api(network=cls.network)
        try:
            transactions = api.get_txs(address)
            txs = []
            for tx_info in transactions:
                tx = tx_info.get(Currencies.bnb)
                if tx is None:
                    continue
                txs.append(Transaction(
                    address=address,
                    from_address=tx.get('from_address'),
                    hash=tx.get('hash'),
                    block=tx.get('block'),
                    timestamp=tx.get('date'),
                    value=tx.get('amount'),
                    confirmations=tx.get('confirmations'),
                    details=tx.get('raw')
                ))
            return txs
        except Exception as e:
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            if raise_error:
                raise e
            msg = f'Failed to get BNB wallet transactions from API: {str(e)}'
            print(msg)
            return None

    @classmethod
    def get_wallet_transactions_bsc_moralis(cls, address, raise_error=False):
        api = MoralisAPI.get_api(network=cls.network)
        try:
            transactions = api.get_txs(address)
            txs = []
            for tx_info in transactions:
                tx = tx_info.get(Currencies.bnb)
                if tx is None:
                    continue
                txs.append(Transaction(
                    address=address,
                    from_address=tx.get('from_address'),
                    hash=tx.get('hash'),
                    block=tx.get('block'),
                    timestamp=tx.get('date'),
                    value=tx.get('amount'),
                    confirmations=tx.get('confirmations', 0),
                    details=tx.get('raw')
                ))
            return txs
        except Exception as e:
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            if raise_error:
                raise e
            msg = f'Failed to get BNB wallet transactions from API: {str(e)}'
            print(msg)
            return None

    @classmethod
    def get_wallet_transactions_bsc_blockbook(cls, address, raise_error=False):
        api = BscBlockbookAPI.get_api()
        try:
            transactions = api.get_txs(address)
            txs = []
            if transactions:
                for transaction in transactions:
                    tx = transaction.get(Currencies.bnb)
                    if tx is None:
                        continue
                    value = tx.get('amount')
                    if tx.get('direction') == 'outgoing':
                        # Transaction is from this address, so it is a withdraw
                        value = -value
                    if tx.get('type') != 'normal':
                        continue
                    txs.append(Transaction(
                        address=address,
                        from_address=tx.get('from_address'),
                        hash=tx.get('hash'),
                        timestamp=tx.get('date'),
                        value=value,
                        confirmations=tx.get('confirmations'),
                        is_double_spend=False,
                        details=tx.get('raw')
                    ))
            return txs
        except Exception as e:
            if raise_error:
                raise e
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            return None

    @classmethod
    def get_latest_block_addresses_bsc_blockbook(cls):
        api = BscBlockbookAPI.get_api()
        if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
            return set(), None
        try:
            return api.get_latest_block(include_info=True)
        except Exception as e:
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])

    @classmethod
    def get_latest_block_addresses_bsc_bitquery(cls):
        api = BscBitqueryAPI.get_api()
        if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
            return set(), None
        try:
            return api.get_latest_block()
        except Exception as e:
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])

    @classmethod
    def get_wallet_withdraws(cls, address):
        """
        This function will return just withdraws of an address
        Note 1: This function is just for bnb in its own network BNB nothing else
        Note 2: If U could not install this messed up package (binance_chain) you'll need to directly request to
        https://dex.binance.org/api/v1/transactions?address={address} to get transactions of an address(Testing purposes)
        """
        from binance_chain.constants import TransactionType

        time.sleep(0.2)
        try:
            # client = get_bnb_external_client()
            # transactions_info = client.get_transactions(
            #     address=address,
            #     tx_type=TransactionType.TRANSFER,
            #     limit=200,
            # )['tx']
            r = requests.get(
                f'https://dex-european.binance.org/api/v1/transactions?address={address}&txType=TRANSFER&offset=0&limit=200',
                proxies=settings.DEFAULT_PROXY)
            transactions_info = r.json().get('tx')
        except Exception as e:
            print('Failed to get BNB wallet withdraws from API: {}'.format(str(e)))
            return None
        if not transactions_info:
            return None

        transactions = []
        for tx_info in transactions_info:
            if tx_info.get('txAsset') != 'BNB':
                continue
            if tx_info.get('fromAddr') != address:  # just withdraws
                continue
            raw_value = Decimal(tx_info.get('value'))
            if raw_value <= Decimal('0'):
                continue
            value = -raw_value  # withdraws have negative value
            transactions.append(Transaction(
                address=address,
                from_address=[tx_info.get('fromAddr')],
                hash=tx_info.get('txHash'),
                timestamp=parse_iso_date(tx_info.get('timeStamp')),
                value=value,
                confirmations=int(tx_info.get('confirmBlocks')),
                is_double_spend=False,
                details=tx_info,
                tag=tx_info.get('memo'),
            ))
        return transactions
