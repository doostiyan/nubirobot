import json
import random
from functools import partial
from typing import List

from django.conf import settings

from exchange.base.logging import report_event
from exchange.blockchain.api.general.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.segwit_address import one_to_eth_address
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from blockchain.parsers import parse_utc_timestamp
    from wallet.models import CURRENCIES as Currencies
    from wallet.models import harmony_ERC20_contract_currency, harmony_ERC20_contract_info
else:
    from exchange.base.models import Currencies
    from exchange.base.parsers import parse_utc_timestamp
    from exchange.blockchain.contracts_conf import harmony_ERC20_contract_currency, harmony_ERC20_contract_info

report_event = partial(report_event, level='warning')


class OneRpcValidator(ResponseValidator):
    @classmethod
    def validate_general_response(cls, response: dict) -> bool:
        if not response:
            return False
        if response.get('error'):
            return False
        if not response.get('result'):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, address_txs_response: dict) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False
        if not address_txs_response.get('result').get('blockNumber'):
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: dict) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False
        if not address_txs_response.get('result').get('transactions'):
            return False
        return True

    @classmethod
    def validate_address_tx_transaction(cls, transaction: dict) -> bool:
        if not cls.validate_transaction(transaction):
            return False
        if transaction.get('shardID') != 0 or transaction.get('toShardID') != 0:
            return False
        if not cls.is_main_token_transfer(transaction):
            return False
        if transaction.get('from') == transaction.get('to'):
            return False
        if transaction.get('from') in cls.invalid_from_addresses_for_ETH_like:
            return False
        return True

    @classmethod
    def validate_token_transaction(cls, transaction: dict, contract_info: dict, direction='') -> bool: # noqa: ANN001
        if not cls.validate_transaction(transaction):
            return False
        if transaction.get('shardID') != 0 or transaction.get('toShardID') != 0:
            return False
        if not cls.is_token_transfer(transaction):
            return False
        if transaction.get('from') == transaction.get('to'):
            return False
        if transaction.get('from') in cls.invalid_from_addresses_for_ETH_like:
            return False
        if one_to_eth_address(transaction.get('to')).lower() != contract_info['address']:
            return False
        return True

    @classmethod
    def is_token_transfer(cls, transaction: dict) -> bool:
        input_len = 138
        return transaction.get('input')[0:10] == '0xa9059cbb' and len(transaction.get('input')) == input_len

    @classmethod
    def is_main_token_transfer(cls, transaction: dict) -> bool:
        return transaction.get('input') in ('0x', '0x0000000000000000000000000000000000000000')

    @classmethod
    def validate_transaction(cls, transaction: dict) -> bool:
        transaction_keys = {
            'input',
            'blockNumber',
            'from',
            'to',
            'blockHash',
            'timestamp',
            'ethHash'
        }
        for key in transaction_keys:
            if not transaction.get(key):
                return False
        if 'value' not in transaction:
            return False
        if not (cls.is_token_transfer(transaction) or cls.is_main_token_transfer(transaction)):
            return False
        return True

    @classmethod
    def validate_address_tx_receipt_transaction(cls, address_tx_receipt_transaction: dict) -> bool:
        if not cls.validate_general_response(address_tx_receipt_transaction):
            return False
        if not isinstance(address_tx_receipt_transaction, dict):
            return False
        if address_tx_receipt_transaction.get('result').get('status') != 1:
            return False
        return True

    @classmethod
    def validate_tx_receipt_response(cls, tx_receipt_response: dict) -> bool:
        if not cls.validate_general_response(tx_receipt_response):
            return False
        return tx_receipt_response.get('result').get('status') == 1

    @classmethod
    def validate_tx_details_transaction(cls, transaction: dict) -> bool:
        if not cls.validate_general_response(transaction):
            return False
        if not cls.validate_transaction(transaction.get('result')):
            return False
        return True

    @classmethod
    def validate_block_tx_transaction(cls, transaction: dict) -> bool:
        block_keys = {
            'number',
            'hash',
            'timestamp',
            'transactions'
        }
        for key in block_keys:
            if not transaction.get(key):
                return False
        if not isinstance(transaction.get('transactions'), list):
            return False
        return True

    @classmethod
    def validate_block_txs_raw_response(cls, block_txs_raw_response: dict) -> bool:
        if not block_txs_raw_response or not isinstance(block_txs_raw_response, dict):
            return False
        if not block_txs_raw_response.get('result') or not isinstance(block_txs_raw_response.get('result'), list):
            return False
        return True


