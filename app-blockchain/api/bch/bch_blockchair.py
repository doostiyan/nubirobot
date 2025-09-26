from cashaddress import convert
from cashaddress.convert import InvalidAddress
from decimal import Decimal
from typing import List
import datetime

from django.conf import settings

from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.general.general import GeneralApi, ResponseValidator, ResponseParser
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.general.dtos.dtos import TransferTx


class BitcoinCashBlockchairValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.003')
    precision = 8

    @classmethod
    def validate_general_response(cls, response):
        if not response or not isinstance(response, dict):
            return False
        if not response.get('data') or not isinstance(response.get('data'), dict):
            return False
        if not response.get('context') or not isinstance(response.get('context'), dict):
            return False
        if not response.get('context').get('state') or not isinstance(response.get('context').get('state'), int):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False
        if not tx_details_response.get('tx_hash') or not isinstance(tx_details_response.get('tx_hash'), str):
            return False
        tx_hash = tx_details_response.get('tx_hash')
        if not tx_details_response.get('data').get(tx_hash) or not isinstance(tx_details_response.get('data').get(tx_hash), dict):
            return False
        tx_details = tx_details_response.get('data').get(tx_hash)
        if not tx_details or not isinstance(tx_details, dict):
            return False
        if not tx_details.get('transaction') or not isinstance(tx_details.get('transaction'), dict):
            return False
        transaction = tx_details.get('transaction')
        if tx_details_response.get('ethereumSpecific'):
            if tx_details_response.get('ethereumSpecific').get('status') != 1:
                return False
        else:
            if not transaction.get('block_id') or not isinstance(transaction.get('block_id'), int):
                return False
            if transaction.get('block_id') == -1:
                return False
        if not transaction.get('hash') or not isinstance(transaction.get('hash'), str):
            return False
        if not transaction.get('time') or not isinstance(transaction.get('time'), str):
            return False
        if transaction.get('fee') is None or not isinstance(transaction.get('fee'), int):
            return False
        if not tx_details.get('inputs') or not tx_details.get('outputs'):
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False
        if not address_txs_response.get('address') or not isinstance(address_txs_response.get('address'), str):
            return False
        address = address_txs_response.get('address')
        if not address_txs_response.get('data').get(address) or not isinstance(
                address_txs_response.get('data').get(address), dict):
            return False
        data = address_txs_response.get('data').get(address)
        if not data.get('transactions') or not isinstance(data.get('transactions'), list):
            return False
        if not data.get('address').get('type') == 'pubkeyhash':
            return False
        if data.get('address').get('formats').get('cashaddr') != address and data.get('address').get('formats').get(
                'legacy') != address:
            return False
        return True

    @classmethod
    def validate_tx_details_transaction(cls, transaction) -> bool:
        if not transaction.get('value') or not isinstance(transaction.get('value'), int):
            return False
        value = BlockchainUtilsMixin.from_unit(transaction.get('value'), cls.precision)
        if value < cls.min_valid_tx_amount:
            return False
        if not transaction.get('recipient') or not isinstance(transaction.get('recipient'), str):
            return False
        if transaction.get('is_from_coinbase') or not isinstance(transaction.get('is_from_coinbase'), bool):
            return False
        return True

    @classmethod
    def validate_address_tx_transaction(cls, transaction) -> bool:
        if not transaction.get('block_id') or not isinstance(transaction.get('block_id'), int):
            return False
        if transaction.get('block_id') == -1:
            return False
        if not transaction.get('hash') or not isinstance(transaction.get('hash'), str):
            return False
        if not transaction.get('time') or not isinstance(transaction.get('time'), str):
            return False
        if not transaction.get('balance_change') or not isinstance(transaction.get('balance_change'), int):
            return False
        if transaction.get('balance_change') < 0:
            return False
        return True


