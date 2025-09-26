import datetime
import json
import random
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.conf import settings

from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class BitQueryCardanoValidator(ResponseValidator):
    @classmethod
    def validate_general_response(cls, response: Dict[str, Any]) -> bool:
        if not response:
            return False
        if response.get('errors'):
            return False
        if not response.get('data'):
            return False
        if not response.get('data').get('cardano'):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(block_head_response):
            return False
        if not block_head_response.get('data').get('cardano').get('blocks'):
            return False
        if not isinstance(block_head_response.get('data').get('cardano').get('blocks'), list):
            return False
        if not block_head_response.get('data').get('cardano').get('blocks')[0].get('height'):
            return False
        return True

    @classmethod
    def validate_balance_response(cls, balance_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(balance_response):
            return False
        if not balance_response.get('data').get('cardano').get('address'):
            return False
        if not isinstance(balance_response.get('data').get('cardano').get('address'), list):
            return False
        if not balance_response.get('data').get('cardano').get('address')[0].get('balance'):
            return False
        if not isinstance(balance_response.get('data').get('cardano').get('address')[0].get('balance'), list):
            return False
        if not balance_response.get('data').get('cardano').get('address')[0].get('balance')[0].get('currency'):
            return False
        if not balance_response.get('data').get('cardano').get('address')[0].get('balance')[0].get('value'):
            return False
        if (balance_response.get('data').get('cardano').get('address')[0].get('balance')[0].get('currency')
                .get('symbol') != 'ADA'):
            return False
        return True

    @classmethod
    def validate_general_txs_response(cls, response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(response):
            return False
        if (not response.get('data').get('cardano').get('outputs') and
                not response.get('data').get('cardano').get('inputs')):
            return False
        if not response.get('data').get('cardano').get('blocks'):
            return False
        return True

    @classmethod
    def validate_batch_tx_details_response(cls, tx_details_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_txs_response(tx_details_response):
            return False
        if not tx_details_response.get('data').get('cardano').get('transactions'):
            return False
        if not tx_details_response.get('data').get('cardano').get('inputs'):
            return False
        if not tx_details_response.get('data').get('cardano').get('outputs'):
            return False
        if not tx_details_response.get('data').get('cardano').get('blocks'):
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: Dict[str, Any]) -> bool:
        return cls.validate_general_txs_response(address_txs_response)

    @classmethod
    def validate_batch_block_txs_response(cls, batch_block_txs_response: Dict[str, Any]) -> bool:
        return cls.validate_general_txs_response(batch_block_txs_response)

    @classmethod
    def validate_utxo_address_txs(cls, input_output_utxo: Dict[str, Any]) -> bool:
        if not isinstance(input_output_utxo, dict):
            return False
        if not input_output_utxo.get('transaction'):
            return False
        if not input_output_utxo.get('block'):
            return False
        if not input_output_utxo.get('inputAddress') and not input_output_utxo.get('outputAddress'):
            return False
        if not input_output_utxo.get('value'):
            return False
        return True

    @classmethod
    def validate_input_output_utxo(cls, input_output_utxo: Dict[str, Any]) -> bool:
        if not cls.validate_utxo_address_txs(input_output_utxo):
            return False
        if not input_output_utxo.get('currency'):
            return False
        if input_output_utxo.get('currency').get('symbol') != 'ADA':
            return False
        return True


class BitQueryCardanoParser(ResponseParser):
    validator = BitQueryCardanoValidator
    precision = 6
    currency = Currencies.ada
    symbol = 'ADA'

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, Any]) -> Decimal:
        if not cls.validator.validate_balance_response(balance_response):
            return Decimal(0)
        return Decimal(
            str(balance_response.get('data').get('cardano').get('address')[0].get('balance')[0].get('value')))

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, Any]) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response):
            return block_head_response.get('data').get('cardano').get('blocks')[0].get('height')
        return None

    @classmethod
    def parse_batch_tx_details_response(cls,
                                        tx_details_response: Dict[str, Any],
                                        block_head: Optional[int]) -> List[TransferTx]:
        if not cls.validator.validate_batch_tx_details_response(tx_details_response):
            return []
        return cls.parse_general_txs_response(tx_details_response, block_head)

    @classmethod
    def parse_address_txs_response(cls,
                                   _: str,
                                   address_txs_response: Dict[str, Any],
                                   block_head: Optional[int]) -> List[TransferTx]:
        if not cls.validator.validate_address_txs_response(address_txs_response):
            return []
        return cls.parse_general_txs_response(address_txs_response, block_head)

    @classmethod
    def parse_batch_block_txs_response(cls, batch_block_txs_response: Dict[str, Any]) -> List[TransferTx]:
        if not cls.validator.validate_batch_block_txs_response(batch_block_txs_response):
            return []
        return cls.parse_general_txs_response(batch_block_txs_response, None)

    @classmethod
    def parse_general_txs_response(cls, response: Dict[str, Any], block_head: Optional[int]) -> List[TransferTx]:
        if block_head is None:
            block_head = response.get('data').get('cardano').get('blocks')[0].get('height')
        transfers: List[TransferTx] = []
        input_addresses = []
        output_addresses = []
        for input_ in response.get('data').get('cardano').get('inputs'):
            if not cls.validator.validate_utxo_address_txs(input_):
                continue
            tx_hash = input_.get('transaction').get('hash')
            from_address = input_.get('inputAddress').get('address')
            new_transfer = True
            if from_address in input_addresses:
                for transfer in transfers:
                    if transfer.from_address == from_address and transfer.tx_hash == tx_hash:
                        transfer.value += Decimal(str(input_.get('value')))
                        new_transfer = False
            if new_transfer:
                transfers.append(cls.make_transfer(input_, block_head, is_input=True))
                input_addresses.append(input_.get('inputAddress').get('address'))

        for output_ in response.get('data').get('cardano').get('outputs'):
            if not cls.validator.validate_utxo_address_txs(output_):
                continue
            tx_hash = output_.get('transaction').get('hash')
            output_address = output_.get('outputAddress').get('address')
            new_transfer = True
            if output_address in input_addresses:
                for transfer in transfers:
                    if transfer.from_address == output_address and transfer.tx_hash == tx_hash:
                        transfer.value -= Decimal(str(output_.get('value')))
                        new_transfer = False
            elif output_address in output_addresses:
                for transfer in transfers:
                    if transfer.to_address == output_address and transfer.tx_hash == tx_hash:
                        transfer.value += Decimal(str(output_.get('value')))
                        new_transfer = False
            if new_transfer:
                transfers.append(cls.make_transfer(output_, block_head, is_input=False))
                output_addresses.append(output_address)
        return transfers

    @classmethod
    def make_transfer(cls, utxo: Dict[str, Any], block_head: int, is_input: bool) -> TransferTx:
        address = utxo.get('inputAddress').get('address') if is_input else utxo.get('outputAddress').get('address')
        return TransferTx(
            block_height=utxo.get('block').get('height'),
            block_hash=None,
            tx_hash=utxo.get('transaction').get('hash'),
            date=parse_iso_date(utxo.get('block').get('timestamp').get('time')),
            success=True,
            confirmations=block_head - utxo.get('block').get('height'),
            from_address=address if is_input else '',
            to_address=address if not is_input else '',
            value=Decimal(str(utxo.get('value'))),
            symbol=cls.symbol,
            memo=None,
            tx_fee=None,
            token=None,
        )


