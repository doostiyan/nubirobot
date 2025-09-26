import json
from decimal import Decimal
from typing import List, Optional

from exchange.base.models import Currencies
from exchange.base.parsers import parse_utc_timestamp_ms
from exchange.blockchain.api.general.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin


class BlastSuiValidator(ResponseValidator):
    valid_tx_types: set = {'ProgrammableTransaction'}
    valid_tx_functions: set = {'TransferObjects'}
    valid_coin_type = ['0x2::sui::SUI']

    @classmethod
    def validate_general_response(cls, response: dict) -> bool:
        if not response:
            return False
        if response.get('error'):
            return False
        if 'result' not in response:
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, response: dict) -> bool:
        if not cls.validate_general_response(response):
            return False
        if not isinstance(response.get('result'), str):
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, response: dict) -> bool:
        if not cls.validate_general_response(response):
            return False
        if not isinstance(response.get('result'), dict):
            return False
        if not isinstance(response['result'].get('data'), list):
            return False

        return True

    @classmethod
    def validate_tx_details_response(cls, response: dict) -> bool:
        if not cls.validate_general_response(response):
            return False
        if not isinstance(response.get('result'), dict):
            return False
        if not cls.validate_transaction(transaction=response['result']):
            return False
        return True

    @classmethod
    def validate_block_txs_response(cls, response: dict) -> bool:
        if not cls.validate_general_response(response=response):
            return False

        if not response.get('result').get('data') and response.get('result').get('data')[0].get('transactions'):
            return False

        return True

    @classmethod
    def validate_batch_tx_details_response(cls, batch_tx_details_response: dict) -> bool:
        if not cls.validate_general_response(response=batch_tx_details_response):
            return False

        return True

    @classmethod
    def validate_transaction(cls, transaction: dict) -> bool:
        if not transaction.get('digest'):
            return False

        if not transaction.get('checkpoint'):
            return False

        if transaction.get('transaction', {}).get('data', {}).get('transaction', {}).get(
                'kind') not in cls.valid_tx_types:
            return False

        if not cls.valid_tx_functions.issubset({list(i.keys())[0] for i in
                                                transaction['transaction']['data']['transaction'].get(
                                                    'transactions')}):
            return False

        if not transaction.get('balanceChanges'):
            return False

        if not all(i.get('owner') and i.get('owner', {}).get('AddressOwner') for i in transaction['balanceChanges']):
            return False

        if not any(int(entry['amount']) > 0 for entry in transaction.get('balanceChanges')):
            return False

        if not transaction.get('transaction', {}).get('data', {}).get('sender'):
            return False

        to_address: str = BlastSuiParser().parse_to_address(balance_changes=transaction['balanceChanges'])

        if not to_address:
            return False

        if transaction.get('transaction', {}).get('data', {}).get('sender') == to_address:
            return False

        if transaction.get('effects', {}).get('status', {}).get('status') != 'success':
            return False

        if BlastSuiParser().parse_amount(balance_changes=transaction['balanceChanges']) <= cls.min_valid_tx_amount:
            return False

        return True


