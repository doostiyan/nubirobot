import json
import random
from typing import Dict, List, Optional
from django.conf import settings

from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin

from exchange.base.models import Currencies
from exchange.base.parsers import parse_iso_date


class DotPolarisResponseValidator(ResponseValidator):
    symbol = 'DOT'
    min_event_length = 3
    valid_transaction_functions = ['transferAllowDeath', 'transferKeepAlive', 'batch', 'batchAll', 'transferAll']
    valid_transaction_modules = ['balances', 'utility']
    valid_event_modules = ['balances']
    valid_event_functions = ['Transfer']
    currency = Currencies.dot
    precision = 10

    @classmethod
    def validate_general_response(cls, response: Dict[str, any]) -> bool:
        if not response or not isinstance(response, dict):
            return False
        if not response.get('data') or not isinstance(response.get('data'), dict):
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False
        if not address_txs_response.get('data').get('transfers') or not isinstance(
                address_txs_response.get('data').get('transfers'), list):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False
        if not tx_details_response.get('data').get('transfers') or not isinstance(
                tx_details_response.get('data').get('transfers'), list):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(block_head_response):
            return False
        block_head_data = block_head_response.get('data')
        if not block_head_data.get('latestBlock') or not isinstance(block_head_data.get('latestBlock'), dict):
            return False
        if block_head_data.get('latestBlock').get('blockNumber') is None or not isinstance(
                block_head_data.get('latestBlock').get('blockNumber'), int):
            return False
        return True

    @classmethod
    def validate_batch_block_txs_response(cls, batch_block_txs_response: dict) -> bool:
        if not cls.validate_general_response(batch_block_txs_response):
            return False
        if not batch_block_txs_response.get('data').get('blockRange') or not isinstance(
                batch_block_txs_response.get('data').get('blockRange'), list):
            return False
        return True

    @classmethod
    def validate_transfer(cls, transfer: Dict[str, any]) -> bool:
        if not any(transfer.get(field) for field in
                   ['extrinsicHash', 'module', 'function', 'blockNumber', 'isTransferEvent', 'attributes']):
            return False
        if not isinstance(transfer.get('module'), str) or not transfer.get('module') in cls.valid_event_modules:
            return False
        if not isinstance(transfer.get('function'), str) or not transfer.get('function') in cls.valid_event_functions:
            return False
        if not isinstance(transfer.get('extrinsicHash'), str):
            return False
        if not isinstance(transfer.get('blockNumber'), int):
            return False
        if not transfer.get('attributes') or not isinstance(transfer.get('attributes'), str):
            return False
        from_address, to_address, amount = json.loads(transfer.get('attributes'))
        if not from_address or not isinstance(from_address, str):
            return False
        if not to_address or not isinstance(to_address, str):
            return False
        if not amount or not isinstance(amount, str):
            return False
        return True

    @classmethod
    def validate_transaction(cls, transaction: dict) -> bool:
        if not transaction.get('extrinsicHash') or not isinstance(transaction.get('extrinsicHash'), str):
            return False
        if not transaction.get('module') or not isinstance(transaction.get('module'), str):
            return False
        if not transaction.get('module') in cls.valid_transaction_modules:
            return False
        if not transaction.get('function') or not isinstance(transaction.get('function'), str):
            return False
        if not transaction.get('function') in cls.valid_transaction_functions:
            return False
        if not transaction.get('isFinalized') or not isinstance(transaction.get('isFinalized'), bool):
            return False
        if not transaction.get('blockNumber') or not isinstance(transaction.get('blockNumber'), int):
            return False
        if not transaction.get('fromAddress') or not isinstance(transaction.get('fromAddress'), str):
            return False
        if not transaction.get('toAddress') or not isinstance(transaction.get('toAddress'), str):
            return False
        if transaction.get('fromAddress').casefold() == transaction.get('toAddress').casefold():
            return False
        if transaction.get('fee') is None or not isinstance(transaction.get('fee'), str):
            return False
        if not transaction.get('events') or not isinstance(transaction.get('events'), list):
            return False
        if len(transaction.get('events')) < cls.min_event_length:
            return False
        return True

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: dict) -> bool:
        if not block_txs_response.get('blockHash') or not isinstance(block_txs_response.get('blockHash'), str):
            return False
        if not block_txs_response.get('blockNumber') or not isinstance(block_txs_response.get('blockNumber'), int):
            return False
        if not block_txs_response.get('timestamp') or not isinstance(block_txs_response.get('timestamp'), str):
            return False
        if not block_txs_response.get('transfers') or not isinstance(block_txs_response.get('transfers'), list):
            return False
        return True