class BitQueryCardanoApi(GeneralApi):
    parser = BitQueryCardanoParser
    _base_url = 'https://graphql.bitquery.io/'
    cache_key = 'ada'
    symbol = 'ADA'
    rate_limit = 6
    block_height_offset = 0
    TRANSACTION_DETAILS_BATCH = True
    SUPPORT_BATCH_GET_BLOCKS = True
    supported_requests = {
        'get_balance': '',
        'get_block_head': '',
        'get_tx_details': '',
        'get_address_txs': '',
        'get_block_txs': ''
    }

    queries = {
        'get_blocks': """
            query getBlockTxs($min_height: Int!, $max_height: Int!, $from: ISO8601DateTime) {
              cardano(network: cardano) {
                inputs(height: {between: [$min_height, $max_height]}, currency: {is: "ADA"}) {
                  transaction {
                    hash
                  }
                  value
                  inputAddress {
                    address
                  }
                  block {
                    height
                    timestamp {
                      time(format: "%Y-%m-%dT%H:%M:%SZ")
                    }
                  }
                }
                outputs(height: {between: [$min_height, $max_height]}, currency: {is: "ADA"}) {
                  transaction {
                    hash
                  }
                  value
                  outputAddress {
                    address
                  }
                  block {
                    height
                    timestamp {
                      time(format: "%Y-%m-%dT%H:%M:%SZ")
                    }
                  }
                }
                blocks(options: {desc: "height", limit: 1}, date: {since: $from}) {
                  height
                }
              }
            }
        """,
        'get_address_txs': """
            query ($address: String!, $from: ISO8601DateTime) {
              cardano(network: cardano) {
                outputs(
                  outputAddress: {is: $address}
                  options: {desc: ["block.height"]}
                  currency: {is: "ADA"}
                  date: {after: $from}
                ) {
                  block {
                    height
                    timestamp {
                      time(format: "%Y-%m-%dT%H:%M:%SZ")
                    }
                  }
                  transaction {
                    hash
                  }
                  outputAddress {
                    address
                  }
                  value
                }
                inputs(
                  inputAddress: {is: $address}
                  options: {desc: ["block.height"]}
                  currency: {is: "ADA"}
                  date: {after: $from}
                ) {
                  block {
                    height
                    timestamp {
                      time(format: "%Y-%m-%dT%H:%M:%SZ")
                    }
                  }
                  transaction {
                    hash
                  }
                  inputAddress {
                    address
                  }
                  value
                }
                blocks(options: {desc: "height", limit: 1}, date: {since: $from}) {
                  height
                }
              }
            }
        """,
        'get_balance': """
            query ($address: String!) {
              cardano(network: cardano)  {
                address(address: {is: $address}) {
                  balance {
                    currency {
                      address
                      symbol
                      tokenType
                    }
                    value
                  }
                }
              }
            }
        """,
        'get_block_head': """
            query ($from: ISO8601DateTime) {
              cardano(network: cardano) {
                blocks(
                  options: {desc: "height", limit: 1}
                  date: {since: $from}
                ) {
                  height
                }
              }
            }
        """,
        'get_tx_details': """
            query ($network: CardanoNetwork!, $hashes: [String!], $limit: Int!, $offset: Int!,$from: ISO8601DateTime) {
                cardano(network: $network) {
                    blocks(options: {desc: "height", limit: 1}, date: {since: $from}) {
                        height
                    }
                    transactions(txHash: {in: $hashes}) {
                        block {
                            height
                            timestamp {
                            time(format: "%Y-%m-%dT%H:%M:%SZ")
                            }
                        }
                        index
                        hash
                        feeValue
                        includedAt {
                            time(format: "%Y-%m-%dT%H:%M:%SZ")
                        }
                    }
                    outputs(
                    txHash: {in: $hashes}
                    options: {asc: "outputIndex", limit: $limit, offset: $offset}
                    currency: {is: "ADA"}
                    ) {
                        outputIndex
                        transaction{
                            hash
                        }
                        block {
                            height
                            timestamp {
                              time(format: "%Y-%m-%dT%H:%M:%SZ")
                            }
                        }
                        outputAddress {
                            address
                        }
                        value
                        currency {
                            symbol
                        }
                    }
                    inputs(
                    txHash: {in: $hashes}
                    options: {asc: "inputIndex", limit: $limit, offset: $offset}
                    currency: {is: "ADA"}
                    ) {
                        inputIndex
                        transaction{
                            hash
                        }
                        block {
                            height
                            timestamp {
                              time(format: "%Y-%m-%dT%H:%M:%SZ")
                            }
                        }
                        inputAddress {
                            address
                            annotation
                        }
                        value
                        currency {
                            symbol
                        }
                    }
                }
            }
        """
    }

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice(settings.BITQUERY_API_KEY)

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        return {
            'Content-Type': 'application/json',
            'X-API-KEY': cls.get_api_key()
        }

    @classmethod
    def get_block_head_body(cls) -> str:
        data = {
            'query': cls.queries.get('get_block_head'),
            'variables': {
                'from': datetime.datetime.utcnow().strftime('%Y-%m-%d')
            }
        }
        return json.dumps(data)

    @classmethod
    def get_tx_details_batch_body(cls, tx_hashes: List[str]) -> str:
        data = {
            'query': cls.queries.get('get_tx_details'),
            'variables': {
                'network': 'cardano',
                'hashes': tx_hashes,
                'limit': 10,
                'offset': 0,
                'from': datetime.datetime.utcnow().strftime('%Y-%m-%d'),
            }
        }
        return json.dumps(data)

    @classmethod
    def get_balance_body(cls, address: str) -> str:
        data = {
            'query': cls.queries.get('get_balance'),
            'variables': {
                'network': 'cardano',
                'address': address,
                'limit': 10,
                'offset': 0,
                'from': datetime.datetime.utcnow().strftime('%Y-%m-%d'),
            }
        }
        return json.dumps(data)

    @classmethod
    def get_address_txs_body(cls, address: str) -> str:
        data = {
            'query': cls.queries.get('get_address_txs'),
            'variables': {
                'address': address,
                'from': (datetime.datetime.utcnow() - datetime.timedelta(days=3)).strftime('%Y-%m-%d')
            }
        }
        return json.dumps(data)

    @classmethod
    def get_blocks_txs_body(cls, from_block: int, to_block: int) -> str:
        data = {
            'query': cls.queries.get('get_blocks'),
            'variables': {
                'min_height': from_block,
                'max_height': to_block,
                'from': datetime.datetime.utcnow().strftime('%Y-%m-%d')
            }
        }
        return json.dumps(data)
