import json
import sys
import traceback
from decimal import Decimal, localcontext
from typing import List, Union

import base58
from django.conf import settings
from django.core.cache import cache
from eth_keys.datatypes import PublicKey
from exchange.base.connections import TrxClient, get_trx_hotwallet
from exchange.base.logging import log_event, report_event, report_exception
from exchange.base.models import Currencies
from exchange.base.parsers import parse_utc_timestamp, parse_utc_timestamp_ms
from exchange.blockchain.api.trx.tron_full_node import TronFullNodeAPI
from exchange.blockchain.bep20 import Bep20BlockchainInspector
from exchange.blockchain.general_blockchain_wallets import GeneralBlockchainWallet
from exchange.blockchain.metrics import metric_incr
from exchange.blockchain.models import CurrenciesNetworkName, Transaction
from exchange.blockchain.utils import AddressNotExist, APIError, BadGateway, GatewayTimeOut, InternalServerError

MIN_SUN = 0
MAX_SUN = 2 ** 256 - 1
UNITS = {
    'sun': Decimal('1000000')
}


def from_sun(number: int) -> Union[int, Decimal]:
    """Helper function that will convert a value in SUN to TRX.

    Args:
        number (int): Value in SUN to convert to TRX

    """
    if number == 0:
        # TODO: why return int? Should be Decimal
        return 0

    if number < MIN_SUN or number > MAX_SUN:
        raise ValueError("value must be between 1 and 2**256 - 1")

    unit_value = UNITS['sun']

    # TODO: Why not using quantize? Specific context precision seems redundant
    with localcontext() as ctx:
        ctx.prec = 999
        d_number = Decimal(value=number, context=ctx)
        result_value = d_number / unit_value

    return result_value