class DotPolarisResponseParser(ResponseParser):
    validator = DotPolarisResponseValidator
    symbol = 'DOT'
    currency = Currencies.dot
    precision = 10

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, any]) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response):
            return block_head_response.get('data').get('latestBlock').get('blockNumber')
        return 0

    @classmethod
    def check_transfer_with_event(cls, transfer_details: dict, event_details: dict) -> bool:
        if not transfer_details.get('tx_hash') == event_details.get('tx_hash'):
            return False
        if not transfer_details.get('to_address') == event_details.get('to_address'):
            return False
        if not transfer_details.get('from_address') == event_details.get('from_address'):
            return False
        return True

    @classmethod
    def parse_transfers(cls, transfers: list, block_head: int, block_hash: str, date: str):
        final_transfers: List[TransferTx] = []
        for transfer in transfers:
            if cls.validator.validate_transaction(transfer):
                transfer_tx_hash = transfer.get('extrinsicHash')
                transfer_to_address = transfer.get('toAddress')
                transfer_from_address = transfer.get('fromAddress')
                transfer_fee = BlockchainUtilsMixin.from_unit(int(transfer.get('fee')), cls.precision)
                block_height = transfer.get('blockNumber')
                if block_head:
                    confirmations = block_head - block_height
                    block_hash = None
                    date = None
                else:
                    confirmations = 0
                    block_hash = block_hash
                    date = date
                events = transfer.get('events')
                for event in events:
                    if cls.validator.validate_transfer(event):
                        event_from_address, event_to_address, event_amount = json.loads(event.get('attributes'))
                        event_amount = BlockchainUtilsMixin.from_unit(int(event_amount), cls.precision)
                        event_tx_hash = event.get('extrinsicHash')
                        transfer_details = {
                            'tx_hash': transfer_tx_hash,
                            'to_address': transfer_to_address,
                            'from_address': transfer_from_address
                        }
                        event_details = {
                            'tx_hash': event_tx_hash,
                            'from_address': event_from_address,
                            'to_address': event_to_address
                        }
                        if cls.check_transfer_with_event(transfer_details, event_details):
                            transfer = TransferTx(
                                tx_hash=transfer_tx_hash,
                                confirmations=confirmations,
                                from_address=transfer_from_address,
                                to_address=transfer_to_address,
                                value=event_amount,
                                block_height=block_height,
                                symbol=cls.symbol,
                                success=True,
                                tx_fee=transfer_fee,
                                block_hash=block_hash,
                                date=date
                            )
                            final_transfers.append(transfer)
                        else:
                            continue
                        break
        return final_transfers

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Dict[str, any], block_head: int) -> List[TransferTx]:
        transfers: List[TransferTx] = []
        if cls.validator.validate_tx_details_response(tx_details_response):
            transfers = cls.parse_transfers(tx_details_response.get('data').get('transfers'), block_head, '', '')
        return transfers

    @classmethod
    def parse_address_txs_response(cls, _: str, address_txs_response: Dict[str, any], block_head: int) -> \
            List[TransferTx]:
        transfers: List[TransferTx] = []
        if cls.validator.validate_address_txs_response(address_txs_response):
            transfers = cls.parse_transfers(address_txs_response.get('data').get('transfers'), block_head, '', '')
        return transfers

    @classmethod
    def parse_batch_block_txs_response(cls, batch_block_txs_response: Dict[str, any]) -> List[TransferTx]:
        total_transfers: List[TransferTx] = []
        if cls.validator.validate_batch_block_txs_response(batch_block_txs_response):
            for block in batch_block_txs_response.get('data').get('blockRange'):
                if cls.validator.validate_block_txs_response(block):
                    block_hash = block.get('blockHash')
                    date = parse_iso_date(block.get('timestamp').replace(' ', 'T') + 'Z')
                    block_transfers = cls.parse_transfers(block.get('transfers'), block_head=0, block_hash=block_hash,
                                                          date=date)
                    total_transfers.extend(block_transfers)
        return total_transfers