class BitcoinCashBlockchairResponseParser(ResponseParser):
    validator = BitcoinCashBlockchairValidator
    symbol = 'BCH'
    currency = Currencies.bch
    precision = 8

    @classmethod
    def convert_address(cls, address):
        try:
            return convert.to_legacy_address(address)
        except InvalidAddress:
            return None

    @classmethod
    def parse_tx_details_response(cls, tx_details_response, block_head) -> List[TransferTx]:
        transfers: List[TransferTx] = []
        if cls.validator.validate_tx_details_response(tx_details_response):
            block_head = tx_details_response.get('context').get('state')
            tx_hash = tx_details_response.get('tx_hash')
            data = tx_details_response.get('data').get(tx_hash)
            block_height = data.get('transaction').get('block_id')
            date = parse_iso_date('T'.join(data.get('transaction').get('time').split()) + 'Z')
            fee = BlockchainUtilsMixin.from_unit(data.get('transaction').get('fee'), precision=cls.precision)
            for input in data.get('inputs'):
                if cls.validator.validate_tx_details_transaction(input):
                    # The address in the response is cashaddress without the prefix bitcoincash, so we should add it to
                    # the address so, we can convert it to legacy address.
                    cash_address = 'bitcoincash:' + input.get('recipient')
                    from_address = cls.convert_address(cash_address)
                    value = BlockchainUtilsMixin.from_unit(input.get('value'), precision=cls.precision)
                    for tx in transfers:
                        if tx.from_address == from_address:
                            tx.value += value
                            break
                    else:
                        transfer = TransferTx(
                            tx_hash=tx_hash,
                            from_address=from_address,
                            to_address='',
                            value=value,
                            block_height=block_height,
                            confirmations=block_head - block_height,
                            success=True,
                            symbol=cls.symbol,
                            date=date,
                            tx_fee=fee,
                        )
                        transfers.append(transfer)
            for output in data.get('outputs'):
                if cls.validator.validate_tx_details_transaction(output) and output.get('type') == 'pubkeyhash':
                    cash_address = 'bitcoincash:' + output.get('recipient')
                    to_address = cls.convert_address(cash_address)
                    value = BlockchainUtilsMixin.from_unit(output.get('value'), precision=cls.precision)
                    for tx in transfers:
                        if tx.from_address == to_address:
                            tx.value -= value
                            break
                    else:
                        transfer = TransferTx(
                            tx_hash=tx_hash,
                            from_address='',
                            to_address=to_address,
                            value=value,
                            block_height=block_height,
                            confirmations=block_head - block_height,
                            success=True,
                            symbol=cls.symbol,
                            date=date,
                            tx_fee=fee,
                        )
                        transfers.append(transfer)

        return transfers

    @classmethod
    def parse_address_txs_response(cls, address, address_txs_response, block_head) -> List[TransferTx]:
        address_txs: List[TransferTx] = []
        if cls.validator.validate_address_txs_response(address_txs_response):
            address = address_txs_response.get('address')
            transactions = address_txs_response.get('data').get(address).get('transactions')
            to_address = address_txs_response.get('data').get(address).get('address').get('formats').get('legacy')
            block_head = address_txs_response.get('context').get('state')
            address_txs: List[TransferTx] = []
            for transaction in transactions:
                if cls.validator.validate_address_tx_transaction(transaction):
                    block_height = transaction.get('block_id')
                    tx_hash = transaction.get('hash')
                    date = parse_iso_date('T'.join(transaction.get('time').split()) + 'Z')
                    value = BlockchainUtilsMixin.from_unit(transaction.get('balance_change'), precision=cls.precision)
                    transfer = TransferTx(
                        tx_hash=tx_hash,
                        to_address=to_address,
                        from_address='',
                        value=value,
                        block_height=block_height,
                        confirmations=block_head - block_height,
                        success=True,
                        symbol=cls.symbol,
                        date=date,
                    )
                    address_txs.append(transfer)

        return address_txs


class BitcoinCashBlockchairApi(GeneralApi):
    parser = BitcoinCashBlockchairResponseParser
    _base_url = 'https://api.blockchair.com/bitcoin-cash'
    cache_key = 'bch'
    symbol = 'BCH'
    rate_limit = 0.2
    need_block_head_for_confirmation = False
    supported_requests = {
        'get_address_txs': '/dashboards/address/{address}?transaction_details=true&limit=15',
        'get_tx_details': '/dashboards/transactions/{tx_hash}?transaction_details=true'
    }

    # For both request we need tx_hash or address in the response because to get the details of the request
    # we need to get them by these hashes or addresses and without them, we cannot access them.
    @classmethod
    def get_tx_details(cls, tx_hash):
        response = cls.request(request_method='get_tx_details', body=cls.get_tx_details_body(tx_hash),
                               headers=cls.get_headers(), tx_hash=tx_hash, apikey=cls.get_api_key(),
                               timeout=cls.timeout)
        response['tx_hash'] = tx_hash
        return response

    @classmethod
    def get_address_txs(cls, address, **kwargs):
        response = cls.request(request_method='get_address_txs', body=cls.get_address_txs_body(address),
                               headers=cls.get_headers(), address=address, apikey=cls.get_api_key(),
                               timeout=cls.timeout)
        response['address'] = address
        return response