class OneRpcParser(ResponseParser):
    validator = OneRpcValidator
    currency = Currencies.one
    precision = 18
    symbol = 'ONE'

    @classmethod
    def contract_currency_list(cls) -> dict:
        return harmony_ERC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_currency(cls, token_address: str) -> int:
        return cls.contract_currency_list().get(token_address)

    @classmethod
    def contract_info_list(cls) -> dict:
        return harmony_ERC20_contract_info.get(cls.network_mode)

    @classmethod
    def contract_info(cls, currency: int) -> dict:
        return cls.contract_info_list().get(currency)

    @classmethod
    def parse_block_head_response(cls, block_head_response: dict) -> int:
        if not cls.validator.validate_block_head_response(block_head_response):
            return 0
        return block_head_response.get('result').get('blockNumber')

    @classmethod
    def parse_address_txs_response(cls, address: str, address_txs_response: dict, block_head: int) -> dict:
        if not cls.validator.validate_address_txs_response(address_txs_response):
            return {}

        ready_for_receipt = []
        transactions = address_txs_response.get('result').get('transactions')
        for tx in transactions:
            if not cls.validator.validate_address_tx_transaction(tx):
                continue
            ready_for_receipt.append({'jsonrpc': '2.0', 'method': 'hmyv2_getTransactionReceipt',
                                      'params': [tx['ethHash']], 'id': tx['ethHash']})

        return {'receipts': ready_for_receipt,
                'transactions': address_txs_response}

    @classmethod
    def parse_address_txs_receipt(cls, address_txs_receipt: dict, block_head: int) -> List[TransferTx]:
        receipts = address_txs_receipt.get('receipts')
        transactions = address_txs_receipt.get('transactions')

        receipts_dict = cls._convert2dict(receipts)
        transfers = []

        for tx in transactions.get('result').get('transactions'):
            receipt = receipts_dict.get(tx.get('ethHash'))
            if not receipt or not cls.validator.validate_address_tx_receipt_transaction(receipt):
                continue

            if cls.convert_address(tx.get('from')) in cls.validator.invalid_from_addresses_for_ETH_like:
                continue
            transfers.append(
                TransferTx(
                    tx_hash=tx.get('ethHash'),
                    from_address=cls.convert_address(tx.get('from')),
                    to_address=cls.convert_address(tx.get('to')),
                    success=True,
                    block_height=tx.get('blockNumber'),
                    block_hash=tx.get('blockHash'),
                    date=parse_utc_timestamp(tx.get('timestamp')),
                    confirmations=block_head - tx.get('blockNumber') if block_head else None,
                    value=BlockchainUtilsMixin.from_unit(tx.get('value'), cls.precision),
                    symbol=cls.symbol,
                )
            )
        return transfers

    @classmethod
    def parse_token_txs_response(cls, address: str, token_txs_response: dict, block_head: dict, contract_info: dict,
                                 direction='') -> dict: # noqa: ANN001
        if not cls.validator.validate_address_txs_response(token_txs_response):
            return {}

        ready_for_receipt = []
        transactions = token_txs_response.get('result').get('transactions')
        for tx in transactions:
            if not cls.validator.validate_token_transaction(tx, contract_info):
                continue
            ready_for_receipt.append({'jsonrpc': '2.0', 'method': 'hmyv2_getTransactionReceipt',
                                      'params': [tx['ethHash']], 'id': tx['ethHash']})

        return {'receipts': ready_for_receipt,
                'token_transactions': token_txs_response}

    @classmethod
    def parse_token_txs_receipt(cls, token_txs_receipt: dict, contract_info: dict, block_head: int) -> List[
        TransferTx]:
        receipts = token_txs_receipt.get('receipts')
        transactions = token_txs_receipt.get('transactions')

        receipts_dict = cls._convert2dict(receipts)
        transfers = []

        for tx in transactions.get('result').get('transactions'):
            receipt = receipts_dict.get(tx.get('ethHash'))
            if not receipt or not cls.validator.validate_address_tx_receipt_transaction(receipt):
                continue

            token_properties = cls.decode_token_tx_input_data(tx.get('input'))
            to_address = token_properties.get('to')
            value = token_properties.get('value')

            transfers.append(
                TransferTx(
                    tx_hash=tx.get('ethHash'),
                    from_address=cls.convert_address(tx.get('from')),
                    to_address=to_address,
                    success=True,
                    block_height=tx.get('blockNumber'),
                    block_hash=tx.get('blockHash'),
                    date=parse_utc_timestamp(tx.get('timestamp')),
                    confirmations=block_head - tx.get('blockNumber') if block_head else None,
                    value=BlockchainUtilsMixin.from_unit(value, contract_info.get('decimals')),
                    symbol=contract_info.get('symbol'),
                )
            )
        return transfers

    @classmethod
    def decode_token_tx_input_data(cls, input_data: str) -> dict:
        value, to = None, None
        try:
            value = int(input_data[74:138], 16)
            to = '0x' + input_data[34:74]
        except Exception:
            pass
        return {'value': value, 'to': to}

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: dict, block_head: int) -> List[TransferTx]:
        if not cls.validator.validate_tx_details_transaction(tx_details_response):
            return []

        transaction = tx_details_response.get('result')
        tx_data = cls._parse_transaction_data(transaction)
        if not tx_data:
            return []

        return [TransferTx(
            block_height=transaction.get('blockNumber'),
            block_hash=transaction.get('blockHash'),
            tx_hash=transaction.get('ethHash'),
            success=True,
            confirmations=block_head - transaction.get('blockNumber') if block_head else None,
            from_address=cls.convert_address(transaction.get('from')),
            to_address=tx_data.get('to_address'),
            value=tx_data.get('value'),
            symbol=tx_data.get('symbol'),
            token=tx_data.get('token'),
            date=parse_utc_timestamp(transaction.get('timestamp')),
        )
        ]

    @classmethod
    def _parse_transaction_data(cls, transaction: dict) -> dict:
        token = None
        symbol = cls.symbol
        if cls.validator.is_token_transfer(transaction):
            token = cls.convert_address(transaction.get('to'))
            token_properties = cls.decode_token_tx_input_data(transaction.get('input'))
            to_address = token_properties.get('to')
            currency = cls.contract_currency(to_address.lower())
            if not currency:
                return {}

            contract_info = cls.contract_info(currency)
            value = BlockchainUtilsMixin.from_unit(token_properties.get('value'), contract_info.get('decimals'))
            symbol = contract_info.get('symbol')
        else:
            to_address = cls.convert_address(transaction.get('to'))
            value = BlockchainUtilsMixin.from_unit(transaction.get('value'), precision=cls.precision)

        return {
            'to_address': to_address,
            'value': value,
            'token': token,
            'symbol': symbol
        }

    @classmethod
    def parse_tx_receipt_response(cls, tx_receipt_response: dict) -> bool:
        return cls.validator.validate_tx_receipt_response(tx_receipt_response)

    @classmethod
    def parse_batch_block_txs_response(cls, batch_block_txs_response: dict) -> List[TransferTx]:
        if not cls.validator.validate_general_response(batch_block_txs_response):
            return []

        transfers = []
        blocks = batch_block_txs_response.get('result')
        for block in blocks:
            if not cls.validator.validate_block_tx_transaction(block):
                continue

            transactions = block.get('transactions')
            for transaction in transactions:
                if not cls.validator.validate_transaction(transaction):
                    continue

                tx_data = cls._parse_transaction_data(transaction)
                if not tx_data:
                    continue
                if cls.convert_address(transaction.get('from')) in cls.validator.invalid_from_addresses_for_ETH_like:
                    continue
                transfers.append(
                    TransferTx(
                        block_height=transaction.get('blockNumber'),
                        block_hash=transaction.get('blockHash'),
                        tx_hash=transaction.get('ethHash'),
                        success=True,
                        from_address=cls.convert_address(transaction.get('from')),
                        to_address=tx_data.get('to_address'),
                        value=tx_data.get('value'),
                        symbol=tx_data.get('symbol'),
                        token=tx_data.get('token'),
                        date=parse_utc_timestamp(transaction.get('timestamp'))
                    )
                )
        return transfers

    @classmethod
    def convert_address(cls, address: str) -> str:
        try:
            return one_to_eth_address(address).lower()
        except Exception:
            return address

    @staticmethod
    def _convert2dict(receipts: list) -> dict:
        try:
            return {receipt.get('id'): receipt for receipt in receipts}
        except Exception:
            return {}


