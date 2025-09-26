import json
from decimal import Decimal
from typing import List, Optional

from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.api.general.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin


class PolarisSolValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.001')
    precision = 9

    @classmethod
    def validate_general_response(cls, response: dict) -> bool:
        if not response:
            return False
        if not response.get('data'):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: dict) -> bool:
        if not cls.validate_general_response(block_head_response):
            return False
        if not block_head_response.get('data').get('latestBlock'):
            return False
        if not block_head_response.get('data').get('latestBlock').get('slot'):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: dict) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False
        if (not tx_details_response.get('data').get('nativeTransfers') or
                not isinstance(tx_details_response.get('data').get('nativeTransfers'), list)):
            return False
        if not cls.validate_transaction(tx_details_response.get('data').get('nativeTransfers')[0]):
            return False
        return True

    @classmethod
    def validate_batch_block_txs_response(cls, batch_block_txs_response: dict) -> bool:
        if not cls.validate_general_response(batch_block_txs_response):
            return False
        if not batch_block_txs_response.get('data').get('blockRange'):
            return False
        return True

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: dict) -> bool:
        key2check = ['blockHash', 'blockHeight', 'blockTime', 'parentSlot', 'slot', 'tokenTransfers', 'nativeTransfers']
        for key in key2check:
            if block_txs_response.get(key) is None:
                return False
        if not isinstance(block_txs_response.get('tokenTransfers'), list):
            return False
        if not isinstance(block_txs_response.get('nativeTransfers'), list):
            return False
        return True

    @classmethod
    def validate_transaction(cls, transaction: dict) -> bool:
        if transaction.get('err') != '':
            return False
        if transaction.get('status') != 'Success':
            return False
        if not transaction.get('transactionHash'):
            return False
        if not (transaction.get('fromAddress') or transaction.get('toAddress')):
            return False
        if not transaction.get('amount'):
            return False
        if transaction.get('action') != 'transfer':
            return False
        if transaction.get('programId') != '11111111111111111111111111111111':
            return False
        if BlockchainUtilsMixin.from_unit(int(transaction.get('amount')),
                                          precision=cls.precision) < cls.min_valid_tx_amount:
            return False
        return True


class PolarisSolParser(ResponseParser):
    validator = PolarisSolValidator
    precision = 9
    symbol = 'SOL'
    currency = Currencies.sol

    @classmethod
    def parse_block_head_response(cls, block_head_response: dict) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response):
            return int(block_head_response.get('data').get('latestBlock').get('slot'))
        return None

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: dict, block_head: int) -> List[TransferTx]:
        if cls.validator.validate_tx_details_response(tx_details_response):
            transaction = tx_details_response.get('data').get('nativeTransfers')[0]
            block_height = transaction.get('slot')
            confirmations = block_head - block_height
            return [TransferTx(
                tx_hash=transaction.get('transactionHash'),
                from_address=transaction.get('fromAddress'),
                to_address=transaction.get('toAddress'),
                success=True,
                block_height=block_height,
                date=None,
                tx_fee=BlockchainUtilsMixin.from_unit(int(transaction.get('fee')), precision=cls.precision),
                memo=None,
                confirmations=confirmations,
                value=BlockchainUtilsMixin.from_unit(int(transaction.get('amount')), precision=cls.precision),
                symbol=cls.symbol,
                token=None,
                block_hash=None
            )]

        return []

    @classmethod
    def parse_batch_block_txs_response(cls, batch_block_txs_response: dict) -> List[TransferTx]:
        block_txs: List[TransferTx] = []
        if cls.validator.validate_batch_block_txs_response(batch_block_txs_response):
            for block in batch_block_txs_response.get('data').get('blockRange'):
                if cls.validator.validate_block_txs_response(block):
                    block_transfers = block.get('nativeTransfers')
                    for transfer in block_transfers:
                        if cls.validator.validate_transaction(transfer):
                            transfer_tx = TransferTx(
                                block_height=transfer.get('slot'),
                                block_hash=None,
                                tx_hash=transfer.get('transactionHash'),
                                date=None,
                                success=True,
                                confirmations=None,
                                from_address=transfer.get('fromAddress'),
                                to_address=transfer.get('toAddress'),
                                value=BlockchainUtilsMixin.from_unit(int(transfer.get('amount')),
                                                                     precision=cls.precision),
                                symbol=cls.symbol,
                                memo=None,
                                tx_fee=BlockchainUtilsMixin.from_unit(int(transfer.get('fee')),
                                                                      precision=cls.precision),
                                token=None,
                            )
                            block_txs.append(transfer_tx)
        return block_txs


class PolarisSolApi(GeneralApi):
    parser = PolarisSolParser
    symbol = 'SOL'
    cache_key = 'sol'
    SUPPORT_BATCH_GET_BLOCKS = True
    _base_url = 'https://graphql.solana.polareum.com'
    need_block_head_for_confirmation = True
    GET_BLOCK_ADDRESSES_MAX_NUM = 500
    block_height_offset = 1500
    timeout = 180

    supported_requests = {
        'get_block_head': '',
        'get_block_txs': ''
    }

    queries = {
        'get_block_head': """
            query Query {
              latestBlock {
                blockHash
                blockHeight
                blockTime
                parentSlot
                previousBlockHash
                slot
              }
            }

        """,
        'get_tx_details': """
        query TransactionDetails {
                    nativeTransfers(
                    txid: $tx_hash
                    ) {
                    action
                    amount
                    err
                    fee
                    fromAddress
                    programId
                    signatures
                    slot
                    status
                    toAddress
                    transactionHash
                    }
                    }
        """,
        'get_blocks': """
           query GetRangeofBlocks  {
          blockRange(sSlot: $from, lSlot: $to) {
            blockHash
            blockHeight
            blockTime
            parentSlot
            previousBlockHash
            slot
            tokenTransfers {
              account
              action
              amount
              authority
              err
              fee
              fromAddress
              mint
              owner
              program
              programId
              rentSysvar
              signatures
              slot
              status
              toAddress
              transactionHash
              decimal
            }
            nativeTransfers {
              action
              amount
              err
              fee
              fromAddress
              programId
              signatures
              slot
              status
              toAddress
              transactionHash
    }
  }
}
        """
    }

    @classmethod
    def get_api_key(cls) -> str:
        return settings.POLARIS_API_KEY

    @classmethod
    def get_headers(cls) -> dict:
        return {
            'Content-Type': 'application/json',
            'X-API-KEY': cls.get_api_key()
        }

    @classmethod
    def get_block_head_body(cls) -> str:
        data = {
            'query': cls.queries.get('get_block_head'),
            'variables': {}
        }
        return json.dumps(data)

    @classmethod
    def get_tx_details_body(cls, tx_hash: str) -> str:
        data = {
            'query': cls.queries.get('get_tx_details').replace('$tx_hash', f'"{tx_hash}"'),
            'variables': {}
        }
        return json.dumps(data)

    @classmethod
    def get_blocks_txs_body(cls, from_block: int, to_block: int) -> str:
        data = {
            'query': cls.queries.get('get_blocks').replace('$from', f'{from_block}').replace('$to', f'{to_block}'),
            'variables': {}
        }
        return json.dumps(data)