class BlastSuiParser(ResponseParser):
    validator = BlastSuiValidator
    precision = 9
    symbol = 'SUI'
    currency = Currencies.sui

    @classmethod
    def parse_block_head_response(cls, block_head_response: dict) -> int:
        if not cls.validator.validate_block_head_response(block_head_response):
            return 0
        return int(block_head_response.get('result'))

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: dict, block_head: int) -> List[TransferTx]:
        if not cls.validator.validate_tx_details_response(tx_details_response):
            return []
        tx = tx_details_response.get('result')
        return [
            TransferTx(
                tx_hash=tx.get('digest'),
                from_address=cls._parse_from_address(transaction=tx),
                to_address=cls.parse_to_address(balance_changes=tx['balanceChanges']),
                success=True,
                block_height=int(tx.get('checkpoint')),
                date=parse_utc_timestamp_ms(s=tx.get('timestampMs')),
                confirmations=block_head - int(tx.get('checkpoint')) if block_head and tx.get('checkpoint') else None,
                value=cls.parse_amount(balance_changes=tx['balanceChanges']),
                symbol=cls.symbol,
            )
        ]

    @classmethod
    def parse_batch_tx_details_response(cls, batch_tx_details_response: dict, block_head: int) -> List[TransferTx]:
        transfers_txs: List[TransferTx] = []
        if cls.validator.validate_batch_tx_details_response(batch_tx_details_response):
            for transaction in batch_tx_details_response.get('result'):
                if cls.validator.validate_transaction(transaction):
                    transfers_txs.append(TransferTx(
                        tx_hash=transaction.get('digest'),
                        from_address=cls._parse_from_address(transaction=transaction),
                        to_address=cls.parse_to_address(balance_changes=transaction['balanceChanges']),
                        success=True,
                        block_height=int(transaction.get('checkpoint')),
                        date=parse_utc_timestamp_ms(s=transaction.get('timestampMs')),
                        confirmations=block_head - int(transaction.get('checkpoint')) if block_head and transaction.get(
                            'checkpoint') else None,
                        value=cls.parse_amount(balance_changes=transaction['balanceChanges']),
                        symbol=cls.symbol,
                    ))

        return transfers_txs

    @classmethod
    def parse_address_txs_response(cls, address: str, address_txs_response: dict, block_head: int) -> list:
        _ = address
        if not cls.validator.validate_address_txs_response(address_txs_response):
            return []
        address_txs: list = []
        for tx in address_txs_response['result']['data']:
            if not cls.validator.validate_transaction(transaction=tx):
                continue
            address_txs.append(TransferTx(
                tx_hash=tx['digest'],
                from_address=cls._parse_from_address(transaction=tx),
                to_address=cls.parse_to_address(balance_changes=tx['balanceChanges']),
                value=cls.parse_amount(balance_changes=tx['balanceChanges']),
                block_height=int(tx['checkpoint']),
                date=parse_utc_timestamp_ms(s=tx.get('timestampMs')),
                confirmations=block_head - int(tx.get('checkpoint')) if block_head and tx.get('checkpoint') else None,
                memo=None,
                block_hash=None,
                success=True,
                symbol=cls.symbol,
            ))

        return address_txs

    @classmethod
    def parse_to_address(cls, balance_changes: dict) -> Optional[str]:
        for change in balance_changes:
            if change.get('coinType') in cls.validator.valid_coin_type and Decimal(change.get('amount')) > 0:
                return change.get('owner').get('AddressOwner')

        return None

    @classmethod
    def parse_amount(cls, balance_changes: dict) -> Optional[Decimal]:
        for change in balance_changes:
            if change.get('coinType') in cls.validator.valid_coin_type and Decimal(change.get('amount')) > 0:
                return BlockchainUtilsMixin.from_unit(int(change.get('amount')), cls.precision)

        return None

    @classmethod
    def _parse_from_address(cls, transaction: dict) -> str:
        return transaction.get('transaction').get('data').get('sender')

    @classmethod
    def parse_block_txs_response(cls, block_txs_response: list) -> List[TransferTx]:
        block_txs: List[TransferTx] = []
        for transaction in block_txs_response:
            if not cls.validator.validate_transaction(transaction=transaction):
                continue

            value = cls.parse_amount(transaction.get('balanceChanges'))

            if not value:
                continue
            block_txs.append(TransferTx(
                tx_hash=transaction.get('digest'),
                from_address=cls._parse_from_address(transaction),
                to_address=cls.parse_to_address(transaction.get('balanceChanges')),
                value=value,
                date=parse_utc_timestamp_ms(s=transaction.get('timestampMs')),
                block_height=int(transaction.get('checkpoint')),
                success=True,
                symbol=cls.symbol
            ))

        return block_txs


class BlastApiSuiApi(GeneralApi):
    parser = BlastSuiParser
    cache_key = 'sui'
    _base_url = 'https://sui-mainnet.public.blastapi.io'
    max_workers_for_get_block = 10

    @classmethod
    def get_headers(cls) -> dict:
        return {'Content-Type': 'application/json'}

    @classmethod
    def get_block_head_body(cls) -> str:
        return json.dumps({
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'sui_getLatestCheckpointSequenceNumber',
            'params': []
        })

    @classmethod
    def get_block_txs_body(cls, block_height: int) -> str:
        return json.dumps({
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'sui_getCheckpoints',
            'params': [str(block_height + 1), 1, True]
        })

    @classmethod
    def get_tx_details_body(cls, tx_hash: str) -> str:
        return json.dumps({
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'sui_getTransactionBlock',
            'params': [
                tx_hash,
                {
                    'showInput': True,
                    'showRawInput': False,
                    'showEffects': True,
                    'showEvents': False,
                    'showObjectChanges': False,
                    'showBalanceChanges': True,
                },
            ]
        })

    @classmethod
    def get_tx_details_batch_body(cls, tx_hashes: list) -> str:
        return json.dumps({
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'sui_multiGetTransactionBlocks',
            'params': [
                tx_hashes,
                {
                    'showInput': True,
                    'showRawInput': False,
                    'showEffects': True,
                    'showEvents': False,
                    'showObjectChanges': False,
                    'showBalanceChanges': True,
                }
            ]
        })

    @classmethod
    def get_address_txs_body(cls, address: str) -> str:
        return json.dumps({
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'suix_queryTransactionBlocks',
            'params': [{
                'filter': {
                    'ToAddress': address,
                },
                'options': {
                    'showInput': True,
                    'showRawInput': False,
                    'showEffects': True,
                    'showEvents': False,
                    'showObjectChanges': False,
                    'showBalanceChanges': True,
                }
            }]
        })
