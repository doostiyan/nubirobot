import hashlib
import sys
import traceback
from datetime import datetime
from decimal import Decimal

import base58
import requests
from django.conf import settings
from exchange.base.logging import log_event, report_exception
from exchange.base.models import Currencies
from exchange.blockchain.api.doge.doge_blockbook import DogeBlockbookAPI
from exchange.blockchain.bep20 import Bep20BlockchainInspector
from exchange.blockchain.general_blockchain_wallets import GeneralBlockchainWallet
from exchange.blockchain.metrics import metric_incr
from exchange.blockchain.models import CurrenciesNetworkName, Transaction
from exchange.blockchain.utils import AddressNotExist, APIError, BadGateway, GatewayTimeOut, InternalServerError


class DogecoinBlockchainInspector(Bep20BlockchainInspector):
    currency = Currencies.doge
    currency_list = [Currencies.doge]

    TESTNET_ENABLED = False
    USE_EXPLORER = 'blockbook'  # blockbook, sochain, dogechain_api, dogechain, blockcypher, coinexplorer
    FAKE_USER_AGENT = True
    fail_count = 0

    get_balance_method = {
        CurrenciesNetworkName.DOGE: 'get_wallets_balance_doge',
        CurrenciesNetworkName.BSC: 'get_wallets_balance_bsc',
    }

    get_transactions_method = {
        CurrenciesNetworkName.DOGE: 'get_wallet_transactions_doge',
        CurrenciesNetworkName.BSC: 'get_wallet_transactions_bsc',
    }

    get_transaction_details_method = {
        CurrenciesNetworkName.DOGE: 'get_transaction_details_doge',
        CurrenciesNetworkName.BSC: 'get_transaction_details_bsc',
    }

    @ classmethod
    def get_transaction_details_doge(cls, tx_hash, network=None):
        tx_details = None
        try:
            tx_details = DogeBlockbookAPI.get_api().get_tx_details(tx_hash=tx_hash)
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut, Exception):
            report_exception()
        return tx_details

    @classmethod
    def get_wallets_balance_doge(cls, address_list):
        if cls.USE_EXPLORER == 'blockbook':
            return cls.get_balance_from_blockbook(address_list)
        if cls.USE_EXPLORER == 'sochain':
            return cls.get_balance_from_sochain(address_list)
        if cls.USE_EXPLORER == 'dogechain':
            return cls.dogechain_get_balance_simple(address_list)
        if cls.USE_EXPLORER == 'dogechain_api':
            return cls.get_balance_from_dogechain(address_list)
        if cls.USE_EXPLORER == 'blockcypher':
            return cls.get_balance_from_blockcypher(address_list)
        return cls.get_balance_from_blockbook(address_list)  # TODO: coinexplorer does not have get balance

    @classmethod
    def get_wallet_transactions_doge(cls, address, network=None):
        if cls.USE_EXPLORER == 'coinexplorer':
            return cls.get_transactions_from_coinexplorer(address)

        return cls.get_transactions_from_blockbook(address)  # TODO: write other doge option get transactions

    @classmethod
    def get_balance_from_blockcypher(cls, address_list):
        url = 'https://api.blockcypher.com/v1/doge/main/addrs/{}/full?limit=1'
        balances = []
        for address in address_list:
            result = requests.get(url=url.format(address)).json()
            balance = result.get('balance')
            balances.append({'address': address, 'balance': balance})

        return balances

    @classmethod
    def dogechain_get_balance_simple(cls, address_list):
        balances = []
        url = "http://dogechain.info/chain/Dogecoin/q/addressbalance/{}"
        for address in address_list:
            response = requests.get(url=url.format(address))
            balances.append({'address': address, 'balance': response.json()})

        return balances

    @classmethod
    def get_balance_from_dogechain(cls, address_list, raise_error=False):
        balances = []
        url = "https://dogechain.info/api/v1/address/balance/{}"
        for address in address_list:
            try:
                result_info = requests.get(url=url.format(address)).json()
                if result_info.get('success') == 1:
                    balance = result_info.get('balance')
                    balances.append({
                        'address': address,
                        'received': balance,
                        'sent': Decimal('0'),
                        'rewarded': Decimal('0'),
                        'balance': balance,
                    })
                else:
                    balances.append({'address': address, 'error': result_info.get('error')})
            except Exception as error:
                if raise_error:
                    raise error
                metric_incr('api_errors_count', labels=['doge', 'doge_chain'])
                report_exception()
        return balances

    @classmethod
    def get_balance_from_blockbook(cls, address_list, raise_error=False):
        balances = []
        api = DogeBlockbookAPI.get_api()
        for address in address_list:
            try:
                response = api.get_balance(address)
                balance = response.get(Currencies.doge, {}).get('amount', 0)
            except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut) as error:
                if raise_error:
                    raise error
                metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
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
    def get_balance_from_sochain(cls, address_list, raise_error=False):
        balances = []
        url = "https://sochain.com/api/v2/get_address_balance/doge/{}"
        for address in address_list:
            try:
                response = cls.get_session().get(url=url.format(address))
                api_response = response.json()
            except Exception as error:
                metric_incr('api_errors_count', labels=['doge', 'sochain'])
                if raise_error:
                    raise error
                return error

            status = api_response.get('status')
            data = api_response.get('data')
            if status == 'success':
                balances.append(
                    {
                        'address': data.get('address'),
                        'network': data.get('network'),
                        'confirmed_balance': data.get('confirmed_balance'),
                        'unconfirmed_balance': data.get('unconfirmed_balance'),
                    }
                )
            if status == 'fail':
                balances.append(
                    {
                        'address': address,
                        'error': data.get('address')
                    }
                )

        return balances

    @classmethod
    def parse_actions_doge(cls, records, address):
        transactions = []
        for record in records:
            transactions.append(
                Transaction(
                    from_address=record.get('vin')[0].get('addresses'),
                    address=record.get('vout')[0].get('addresses')[0],
                    hash=record.get('txid'),
                    block=record.get('blockHeight'),
                    confirmations=record.get('confirmations'),
                    value=Decimal(record.get('value')) / Decimal('1e8'),
                    timestamp=datetime.fromtimestamp(record.get('blockTime')),
                    is_double_spend=False,
                    details=record
                )
            )
        return transactions

    @classmethod
    def get_explorer_url(cls):
        pass

    @classmethod
    def get_transactions_from_blockbook(cls, address, raise_error=False):
        api = DogeBlockbookAPI.get_api()
        try:
            txs = api.get_txs(address)
            transactions = []
            for tx_info_list in txs:
                tx_info = tx_info_list.get(Currencies.doge)
                value = tx_info.get('amount')

                # Process transaction types
                if value < Decimal('1.00000000'):
                    value = Decimal('0')

                if tx_info.get('direction') == 'outgoing':
                    # Transaction is from this address, so it is a withdraw
                    value = -value

                if tx_info.get('type') != 'normal':
                    continue

                transactions.append(Transaction(
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
            if raise_error:
                raise error
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            report_exception()
            return []

    @classmethod
    def get_transactions_from_coinexplorer(cls, address):
        url = "https://www.coinexplorer.net/api/v1/DOGE/address/transactions?address={}"
        result = cls.get_session().get(url=url.format(address), timeout=60)
        response = (str(result).split('['))[1].split(']')[0]
        if response != '200':
            return 'Coinexplorer Gateway is not available!'
        transactions_info = result.json()
        if transactions_info.get('success') == 'false':
            return transactions_info.get('error')
        transactions = []
        for tx_info in transactions_info.get('result'):
            transactions.append(Transaction(
                address=address,
                hash=tx_info.get('txid'),
                timestamp=tx_info.get('time'),
                value=tx_info.get('change'),
                confirmations=None,
                is_double_spend=False,
                details=tx_info,
            ))

        return transactions

    @classmethod
    def get_latest_block_addresses(cls, include_inputs=False, include_info=True):
        return cls.get_latest_block_addresses_blockbook(include_inputs=include_inputs, include_info=include_info)

    @classmethod
    def get_latest_block_addresses_blockbook(cls, include_inputs=False, include_info=True):
        """
            Retrieve block from blockbook by trezor.io
            :return: Set of addresses output transactions with pay to public key hash
            in last block processed until the last block mined
            API Document: https://github.com/trezor/blockbook/blob/master/docs/api.md
        """

        api = DogeBlockbookAPI.get_api()
        if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
            return set(), None, 0
        try:
            return api.get_latest_block(include_inputs=include_inputs,
                                                               include_info=include_info)
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut) as error:
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            traceback.print_exception(*sys.exc_info())
            return set(), None, 0


class DogeBlockchainWallet(GeneralBlockchainWallet):
    currency = Currencies.doge
    coin_type = 3

    def pub_key_to_address(self, pub_key):
        hash160_bytes = hashlib.new('ripemd160', hashlib.sha256(pub_key).digest()).digest()
        network_hash160_bytes = b'\x1e' + hash160_bytes
        return base58.b58encode_check(network_hash160_bytes).decode('utf-8')
