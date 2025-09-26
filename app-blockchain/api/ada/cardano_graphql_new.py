import json
from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List, Optional

from exchange.base.models import Currencies
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.general.dtos import Balance, TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin


class CardanoGraphqlValidator(ResponseValidator):
    min_valid_tx_amount = Decimal(0)
    precision = 6

    @classmethod
    def validate_general_response(cls, response: Dict[str, Any]) -> bool:
        if not response:
            return False
        if response.get('errors'):
            return False
        if not response.get('data'):
            return False
        if not isinstance(response.get('data'), dict):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(block_head_response):
            return False
        if not block_head_response.get('data').get('cardano', {}).get('tip', {}).get('number'):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False
        if not tx_details_response.get('data').get('transactions'):
            return False
        if not isinstance(tx_details_response.get('data').get('transactions'), list):
            return False
        if not tx_details_response.get('data').get('cardano'):
            return False
        return True

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if not {'hash', 'inputs', 'outputs', 'block', 'fee', 'includedAt'}.issubset(
                transaction.keys()):
            return False
        if not transaction.get('block', {}).get('number'):
            return False
        if not cls._validate_input_output_keys(transaction.get('inputs')):
            return False
        if not cls._validate_input_output_keys(transaction.get('outputs')):
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: Dict[str, Any]) -> bool:
        if not cls.validate_tx_details_response(address_txs_response):
            return False
        return True

    @classmethod
    def validate_balances_response(cls, balances_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(balances_response):
            return False
        if not balances_response.get('data').get('paymentAddresses'):
            return False
        return False

    @classmethod
    def validate_batch_block_txs_response(cls, block_txs_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(block_txs_response):
            return False
        if not block_txs_response.get('data').get('blocks'):
            return False
        return True

    @classmethod
    def validate_block_tx_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if not transaction.get('hash'):
            return False
        if not transaction.get('inputs') or not isinstance(transaction.get('inputs'), list):
            return False
        if not transaction.get('outputs') or not isinstance(transaction.get('outputs'), list):
            return False
        if not cls._validate_input_output_keys(transaction.get('inputs')):
            return False
        if not cls._validate_input_output_keys(transaction.get('outputs')):
            return False
        return True

    @classmethod
    def _validate_input_output_keys(cls, values: list) -> bool:
        for input_output in values:
            if not isinstance(input_output, dict):
                return False
            if not input_output.get('address'):
                return False
            if not input_output.get('value'):
                return False
            value = input_output.get('value')
            if not (isinstance(value, int) or (isinstance(value, str) and value.isnumeric())):
                return False
            value = BlockchainUtilsMixin.from_unit(int(value), cls.precision)
            if value < cls.min_valid_tx_amount:
                return False
        return True


class CardanoGraphqlParser(ResponseParser):
    currency = Currencies.ada
    validator = CardanoGraphqlValidator
    precision = 6
    symbol = 'ADA'

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, Any]) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response):
            return block_head_response.get('data').get('cardano').get('tip').get('number')
        return None

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Dict[str, Any], block_head: int) -> List[TransferTx]:
        if not cls.validator.validate_tx_details_response(tx_details_response):
            return []

        txs = tx_details_response.get('data', {}).get('transactions')
        return cls._convert_tx_to_transfer_dto(block_head, txs)

    @classmethod
    def _parse_tx_details_transfer_tx(cls,
                                      address: str,
                                      value: Decimal,
                                      block_head: int,
                                      block_height: int,
                                      tx_hash: str,
                                      tx_fee: int,
                                      date: str,
                                      direction: str) -> TransferTx:
        if direction not in ['input', 'output']:
            raise ValueError("Please insert one of input/output as 'direction' argument")

        if direction == 'input':
            address = {'from_address': address, 'to_address': ''}
        elif direction == 'output':
            address = {'to_address': address, 'from_address': ''}
        return TransferTx(
            block_hash=None,
            block_height=block_height,
            confirmations=block_head - block_height,
            value=value,
            date=parse_iso_date(date),
            success=True,
            symbol=cls.symbol,
            tx_hash=tx_hash,
            tx_fee=BlockchainUtilsMixin.from_unit(int(tx_fee), precision=cls.precision),
            **address
        )

    @classmethod
    def parse_address_txs_response(cls,
                                   address: str,
                                   address_txs_response: Dict[str, Any],
                                   block_head: int) -> List[TransferTx]:
        if not cls.validator.validate_address_txs_response(address_txs_response):
            return []
        txs = address_txs_response.get('data', {}).get('transactions')
        return cls._convert_tx_to_transfer_dto(block_head, txs, address)

    @classmethod
    def parse_balances_response(cls, balances_response: Dict[str, Any]) -> List[Balance]:
        if not cls.validator.validate_balances_response(balances_response):
            return []
        # TODO: This method response has problem that should be fixed
        # TODO: This is useful links
        #  https://github.com/cardano-foundation/cardano-graphql/blob/master/packages/api-cardano-db-hasura/src/example_queries/paymentAddress/summary.graphql
        #  https://github.com/cardano-foundation/cardano-graphql/issues/869
        #  https://cardano-foundation.github.io/cardano-graphql/
        #  Below code has brought from old structure

        """
        balances = list()
        payments = balances_response.get('data').get('paymentAddresses')
        for address, payment in zip(balances_response, payments):
            balance = payment.get('summary', ).get('assetBalances')
            if len(balance) == 0:
                amount = Decimal(0)
            else:
                amount = balance[0].get('quantity')
            balances.append({
                self.currency: {
                    'address': payment.get('address'),
                    'balance': self.from_unit(int(amount))
                }
            })
        return balances
        """
        return []

    @classmethod
    def _convert_tx_to_transfer_dto(cls,
                                    block_head: int,
                                    txs: list,
                                    address: Optional[str] = None) -> List[TransferTx]:
        input_txs: List[TransferTx] = []
        output_txs: List[TransferTx] = []
        for tx in txs:
            if cls.validator.validate_transaction(tx):
                block_height = tx.get('block').get('number')
                tx_hash = tx.get('hash')
                tx_fee = tx.get('fee', 0)
                date = tx.get('includedAt')

                aggregated_inputs = cls._aggregate_values_with_same_address(tx.get('inputs'))
                aggregated_outputs = cls._aggregate_values_with_same_address(tx.get('outputs'))

                for input_address, input_value in aggregated_inputs.items():
                    if address and input_address != address:
                        continue

                    value = input_value
                    if aggregated_outputs.get(input_address):
                        value -= aggregated_outputs[input_address]
                        del aggregated_outputs[input_address]
                        if value == Decimal('0'):
                            continue
                    input_txs.append(cls._parse_tx_details_transfer_tx(input_address, value, block_head,
                                                                       block_height, tx_hash,
                                                                       tx_fee, date, 'input'))

                for output_address, output_value in aggregated_outputs.items():
                    if (address and output_address != address) or output_value == Decimal(0):
                        continue
                    output_txs.append(
                        cls._parse_tx_details_transfer_tx(output_address, output_value, block_head, block_height,
                                                          tx_hash, tx_fee, date,
                                                          'output'))
        return input_txs + output_txs

    @classmethod
    def parse_batch_block_txs_response(cls, batch_block_txs_response: Dict[str, Any]) -> List[TransferTx]:
        input_txs: List[TransferTx] = []
        output_txs: List[TransferTx] = []

        if not cls.validator.validate_batch_block_txs_response(batch_block_txs_response):
            return []
        for block_transactions in batch_block_txs_response.get('data').get('blocks'):
            block_hash = block_transactions.get('hash')
            block_height = block_transactions.get('number')
            transactions = block_transactions.get('transactions', [])
            for tx_info in transactions:
                if not cls.validator.validate_block_tx_transaction(tx_info):
                    continue
                tx_hash = tx_info.get('hash')

                aggregated_inputs = cls._aggregate_values_with_same_address(tx_info.get('inputs'))
                aggregated_outputs = cls._aggregate_values_with_same_address(tx_info.get('outputs'))

                for input_address, input_value in aggregated_inputs.items():

                    value = input_value

                    if aggregated_outputs.get(input_address):
                        value -= aggregated_outputs[input_address]
                        del aggregated_outputs[input_address]

                    value -= BlockchainUtilsMixin.from_unit(int(tx_info.get('fee', 0)), precision=cls.precision)

                    input_txs.append(
                        cls._parse_block_tx_to_transfer_dto(block_hash, block_height, tx_hash, input_address,
                                                            value, 'input'))

                for output_address, output_value in aggregated_outputs.items():
                    output_txs.append(
                        cls._parse_block_tx_to_transfer_dto(block_hash, block_height, tx_hash, output_address,
                                                            output_value, 'output'))
        return input_txs + output_txs

    @classmethod
    def _parse_block_tx_to_transfer_dto(cls,
                                        block_hash: str,
                                        block_height: int,
                                        tx_hash: str,
                                        address: str,
                                        value: Decimal,
                                        direction: str) -> TransferTx:
        if direction not in ['input', 'output']:
            raise ValueError("Please insert one of input/output as 'direction' argument")

        if direction == 'input':
            address = {'from_address': address, 'to_address': ''}
        elif direction == 'output':
            address = {'to_address': address, 'from_address': ''}
        return TransferTx(
            block_hash=block_hash,
            block_height=block_height,
            value=value,
            success=True,
            symbol=cls.symbol,
            tx_hash=tx_hash,
            **address
        )

    @classmethod
    def _aggregate_values_with_same_address(cls, data: List[dict]) -> dict:
        input_output_dict = defaultdict(int)
        for input_output in data:
            input_output_dict[input_output.get('address')] += BlockchainUtilsMixin.from_unit(
                int(input_output.get('value')), precision=cls.precision)
        return input_output_dict


