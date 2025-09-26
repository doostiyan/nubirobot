from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from exchange.base.logging import report_exception
from exchange.blockchain.api.bsc.bsc_bitquery import BscBitqueryAPI, BtcBitqueryAPI
from exchange.blockchain.api.bsc.bsc_blockbook import BscBlockbookAPI
from exchange.blockchain.api.bsc.bsc_covalent import BSCCovalenthqAPI
from exchange.blockchain.api.bsc.bscscan import BscScanAPI
from exchange.blockchain.api.bsc.moralis import MoralisAPI
from exchange.blockchain.contracts_conf import BEP20_contract_currency, BEP20_contract_info
from exchange.blockchain.metrics import metric_incr
from exchange.blockchain.models import BaseBlockchainInspector, Transaction
from exchange.blockchain.utils import (AddressNotExist, APIError, BadGateway, GatewayTimeOut, InternalServerError,
                                       RateLimitError, ValidationError)


class Bep20BlockchainInspector(BaseBlockchainInspector):
    """ Based on: etherscan.io
        Rate limit: ? requests/sec
    """
    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS else 'mainnet'
    currency_list = None

    USE_EXPLORER_BALANCE_BSC = 'web3'  # Available options: bscscan, bitquery, blockbook, moralis, web3, covalent
    USE_EXPLORER_TRANSACTION_BSC = 'bscscan'  # Available options: bscscan, blockbook, moralis, covalent
    USE_EXPLORER_TRANSACTION_DETAILS_BSC = 'bitquery'  # Available options: bscscan, blockbook, moralis

    @classmethod
    def get_api_bsc(cls, api_selection):
        if api_selection == 'bitquery':
            return BscBitqueryAPI.get_api(network=cls.network)

    @classmethod
    def bep20_contract_currency_list(cls, network=None):
        if network is None:
            network = cls.network
        return BEP20_contract_currency[network]

    @classmethod
    def bep20_contract_info_list(cls, network=None):
        if network is None:
            network = cls.network
        if cls.currency_list is not None:
            currency_subset = {currency: BEP20_contract_info[network][currency] for currency in cls.currency_list if
                               currency in BEP20_contract_info[network]}

            return currency_subset
        return BEP20_contract_info[network]

    @classmethod
    def are_bep20_addresses_equal(cls, addr1, addr2):
        if not addr1 or not addr2:
            return False
        addr1 = addr1.lower()
        if not addr1.startswith('0x'):
            addr1 = '0x' + addr1
        addr2 = addr2.lower()
        if not addr2.startswith('0x'):
            addr2 = '0x' + addr2
        return addr1 == addr2

    @classmethod
    def get_transaction_details_bsc(cls, tx_hash, raise_error=False):
        tx_details = None
        try:
            tx_details = BscScanAPI.get_api(network=cls.network).get_tx_details(tx_hash=tx_hash)
            tx_details['transfers'] = tx_details.get('transfers').get(cls.currency) or []
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut,
                RateLimitError, Exception) as error:
            if raise_error:
                raise error
        return tx_details

    @classmethod
    def get_wallets_balance_bsc(cls, address_list):
        if cls.USE_EXPLORER_BALANCE_BSC == 'bitquery':
            return cls.get_wallets_balance_bsc_bitquery(address_list)
        if cls.USE_EXPLORER_BALANCE_BSC == 'bscscan':
            return cls.get_wallets_balance_bsc_bscscan(address_list)
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
        balances = defaultdict(list)
        api = BSCCovalenthqAPI.get_api()
        for address in address_list:
            result = api.get_balance(address)
            for currency, contract_info in cls.bep20_contract_info_list().items():
                try:
                    response = result.get(currency)
                    if not response:
                        continue
                    balances[currency].append({
                        'address': response.get('address'),
                        'balance': response.get('balance'),
                        'received': response.get('balance'),
                        'sent': Decimal('0'),
                        'rewarded': Decimal('0'),
                    })
                except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut,
                        ValidationError, RateLimitError) as error:
                    if raise_error:
                        raise error
                    metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
        return balances

    @classmethod
    def get_wallets_balance_bsc_web3(cls, address_list, raise_error=False):
        from exchange.blockchain.api.bsc.bsc_rpc import BSCRPC
        balances = defaultdict(list)
        api = BSCRPC.get_api()
        for address in address_list:
            for currency, contract_info in cls.bep20_contract_info_list().items():
                try:
                    response = api.get_token_balance(address, contract_info)
                    if not response:
                        continue
                    balances[currency].append({
                        'address': response.get('address'),
                        'balance': response.get('amount'),
                        'received': response.get('amount'),
                        'sent': Decimal('0'),
                        'rewarded': Decimal('0'),
                    })
                except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut,
                        ValidationError, RateLimitError) as error:
                    if raise_error:
                        raise error
                    metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
        return balances

    @classmethod
    def get_wallets_balance_bsc_bscscan(cls, address_list, raise_error=False):
        balances = defaultdict(list)
        api = BscScanAPI.get_api(network=cls.network)
        for address in address_list:
            for currency, contract_info in cls.bep20_contract_info_list().items():
                try:
                    res = api.get_token_balance(address, contract_info)
                    balances[currency].append({
                        'address': address,
                        'received': res.get('amount'),
                        'sent': Decimal('0'),
                        'rewarded': Decimal('0'),
                        'balance': res.get('amount'),
                    })
                except Exception as error:
                    if raise_error:
                        raise error
                    metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
        return balances

    @classmethod
    def get_wallets_balance_bsc_bitquery(cls, address_list, raise_error=False):
        balances = defaultdict(list)
        api = BtcBitqueryAPI.get_api()
        for address in address_list:
            for currency, contract_info in cls.bep20_contract_info_list().items():
                try:
                    res = api.get_balance(address, contract_info)
                    balance = res.get(contract_info.get('address')).get('amount')
                    balances[currency].append({
                        'address': address,
                        'received': balance,
                        'sent': Decimal('0'),
                        'rewarded': Decimal('0'),
                        'balance': balance,
                    })
                except Exception as error:
                    if raise_error:
                        raise error
                    metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
        return balances

    @classmethod
    def get_wallets_balance_bsc_blockbook(cls, address_list, raise_error=False):
        balances = defaultdict(list)
        api = BtcBitqueryAPI.get_api()
        for address in address_list:
            try:
                res = api.get_balance(address)
                for currency, contract_info in cls.bep20_contract_info_list().items():
                    balance = res.get(currency)
                    if not balance:
                        continue
                    balances[currency].append({
                        'address': address,
                        'received': balance.get('amount'),
                        'sent': Decimal('0'),
                        'unconfirmed': balance.get('unconfirmed_amount'),
                        'balance': balance.get('amount'),
                    })
            except Exception as error:
                metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
                if raise_error:
                    raise error
        return balances

    @classmethod
    def get_wallets_balance_bsc_moralis(cls, address_list, raise_error=False):
        balances = defaultdict(list)
        api = MoralisAPI.get_api()
        for address in address_list:
            try:
                res = api.get_token_balance(address)
                for currency, contract_info in cls.bep20_contract_info_list().items():
                    balance = res.get(currency)
                    if not balance:
                        continue
                    balances[currency].append({
                        'address': address,
                        'received': balance.get('amount'),
                        'sent': Decimal('0'),
                        'unconfirmed': balance.get('unconfirmed_amount'),
                        'balance': balance.get('amount'),
                    })
            except Exception as error:
                metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
                if raise_error:
                    raise error
                report_exception()
        return balances

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
    def get_wallet_transactions_bsc_bscscan(cls, address, raise_error=False):
        txs = defaultdict(list)
        api = BscScanAPI.get_api(network=cls.network)
        for currency, contract_info in cls.bep20_contract_info_list().items():
            try:
                transactions = api.get_token_txs(address, contract_info)
                for tx_info in transactions:
                    tx = tx_info.get(currency)
                    if tx is None:
                        continue
                    if contract_info.get('from_block', 0) >= tx.get('block'):
                        continue
                    txs[currency].append(Transaction(
                        address=address,
                        from_address=tx.get('from_address'),
                        hash=tx.get('hash'),
                        block=tx.get('block'),
                        timestamp=tx.get('date'),
                        value=tx.get('amount'),
                        confirmations=tx.get('confirmations'),
                        details=tx.get('raw')
                    ))
            except Exception as error:
                metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
                if raise_error:
                    raise error
                report_exception()
        return txs

    @classmethod
    def get_wallet_transactions_bsc_moralis(cls, address, raise_error=False):
        api = MoralisAPI.get_api()
        try:
            txs = api.get_token_txs(address, limit=40)
            transactions = defaultdict(list)
            for tx_info_list in txs:
                for currency, contract_info in cls.bep20_contract_info_list().items():
                    tx_info = tx_info_list.get(currency)
                    if not tx_info:
                        continue
                    if contract_info.get('from_block', 0) >= tx_info.get('block'):
                        continue
                    transactions[currency].append(Transaction(
                        address=address,
                        from_address=tx_info.get('from_address'),
                        hash=tx_info.get('hash'),
                        timestamp=tx_info.get('date'),
                        value=tx_info.get('amount'),
                        confirmations=int(tx_info.get('confirmations') or 0),
                        is_double_spend=False,
                        block=tx_info.get('block'),
                        details=tx_info,
                    ))
            return transactions
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut,
                RateLimitError) as error:
            if raise_error:
                raise error
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            report_exception()
            return None

    @classmethod
    def get_wallet_transactions_bsc_blockbook(cls, address, raise_error=False):
        api = BscBlockbookAPI.get_api()
        try:
            txs = api.get_txs(address, limit=40)
            transactions = defaultdict(list)
            for tx_info_list in txs:
                for currency, contract_info in cls.bep20_contract_info_list().items():
                    tx_info = tx_info_list.get(currency)
                    if not tx_info:
                        continue
                    value = tx_info.get('amount')

                    # Process transaction types
                    if tx_info.get('direction') == 'outgoing':
                        # Transaction is from this address, so it is a withdraw
                        value = -value

                    if tx_info.get('type') != 'normal':
                        continue

                    from_addr = list(tx_info.get('from_address'))[0]
                    if cls.are_bep20_addresses_equal(
                        from_addr, '0x70Fd2842096f451150c5748a30e39b64e35A3CdF'
                    ) or cls.are_bep20_addresses_equal(
                        from_addr, '0x491fe5F4724e642C90372B0B95b60c4aC8d13F1c'
                    ) or cls.are_bep20_addresses_equal(
                        from_addr, '0xB256caa23992e461E277CfA44a2FD72E2d6d2344'
                    ) or cls.are_bep20_addresses_equal(
                        from_addr, '0x06cC26db08674CbD9FF4d52444712E23cA3d046d'
                    ):
                        value = Decimal('0')

                    transactions[currency].append(Transaction(
                        address=address,
                        from_address=tx_info.get('from_address'),
                        hash=tx_info.get('hash'),
                        timestamp=tx_info.get('date'),
                        value=value,
                        confirmations=int(tx_info.get('confirmations') or 0),
                        is_double_spend=False,
                        block=tx_info.get('raw').get('blockHeight'),
                        details=tx_info,
                    ))
            return transactions
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut) as error:
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            if raise_error:
                raise error
            report_exception()
            return None

    @classmethod
    def get_wallet_transactions_bsc_covalent(cls, address, raise_error=False):
        txs = defaultdict(list)
        api = BSCCovalenthqAPI.get_api()
        for currency, contract_info in cls.bep20_contract_info_list().items():
            try:
                transactions = api.get_token_txs(address, contract_info)
                for tx_info in transactions:
                    tx = tx_info.get(currency)
                    if tx is None:
                        continue
                    if contract_info.get('from_block', 0) >= tx.get('block'):
                        continue
                    txs[currency].append(Transaction(
                        address=address,
                        from_address=tx.get('from_address'),
                        hash=tx.get('hash'),
                        block=tx.get('block'),
                        timestamp=tx.get('date'),
                        value=tx.get('amount'),
                        confirmations=tx.get('confirmations'),
                        details=tx.get('raw')
                    ))
            except Exception as error:
                metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
                if raise_error:
                    raise error
                report_exception()
        return txs