class TRXBlockchainInspector(Bep20BlockchainInspector):
    """ Based on: https://apilist.tronscan.org/api for main
        and https://api.shasta.tronscan.org/api for shasta (testnet)
    """
    currency = Currencies.trx
    currency_list = [Currencies.trx]

    TESTNET_ENABLED = False
    USE_FULLNODE = True
    USE_SOLIDITY = False
    USE_TRONGRID = True
    FAKE_USER_AGENT = True
    fail_count = 0

    get_balance_method = {
        CurrenciesNetworkName.TRX: 'get_wallets_balance_trx',
        CurrenciesNetworkName.BSC: 'get_wallets_balance_bsc',
    }

    get_transactions_method = {
        CurrenciesNetworkName.TRX: 'get_wallet_transactions_trx',
        CurrenciesNetworkName.BSC: 'get_wallet_transactions_bsc',
    }

    get_transaction_details_method = {
        CurrenciesNetworkName.TRX: 'get_transaction_details_trx',
        CurrenciesNetworkName.BSC: 'get_transaction_details_bsc',
    }

    @classmethod
    def get_balance(cls, address):
        # TODO: Didn't use solidity for now
        if cls.USE_FULLNODE:
            return cls.get_wallet_balance_fullnode(address)
        elif cls.USE_TRONGRID:
            return cls.get_wallet_balance_trongrid_api(address)
        else:
            return cls.get_wallet_balance_tronscan(address)

    @classmethod
    def get_transaction(cls, address):
        # TODO: Didn't use solidity for now
        if cls.USE_SOLIDITY:
            return cls.get_wallet_transactions_solidity(address)
        elif cls.USE_TRONGRID:
            return cls.get_wallet_transactions_trongrid(address)
        else:
            return cls.get_wallet_transactions_tronscan(address)

    @classmethod
    def get_explorer_url(cls):
        if cls.USE_TRONGRID:
            if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
                explorer_url = 'https://api.shasta.trongrid.io/'
            else:
                explorer_url = 'https://api.trongrid.io/'
        else:
            if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
                explorer_url = 'https://api.shasta.tronscan.org/api/'
            else:
                explorer_url = 'https://apilist.tronscan.org/api/'
        return explorer_url

    @classmethod
    def get_wallets_balance_trx(cls, address_list: List[str]):
        # Try twice in getting error
        for i in range(0, 1):
            balances = []
            for address in address_list:
                balance = cls.get_balance(address)
                if balance is None:
                    continue
                balances.append(balance)
            else:
                return balances
        return None

    @classmethod
    def get_wallet_transactions_trx(cls, address, network=None):
        # Try twice in getting error
        for i in range(0, 1):
            transactions = cls.get_transaction(address)
            if transactions is None:
                continue
            return transactions
        return None

    @classmethod
    def get_wallet_balance_tronscan(cls, address: str, raise_error=False):
        """ Get TRX account balance
        """
        explorer_url = cls.get_explorer_url() + 'account?address={}'
        try:
            api_response = cls.get_session().get(explorer_url.format(address), timeout=25)
            info = api_response.json()
        except Exception as e:
            if raise_error:
                raise e

            return None
        if info.get('error'):

            return None
        balance = info.get('balance')
        if balance is None:
            return None
        balance = balance / Decimal(1e6)
        return {
            'address': address,
            'received': balance,
            'sent': Decimal('0'),
            'balance': Decimal(balance),
            'unconfirmed': Decimal('0'),
        }

    @classmethod
    def parse_actions_tronscan(cls, records, address):
        transactions = []
        for record in records:
            if record.get('tokenName') != '_':  # token: '_' shows only TRX transfers;
                continue

            raw_value = record.get('amount')
            if not raw_value:
                continue
            raw_value = Decimal(raw_value) / Decimal(1e6)
            if raw_value < Decimal('0.001'):
                continue
            if record.get('transferFromAddress') == address:  # is send.
                value = -1 * raw_value
            elif record.get('transferToAddress') == address:  # is receive.
                value = raw_value
            else:
                value = Decimal('0')

            if record.get('transferFromAddress') in ['TM9RwJndZHmDVLSZcY6J76ci22AzPp2krj', 'TVCAuYMw5afP96y5Wep866AXVWZJRH8fdo']:
                value = Decimal('0.000000')

            confirmations = 20 if record.get('confirmed') else 0
            timestamp = int(record.get('timestamp')) // 1000
            transactions.append(Transaction(
                address=address,
                from_address=[record.get('transferFromAddress')],
                hash=record.get('transactionHash'),
                timestamp=parse_utc_timestamp(timestamp),
                value=value,
                confirmations=confirmations,
                is_double_spend=False,
                block=record.get('block'),
                details=record,
            ))
        return transactions

    @classmethod
    def get_wallet_transactions_tronscan(cls, address, raise_error=False):
        explorer_url = cls.get_explorer_url() + 'transfer?sort=-timestamp&count=true&limit={}&start={}&token={}&address={}'
        try:
            api_response = cls.get_session().get(explorer_url.format(5, 0, '_', address), timeout=25)
            res = api_response.json()
        except Exception as e:
            if raise_error:
                raise e
            print('[Inspector:Trx][Transaction:TronScan] Failed to get TRX wallet transactions from API: {}'.format(
                str(e)))
            return None
        records = res.get('data')
        if not records:
            return []
        transactions = cls.parse_actions_tronscan(records, address) or []
        return transactions

    @classmethod
    def get_wallet_balance_fullnode(cls, address: str, raise_error=False):
        """ Get TRX account balance from TronGrid Full Node
        """
        api = TronFullNodeAPI.get_api()
        try:
            response = api.get_balance(address)
            balance = response.get(Currencies.trx, {}).get('amount', Decimal('0.0'))
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut) as error:
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            if raise_error:
                raise error
            balance = Decimal('0.0')
        return {
            'address': address,
            'received': balance,
            'sent': Decimal('0'),
            'balance': balance,
            'unconfirmed': Decimal('0'),
        }

    @classmethod
    def get_wallet_balance_trongrid_solidity(cls, address: str, raise_error=False):
        """ Get TRX account balance from TronGrid Solidity Node
        """
        explorer_url = cls.get_explorer_url() + 'walletsolidity/getaccount'
        try:
            data = {
                "address": address,
                "visible": True
            }
            api_response = cls.get_session().post(explorer_url, data=data,
                                                  headers={"content-type": "application/json"}, timeout=25)
            info = api_response.json()
        except Exception as e:
            if raise_error:
                raise e
            return None
        balance = info.get('balance')
        if balance is None:
            return None
        try:
            balance = from_sun(balance)
        except ValueError as e:
            return None
        return {
            'address': address,
            'received': balance,
            'sent': Decimal('0'),
            'balance': Decimal(balance),
            'unconfirmed': Decimal('0'),
        }

    @classmethod
    def get_wallet_balance_trongrid_api(cls, address: str, raise_error=False):
        """ Get TRX account balance from TronGrid API
        """
        explorer_url = "https://try.readme.io/" + cls.get_explorer_url() + 'v1/accounts/{}?only_confirmed=true'
        try:
            session = cls.get_session()
            session.headers['Origin'] = 'https://developers.tron.network'
            api_response = session.get(explorer_url.format(address), timeout=25)
            info = api_response.json()
        except Exception as e:
            if raise_error:
                raise e
            metric_incr('api_errors_count', labels=['trx', 'trongrid'])
            return None
        if not info.get('success'):
            print('[Inspector:Trx][Balance:API] Failed to get TRX balance: {}'.format(str(info.get('error'))))
            return None
        try:
            balance = info.get('data', [{}])[0].get("balance")
        except IndexError:
            balance = 0
        if balance is None:
            return None
        balance = from_sun(balance)
        return {
            'address': address,
            'received': balance,
            'sent': Decimal('0'),
            'balance': Decimal(balance),
            'unconfirmed': Decimal('0'),
        }

    @classmethod
    def get_wallet_transactions_trongrid(cls, address, raise_error=False):
        """ Get TRX account balance from TronGrid
        """
        # explorer_url = "https://try.readme.io/" + cls.get_explorer_url() + 'v1/accounts/{}/transactions?only_to=true&limit=50&only_confirmed=true'
        explorer_url = cls.get_explorer_url() + 'v1/accounts/{}/transactions?only_to=true&limit=50&only_confirmed=true'
        try:
            session = cls.get_session()
            # session.headers['Origin'] = 'https://developers.tron.network'
            api_response = session.get(explorer_url.format(address), timeout=25)
            res = api_response.json()
        except Exception as e:
            if raise_error:
                raise e
            metric_incr('api_errors_count', labels=['trx', 'trongrid'])
            return None
        if not res.get('success'):
            return None
        records = res.get('data')
        if not records:
            return []
        transactions = cls.parse_actions_trongrid(records, address) or []
        return transactions

    @classmethod
    def parse_actions_trongrid(cls, records, address):
        transactions = []
        for record in records:
            raw_data = record.get("raw_data")
            if not raw_data:
                continue
            contract = raw_data.get("contract", [{}])[0]
            transaction_type = contract.get("type")
            if transaction_type != "TransferContract":
                continue
            value = contract.get("parameter", {}).get("value", {}).get("amount")
            if not value:
                continue
            owner_address = contract.get('parameter', {}).get('value', {}).get('owner_address')
            if base58.b58decode_check('TM9RwJndZHmDVLSZcY6J76ci22AzPp2krj').hex().lower() == owner_address.lower():
                value = Decimal('0.000000')

            if base58.b58decode_check('TVCAuYMw5afP96y5Wep866AXVWZJRH8fdo').hex().lower() == owner_address.lower():
                value = Decimal('0.000000')

            try:
                value = from_sun(value)
            except ValueError as e:
                continue
            if value < Decimal('0.001'):
                continue
            # TODO: Don't trust to query parameter and check the to address

            # Estimating confirmations
            confirmations = 20
            transaction_block_number = int(record.get('blockNumber'))
            try:
                latest_block = cache.get('trx_latest_block')
                if latest_block and transaction_block_number:
                    confirmations = max(confirmations, latest_block - transaction_block_number)
            except:
                pass

            timestamp = int(record.get('block_timestamp')) // 1000
            transactions.append(Transaction(
                address=address,
                from_address=[cls.from_hex(owner_address)],
                hash=record.get('txID'),
                timestamp=parse_utc_timestamp(timestamp),
                value=value,
                confirmations=confirmations,
                is_double_spend=False,
                block=transaction_block_number,
                details=record,
            ))
        return transactions

    @classmethod
    def get_wallet_transactions_solidity(cls, address: str, raise_error=False):
        """ Get TRX account balance from TronGrid Solidity Node
        """
        explorer_url = 'http://47.90.247.237:8091/' + 'walletextension/gettransactionstothis'
        try:
            data = {
                'account': {
                    'address': base58.b58decode_check(address).hex().upper()
                },
                'limit': 30
            }
            api_response = cls.get_session().post(explorer_url, data=json.dumps(data),
                                                  headers={"content-type": "application/json"}, timeout=25)
            res = api_response.json()
        except Exception as e:
            if raise_error:
                raise e
            return None
        records = res.get('transaction')
        if not records:
            return []
        transactions = cls.parse_actions_solidity(records, address) or []
        return transactions

    @classmethod
    def parse_actions_solidity(cls, records, address):
        transactions = []
        for record in records:
            contract_ret = record.get('ret', [{}])[0].get('contractRet')
            if contract_ret != "SUCCESS":
                continue
            contract = record.get('raw_data', {}).get('contract', [{}])[0]
            transaction_type = contract.get('type')
            if transaction_type != 'TransferContract':
                continue
            value = contract.get('parameter', {}).get('value', {}).get('amount')
            if not value:
                continue

            try:
                value = from_sun(value)
            except ValueError as e:
                continue
            if value < Decimal('0.001'):
                continue
            owner_address = contract.get('parameter', {}).get('value', {}).get('owner_address')
            if base58.b58decode_check(address).hex().upper() != contract.get('parameter', {}).get('value', {}).get('to_address').upper():
                value = -1 * value

            if base58.b58decode_check('TM9RwJndZHmDVLSZcY6J76ci22AzPp2krj').hex().lower() == owner_address.lower():
                value = Decimal('0.000000')

            if base58.b58decode_check('TVCAuYMw5afP96y5Wep866AXVWZJRH8fdo').hex().lower() == owner_address.lower():
                value = Decimal('0.000000')

            # TODO Don't trust to solidity node and check the number of confirmation
            confirmations = 20
            # Timestamp maybe incorrect in some cases. e.q.: c34cb2268758acdd39922010f0aedc9da8ac821ff287358b057082b835302ede
            timestamp = int(record.get('raw_data', {}).get('expiration'))
            transactions.append(Transaction(
                address=address,
                from_address=[cls.from_hex(owner_address)],
                hash=record.get('txID'),
                timestamp=parse_utc_timestamp_ms(timestamp),
                value=value,
                confirmations=confirmations,
                is_double_spend=False,
                details=record,
            ))
        return transactions

    @classmethod
    def from_hex(cls, address):
        if len(address) < 40:
            address = address.zfill(40)
        if len(address) == 40:
            address = '41' + address
        return base58.b58encode_check(bytes.fromhex(address)).decode()

    @classmethod
    def get_latest_block_addresses(cls, include_inputs=False, include_info=False):
        return cls.get_latest_block_addresses_fullnode(include_inputs=include_inputs,
                                                       include_info=include_info)

    @classmethod
    def get_latest_block_addresses_fullnode(cls, include_inputs=False, include_info=False):
        """
            Retrieve block from blockbook by trezor.io
            :return: Set of addresses output transactions with pay to public key hash
            in last block processed until the last block mined
            API Document: https://bch.btc.com/api-doc
        """

        if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
            return set(), None, 0
        api = TronFullNodeAPI.get_api()
        try:
            return api.get_latest_block(include_inputs=include_inputs, include_info=include_info)
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut) as error:
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            traceback.print_exception(*sys.exc_info())