class DotPolarisApi(GeneralApi):
    parser = DotPolarisResponseParser
    cache_key = 'dot'
    symbol = 'DOT'
    USE_PROXY = False
    block_height_offset = 5
    SUPPORT_BATCH_GET_BLOCKS = True
    GET_BLOCK_ADDRESSES_MAX_NUM = 50
    _base_url = 'https://graphql.polkadot.polaristech.ir'
    supported_requests = {
        'get_address_txs': '',
        'get_block_head': '',
        'get_block_txs': '',
        'get_tx_details': '',
    }

    queries = {
        'get_block_head': """
                query GetLatestBlock {
                    latestBlock {
                         blockHash
                         blockNumber
                         timestamp
                    }
                }
            """,
        'get_tx_details': """
                query TransactionDetails($tx_hash: String!) {
                    transfers(extrinsicHash: $tx_hash)  {
                          extrinsicHash
                          module
                          function
                          isFinalized
                          blockNumber
                          fromAddress
                          toAddress
                          amount
                          fee
                          tip
                          events {
                            module
                            function
                            extrinsicHash
                            extrinsicIdx
                            blockNumber
                            isTransferEvent
                            attributes
                          }
                    }
                }
            """,
        'get_address_txs': """
                    query TransactionDetails($toAddress: String!, $limit: Int!, $skip: Int!) {
                        transfers(toAddress: $toAddress, limit: $limit, skip: $skip)  {
                              extrinsicHash
                              module
                              function
                              isFinalized
                              blockNumber
                              fromAddress
                              toAddress
                              amount
                              fee
                              tip
                              events {
                                module
                                function
                                extrinsicHash
                                extrinsicIdx
                                blockNumber
                                isTransferEvent
                                attributes
                              }
                        }
                    }
                """,
        'get_blocks': """
                query GetRangeofBlocks($from: BigInt!, $to: BigInt!) {
                    blockRange(sBlock: $from, lBlock: $to) {
                         blockHash
                         blockNumber
                         timestamp
                         transfers {
                              extrinsicHash
                              module
                              function
                              isFinalized
                              blockNumber
                              fromAddress
                              toAddress
                              amount
                              fee
                              tip
                              events {
                                module
                                function
                                extrinsicHash
                                extrinsicIdx
                                blockNumber
                                isTransferEvent
                                attributes
                              }
                         }
                    }
                }
            """
    }

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        return {
            'Content-Type': 'application/json',
            'X-API-KEY': cls.get_api_key()
        }

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice(settings.DOT_POLARIS_APIKEY)

    @classmethod
    def get_block_head_body(cls) -> Optional[str]:
        data = {
            'query': cls.queries.get('get_block_head'),
            'variables': {}
        }
        return json.dumps(data)

    @classmethod
    def get_tx_details_body(cls, tx_hash: str) -> str:
        data = {
            'query': cls.queries.get('get_tx_details'),
            'variables': {
                'tx_hash': tx_hash
            }
        }
        return json.dumps(data)

    @classmethod
    def get_address_txs_body(cls, address: str) -> str:
        data = {
            'query': cls.queries.get('get_address_txs'),
            'variables': {
                'toAddress': address,
                'limit': 20,
                'skip': 0,
            }
        }
        return json.dumps(data)

    @classmethod
    def get_blocks_txs_body(cls, from_block: int, to_block: int) -> str:
        data = {
            'query': cls.queries.get('get_blocks'),
            'variables': {
                'from': from_block,
                'to': to_block,
            }
        }
        return json.dumps(data)
