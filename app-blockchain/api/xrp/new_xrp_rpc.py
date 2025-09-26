import json
from decimal import Decimal
from typing import List

from django.conf import settings
from exchange.blockchain.api.general.general import GeneralApi, ResponseValidator, ResponseParser
from exchange.blockchain.utils import BlockchainUtilsMixin
from exchange.base.parsers import parse_utc_timestamp_from_2000

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.general.dtos.dtos import TransferTx


class RippleRpcValidator(ResponseValidator):

    @classmethod
    def validate_general_response(cls, response):
        if not response or not isinstance(response, dict):
            return False
        if not response.get('result') or not isinstance(response.get('result'), dict):
            return False
        return True

    @classmethod
    def validate_balance_response(cls, balance_response) -> bool:
        if not cls.validate_general_response(balance_response):
            return False
        result = balance_response.get('result')
        if not result.get('account_data') or not isinstance(result.get('account_data'), dict):
            return False
        if (not result.get('account_data').get('Balance') or
                not isinstance(result.get('account_data').get('Balance'), str)):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False
        transaction = tx_details_response.get('result')
        if not transaction.get('validated'):
            return False
        if not transaction.get('status') or not isinstance(transaction.get('status'), str):
            return False
        if not transaction.get('status').casefold() == 'success'.casefold():
            return False
        meta = transaction.get('meta')
        if not meta or not isinstance(meta, dict):
            return False
        if (not meta.get('TransactionResult') or
                not meta.get('TransactionResult') == 'tesSUCCESS'):
            return False
        if not meta.get('delivered_amount') or isinstance(meta.get('delivered_amount'), dict):
            return False
        return cls.validate_transaction(transaction)

    @classmethod
    def validate_transaction(cls, transaction) -> bool:
        if any(transaction.get(field) is None for field in
               ('TransactionType', 'Account', 'Destination', 'Fee', 'date', 'hash', 'ledger_index')):
            return False
        if not transaction.get('TransactionType') == 'Payment':
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False
        if not address_txs_response.get('result').get('status').casefold() == 'success'.casefold():
            return False
        if (not address_txs_response.get('result').get('ledger_index_max') or
                not isinstance(address_txs_response.get('result').get('ledger_index_max'), int)):
            return False
        if (not address_txs_response.get('result').get('transactions') or
                not isinstance(address_txs_response.get('result').get('transactions'), list)):
            return False
        return True

    @classmethod
    def validate_address_tx_transaction(cls, transaction) -> bool:
        meta = transaction.get('meta')
        if not transaction.get('validated'):
            return False
        if not meta or not isinstance(meta, dict):
            return False
        if (not meta.get('TransactionResult') or
                not meta.get('TransactionResult') == 'tesSUCCESS'):
            return False
        if not meta.get('delivered_amount') or isinstance(meta.get('delivered_amount'), dict):
            return False
        tx = transaction.get('tx')
        return cls.validate_transaction(tx)


class RippleRpcResponseParser(ResponseParser):
    validator = RippleRpcValidator
    symbol = 'XRP'
    currency = Currencies.xrp
    precision = 6

    @classmethod
    def parse_balance_response(cls, balance_response) -> Decimal:
        if cls.validator.validate_balance_response(balance_response):
            balance = balance_response.get('result').get('account_data').get('Balance')
            return BlockchainUtilsMixin.from_unit(int(balance), cls.precision)
        return Decimal('0')

    @classmethod
    def parse_tx_details_response(cls, tx_details_response, block_head) -> List[TransferTx]:
        if cls.validator.validate_tx_details_response(tx_details_response):
            transaction = tx_details_response.get('result')
            from_address = transaction.get('Account')
            to_address = transaction.get('Destination')
            memo = transaction.get('DestinationTag')
            tx_hash = transaction.get('hash')
            amount = BlockchainUtilsMixin.from_unit(int(transaction.get('meta').get('delivered_amount')),
                                                    cls.precision)
            fee = BlockchainUtilsMixin.from_unit(int(transaction.get('Fee')), cls.precision)
            date = parse_utc_timestamp_from_2000(transaction.get('date'))
            block_height = transaction.get('ledger_index')
            return [TransferTx(
                from_address=from_address,
                to_address=to_address,
                memo='' if memo is None else str(memo),
                tx_hash=tx_hash,
                value=amount,
                block_height=block_height,
                tx_fee=fee,
                date=date,
                symbol=cls.symbol,
                success=True
            )]
        return []

    @classmethod
    def parse_address_txs_response(cls, address, address_txs_response, block_head) -> List[TransferTx]:
        address_txs: List[TransferTx] = []
        if cls.validator.validate_address_txs_response(address_txs_response):
            transactions = address_txs_response.get('result').get('transactions')
            for transaction in transactions:
                if cls.validator.validate_address_tx_transaction(transaction):
                    tx = transaction.get('tx')
                    from_address = tx.get('Account')
                    to_address = tx.get('Destination')
                    memo = tx.get('DestinationTag')
                    tx_hash = tx.get('hash')
                    amount = BlockchainUtilsMixin.from_unit(int(transaction.get('meta').get('delivered_amount')),
                                                            cls.precision)
                    fee = BlockchainUtilsMixin.from_unit(int(tx.get('Fee')), cls.precision)
                    date = parse_utc_timestamp_from_2000(tx.get('date'))
                    block_head = address_txs_response.get('result').get('ledger_index_max')
                    block_height = tx.get('ledger_index')
                    confirmation = block_head - block_height
                    address_tx = TransferTx(
                        from_address=from_address,
                        to_address=to_address,
                        memo='' if memo is None else str(memo),
                        value=amount,
                        tx_hash=tx_hash,
                        tx_fee=fee,
                        date=date,
                        confirmations=confirmation,
                        symbol=cls.symbol,
                        success=True,
                        block_height=block_height,
                    )
                    address_txs.append(address_tx)
        return address_txs


class RippleClusterApi(GeneralApi):
    parser = RippleRpcResponseParser
    _base_url = 'https://xrplcluster.com'
    cache_key = 'xrp'
    symbol = 'XRP'
    need_block_head_for_confirmation = False
    supported_requests = {
        'get_tx_details': '',
        'get_address_txs': '',
        'get_balance': ''
    }

    @classmethod
    def get_headers(cls):
        return {
            'content-type': 'application/json'
        }

    @classmethod
    def get_address_txs_body(cls, address):
        data = {
            "method": "account_tx",
            "params": [
                {
                    "account": address,
                    "binary": False,
                    "forward": False,
                    "ledger_index_max": -1,
                    "ledger_index_min": -1,
                    "limit": 500
                }
            ]
        }

        return json.dumps(data)

    @classmethod
    def get_tx_details_body(cls, tx_hash):
        data = {
            "method": "tx",
            "params": [
                {
                    "transaction": tx_hash,
                    "binary": False,
                }
            ]
        }
        return json.dumps(data)

    @classmethod
    def get_balance_body(cls, address):
        data = {
            "method": "account_info",
            "params": [
                {
                    "account": address,
                    "ledger_index": "current",
                    "queue": True
                }
            ]
        }
        return json.dumps(data)


class RippleWsApi(RippleClusterApi):
    _base_url = 'https://xrpl.ws/'


class RippleS1Api(RippleClusterApi):
    _base_url = 'https://s1.ripple.com:51234/'


class RippleS2Api(RippleClusterApi):
    _base_url = 'https://s2.ripple.com:51234/'