class OneRpcApi(GeneralApi):
    NEED_ADDRESS_TRANSACTION_RECEIPT = True
    NEED_TOKEN_TRANSACTION_RECEIPT = True
    SUPPORT_BATCH_GET_BLOCKS = True
    need_transaction_receipt = True
    parser = OneRpcParser
    GET_TXS_OFFSET = 0
    GET_TXS_LIMIT = 25
    cache_key = 'one'
    rate_limit = 0

    # you can use https://api.harmony.one or https://harmony.public-rpc.com or https://api.s0.t.hmny.io
    _base_url = 'https://api.harmony.one'

    # https://harmony.public-rpc.com
    # https://harmony-0-rpc.gateway.pokt.network
    # https://1rpc.io/one'

    @classmethod
    def get_headers(cls) -> dict:
        return {'content-type': 'application/json'}

    @classmethod
    def get_address_txs_body(cls, address: str) -> str:
        return cls._address_txs_token_txs_body(address)

    @classmethod
    def get_token_txs_body(cls, address: str, contract_info: dict) -> str:
        return cls._address_txs_token_txs_body(address)

    @classmethod
    def _address_txs_token_txs_body(cls, address: str) -> str:
        return json.dumps({
            'jsonrpc': '2.0',
            'method': 'hmyv2_getTransactionsHistory',
            'params': [
                {
                    'address': address,
                    'pageIndex': cls.GET_TXS_OFFSET,
                    'pageSize': cls.GET_TXS_LIMIT,
                    'fullTx': True,
                    'txType': 'ALL',
                    'order': 'DESC'
                }
            ],
            'id': 1
        })

    @classmethod
    def get_block_head_body(cls) -> str:
        return json.dumps({'jsonrpc': '2.0', 'method': 'hmyv2_latestHeader', 'params': [], 'id': 1})

    @classmethod
    def get_address_txs_receipt(cls, data_dict: dict) -> dict:
        receipts = cls.request('', body=json.dumps(data_dict.get('receipts')),
                               headers=cls.get_headers())
        return {
            'receipts': receipts,
            'transactions': data_dict.get('transactions')
        }

    @classmethod
    def get_token_txs_receipt(cls, data_dict: dict) -> dict:
        receipts = cls.request('', body=json.dumps(data_dict.get('receipts')),
                               headers=cls.get_headers())
        return {
            'receipts': receipts,
            'transactions': data_dict.get('token_transactions')
        }

    @classmethod
    def get_tx_details_body(cls, tx_hash: str) -> str:
        tx_data = {'jsonrpc': '2.0', 'method': 'hmyv2_getTransactionByHash', 'params': [tx_hash], 'id': 1}
        return json.dumps(tx_data)

    @classmethod
    def get_tx_receipt_body(cls, tx_hash: str) -> str:
        receipt_data = {'jsonrpc': '2.0', 'method': 'hmyv2_getTransactionReceipt', 'params': [tx_hash], 'id': 1}
        return json.dumps(receipt_data)

    @classmethod
    def get_blocks_txs_body(cls, from_block: int, to_block: int) -> str:
        req_schema = {
            'jsonrpc': '2.0',
            'method': 'hmyv2_getBlocks',
            'params': [
                from_block - 1,
                to_block,
                {
                    'withSigners': False,
                    'fullTx': True,
                    'inclStaking': False
                }
            ],
            'id': 1
        }
        return json.dumps(req_schema)


class AnkrHarmonyRpc(OneRpcApi):
    """
    rate limit doc: https://www.ankr.com/docs/rpc-service/service-plans/#rate-limits
    """
    _base_url = 'https://rpc.ankr.com/harmony'
    rate_limit = 0.033  # ≈1800 requests/minute — guaranteed

    supported_requests = {
        'get_tx_details': '/{apikey}',
        'get_tx_receipt': '/{apikey}',
        'get_block_head': '/{apikey}',
    }

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice(settings.HARMONY_ANKER_API_KEY)