class TronBlockchainWallet(GeneralBlockchainWallet):
    currency = Currencies.trx

    @classmethod
    def is_bytes(cls, value):
        bytes_types = (bytes, bytearray)
        return isinstance(value, bytes_types)

    def pub_key_to_address(self, pub_key):
        pub_key = PublicKey.from_compressed_bytes(pub_key).to_address()
        address = '41' + pub_key[2:]
        to_base58 = base58.b58encode_check(bytes.fromhex(address))
        if self.is_bytes(to_base58):
            to_base58 = to_base58.decode()
        return to_base58

    @classmethod
    def freeze_wallet(cls, amount, resource, receiver_account):
        trx_hotwallet = get_trx_hotwallet()
        try:
            params = [{
                'receiver_account': receiver_account,
                'amount': amount,
                'resource': resource,
            }, trx_hotwallet.password]

            response = trx_hotwallet.request(
                method="freeze",
                params=params,
                rpc_id="curltext",
            )
            return response

        except Exception as e:
            msg = '[Exception] {}'.format(str(e))
            print(msg)
            return {
                'error': msg,
            }

    @classmethod
    def unfreeze_wallet(cls, resource, receiver_account):
        trx_hotwallet = get_trx_hotwallet()
        try:
            params = [{
                'receiver_account': receiver_account,
                'resource': resource,
            }, trx_hotwallet.password]

            response = trx_hotwallet.request(
                method="unfreeze",
                params=params,
                rpc_id="curltext",
            )
            return response

        except Exception as e:
            msg = '[Exception] {}'.format(str(e))
            print(msg)
            return {
                'error': msg,
            }

    @classmethod
    def mint_wallet(cls, amount, currency):
        trx_hotwallet = TrxClient.get_client()
        try:
            params = [{
                'amount': amount,
            }, trx_hotwallet.password, trx_hotwallet.password]

            response = trx_hotwallet.request(
                method="mint",
                params=params,
                rpc_id="curltext",
            )
            return response

        except Exception as e:
            msg = '[Exception] {}'.format(str(e))
            print(msg)
            return {
                'error': msg,
            }

    @classmethod
    def ztron_balance_wallet(cls, currency):
        trx_hotwallet = TrxClient.get_client()
        try:
            params = [{}]

            response = trx_hotwallet.request(
                method="get_rcm_values",
                params=params,
                rpc_id="curltext",
            )
            return response

        except Exception as e:
            msg = '[Exception] {}'.format(str(e))
            print(msg)
            return {
                'error': msg,
            }