class CardanoGraphqlApi(GeneralApi):
    """
        Cardano API explorer.

        supported coins: ada
        API docs: https://graphql.adatools.io/
        API docs2: https://iohk.zendesk.com/hc/en-us/articles/900000906566-Sample-cardano-graphql-queries
        Explorer: https://explorer.cardano.org/graphql/
        """

    symbol = 'ADA'
    cache_key = 'ada'
    currency = Currencies.ada
    parser = CardanoGraphqlParser
    SUPPORT_BATCH_GET_BLOCKS = True
    SUPPORT_GET_BALANCE_BATCH = True
    GET_TXS_TRANSACTION_LIMIT = 25
    # https://explorer.cardano.org/graphql/
    # https://graphql-api.mainnet.dandelion.link/graphql/
    # https://mainnet-graphql.adatools.io/graphql/mainnet/
    _base_url = 'https://nodes4.nobitex1.ir/ada/graphql/'
    testnet_url = 'https://graphql-testnet.adatools.io/'

    supported_requests = {
        'get_address_txs': '',
        'get_block_head': '',
        'get_block_txs': '',
        'get_balance': '',
        'get_tx_details': ''
    }

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        return {'Content-Type': 'application/json'}

    @classmethod
    def get_block_head_body(cls) -> str:
        query = """
                    query{
                      cardano{
                        tip{
                            number
                        }
                      }
                    }
                """
        data = {'query': query}
        return json.dumps(data)

    @classmethod
    def get_tx_details_body(cls, tx_hash: str) -> str:
        data = {
            'query': """
                        query get_tx($hash:Hash32Hex!){
                          transactions(where:{hash :{_eq:$hash}}){

                            fee
                            hash
                            inputs{
                              address
                              value
                            }
                            outputs{
                              address
                              value
                            }
                            block{
                              number
                            }
                            includedAt

                          }
                          cardano{
                            tip{
                              number
                            }
                          }
                        }
                    """,
            'variables': {
                'hash': tx_hash,
            }
        }
        return json.dumps(data)

    @classmethod
    def get_address_txs_body(cls, address: str) -> str:
        query = """
                    query getAddressTransactions($address: String!) {
                          transactions(
                            limit: %s
                            where: {
                                outputs: { address: { _eq: $address } }
                            }
                            order_by: { includedAt: desc }
                          ) {
                            block {
                              number
                            }
                            hash
                            fee
                            includedAt
                            inputs {
                              address
                              value
                            }
                            outputs {
                              address
                              value
                            }
                          }
                          cardano{
                            tip{
                              number
                            }
                          }
                    }
                """
        data = {
            'query': query % cls.GET_TXS_TRANSACTION_LIMIT,
            'variables': {
                'address': address
            }}
        return json.dumps(data)

    @classmethod
    def get_balances_body(cls, addresses: List[str]) -> str:
        query = """
                    query paymentAddressSummary(
                      $addresses: [String!]!
                    ) {
                      paymentAddresses (addresses: $addresses) {
                        summary{
                          assetBalances {
                            asset {
                              assetId
                              description
                              name
                            }
                            quantity
                          }
                        }
                      }
                    }
                """
        data = {
            'query': query,
            'variables': {
                'addresses': addresses
            }}
        return json.dumps(data)

    @classmethod
    def get_blocks_txs_body(cls, from_block: int, to_block: int) -> str:
        query = """
                query getBlockTxs($min_height: Int!, $max_height: Int!) {
                      blocks(where:  {_and: [{number: {_gte: $min_height}}, {number: {_lt: $max_height}}]}) {
                        hash,
                        number,
                        transactions {
                          hash
                          inputs {
                            address
                            value
                          }
                          outputs {
                            address
                            value
                          }
                          fee
                        }
                      }
                    }
                """
        data = {
            'query': query,
            'variables': {
                'min_height': from_block,
                'max_height': to_block + 1
            }}
        return json.dumps(data)
