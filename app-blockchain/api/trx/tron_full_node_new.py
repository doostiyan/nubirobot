import json
from decimal import Decimal
from typing import Dict, List, Tuple, Union

import base58

from exchange.base.models import Currencies
from exchange.base.parsers import parse_timestamp_microseconds
from exchange.blockchain.api.general.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.api.trx import create2_simulator
from exchange.blockchain.contracts_conf import TRC20_contract_currency, TRC20_contract_info
from exchange.blockchain.utils import BlockchainUtilsMixin


class TronFullNodeValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.001')

    @classmethod
    def validate_general_response(cls, response: Dict[str, any]) -> bool:
        if not response:
            return False
        if response.get('Error'):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(block_head_response):
            return False
        if not block_head_response.get('block_header', {}).get('raw_data', {}).get('number'):
            return False
        return True

    @classmethod
    def validate_balance_response(cls, balance_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(balance_response):
            return False
        if not balance_response.get('balance') or not balance_response.get('address'):
            return False
        if not isinstance(balance_response.get('balance'), int):
            return False
        return True

    @classmethod
    def validate_token_balance_response(cls, token_balance_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(token_balance_response):
            return False
        if not token_balance_response.get('result'):
            return False
        if token_balance_response.get('result').get('code'):
            return False
        if not token_balance_response.get('result').get('result'):
            return False
        if not token_balance_response.get('constant_result'):
            return False
        return True

    @classmethod
    def validate_batch_block_txs_response(cls, batch_block_txs_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(batch_block_txs_response):
            return False
        if not batch_block_txs_response.get('block'):
            return False
        return True

    @classmethod
    def validate_block_txs_raw_response(cls, block_txs_raw_response: Dict[str, any]) -> bool:
        if not block_txs_raw_response or not isinstance(block_txs_raw_response, dict):
            return False
        if (not block_txs_raw_response.get('transactions') or
                not isinstance(block_txs_raw_response.get('transactions'), list)):
            return False
        return True

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(block_txs_response):
            return False
        if not block_txs_response.get('transactions'):
            return False
        if not block_txs_response.get('block_header'):
            return False
        if not block_txs_response.get('block_header').get('raw_data'):
            return False
        if not block_txs_response.get('block_header').get('raw_data').get('number'):
            return False
        return True

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, any]) -> bool:
        if not transaction.get('txID'):
            return False
        if not transaction.get('ret') or not isinstance(transaction.get('ret'), list):
            return False
        if transaction.get('ret')[0].get('contractRet') != 'SUCCESS':
            return False
        if not transaction.get('raw_data'):
            return False
        if not transaction.get('raw_data').get('contract'):
            return False
        if not isinstance(transaction.get('raw_data').get('contract'), list):
            return False
        if not transaction.get('raw_data').get('contract')[0].get('type'):
            return False
        return True

    @classmethod
    def validate_trigger_smart_contract(cls, contract: List[Dict[str, any]]) -> bool:
        if not contract or not isinstance(contract, list):
            return False
        if not contract[0].get('parameter'):
            return False
        if not contract[0].get('parameter').get('value'):
            return False
        if not contract[0].get('parameter').get('value').get('data'):
            return False
        if not contract[0].get('parameter').get('value').get('contract_address'):
            return False
        return True

    @classmethod
    def validate_transfer_contract(cls, contract: List[Dict[str, any]]) -> bool:
        if not contract or not isinstance(contract, list):
            return False
        if not contract[0].get('parameter'):
            return False
        if not contract[0].get('parameter').get('value'):
            return False
        if not contract[0].get('parameter').get('value'):
            return False
        if not contract[0].get('parameter').get('value').get('owner_address'):
            return False
        if not contract[0].get('parameter').get('value').get('to_address'):
            return False
        if not contract[0].get('parameter').get('value').get('amount'):
            return False
        value = BlockchainUtilsMixin.from_unit(int(contract[0].get('parameter').get('value').get('amount')),
                                               TronFullNodeParser.precision)
        if value < cls.min_valid_tx_amount:
            return False
        return True


class TronFullNodeParser(ResponseParser):
    validator = TronFullNodeValidator
    symbol = 'TRX'
    currency = Currencies.trx
    precision = 6
    withdraw_token_method_id = 'c0a797d8' # noqa: S105
    withdraw_main_method_id = '268a6de5'
    create_child_with_token_method_id = 'ba35d0b5' # noqa: S105
    create_child_with_main_method_id = '6878bad9'
    main_method_ids = ['6878bad9', '268a6de5']
    token_method_ids = ['c0a797d8', 'ba35d0b5']
    mother_contract_address = 'TFdko4yMVrKZarYLkC8XKgjrRmhsu9D7iA'

    @classmethod
    def parse_block_head_response(cls, block_head_response: dict) -> int:
        if not cls.validator.validate_block_head_response(block_head_response):
            return 0
        return int(block_head_response.get('block_header').get('raw_data').get('number')) - 500

    @classmethod
    def parse_balance_response(cls, balance_response: dict) -> Union[Decimal, int]:
        if not cls.validator.validate_balance_response(balance_response):
            return Decimal('0')
        return BlockchainUtilsMixin.from_unit(int(balance_response.get('balance')), cls.precision)

    @classmethod
    def parse_token_balance_response(cls, balance_response: dict, contract_info: Dict[str, Union[str, int]]) -> Decimal:
        if not cls.validator.validate_token_balance_response(balance_response):
            return Decimal('0')
        constant_result = balance_response.get('constant_result', [0])
        balance = int(constant_result[0], 16)
        return BlockchainUtilsMixin.from_unit(int(balance), precision=contract_info.get('decimals'))

    @classmethod
    def parse_batch_block_txs_response(cls, batch_block_txs_response: dict) -> List[TransferTx]:
        if not cls.validator.validate_batch_block_txs_response(batch_block_txs_response):
            return []
        transfers: List[TransferTx] = []
        for block in batch_block_txs_response.get('block'):
            if not cls.validator.validate_block_txs_response(block):
                continue
            for transaction in block.get('transactions'):
                if not cls.validator.validate_transaction(transaction):
                    continue
                block_height = int(block.get('block_header').get('raw_data').get('number'))
                contract = transaction.get('raw_data').get('contract')
                tx_type = contract[0].get('type')
                if tx_type == 'TriggerSmartContract' and cls.validator.validate_trigger_smart_contract(contract):
                    tx_contract_info = contract[0].get('parameter').get('value')
                    tx_data = tx_contract_info.get('data')
                    contract_address = cls.from_hex(tx_contract_info.get('contract_address'))
                    if tx_data[:8] != 'a9059cbb':
                        if (tx_data[:8] in (cls.token_method_ids + cls.main_method_ids)
                                and contract_address == cls.mother_contract_address):
                            data = cls.extract_data_from_transaction(tx_data, contract_address)
                            from_address, to_address, value, currency, symbol = data
                            if not currency:
                                continue
                        else:
                            continue
                    else:
                        try:
                            currency = TRC20_contract_currency.get(cls.network_mode).get(contract_address)
                            if not currency:
                                continue
                            contract_info = TRC20_contract_info.get(cls.network_mode).get(currency)
                            from_address = cls.from_hex(tx_contract_info.get('owner_address', ''))
                            to_address = cls.from_hex(tx_data[8:72].lstrip('0').lower())
                            symbol = contract_info.get('symbol')
                            value = BlockchainUtilsMixin.from_unit(int(tx_data[72:136] or '0', 16),
                                                                   contract_info.get('decimals'))
                        except ValueError:
                            continue
                elif tx_type == 'TransferContract' and cls.validator.validate_transfer_contract(contract):
                    from_address = cls.from_hex(contract[0].get('parameter').get('value').get('owner_address'))
                    symbol = cls.symbol
                    to_address = cls.from_hex(contract[0].get('parameter').get('value').get('to_address'))
                    value = BlockchainUtilsMixin.from_unit(
                        int(contract[0].get('parameter').get('value').get('amount')), cls.precision)
                    if value < Decimal('0.001'):
                        continue
                else:
                    continue
                if from_address in ['TM9RwJndZHmDVLSZcY6J76ci22AzPp2krj', 'TVCAuYMw5afP96y5Wep866AXVWZJRH8fdo']:
                    continue
                date = None
                if transaction.get('raw_data').get('timestamp'):
                    date = parse_timestamp_microseconds(int(transaction.get('raw_data').get('timestamp')/1000))
                transfers.append(TransferTx(
                    tx_hash=transaction.get('txID'),
                    success=True,
                    from_address=from_address,
                    to_address=to_address,
                    value=value,
                    symbol=symbol,
                    confirmations=0,
                    block_height=block_height,
                    block_hash=None,
                    date=date,
                    memo=None,
                    tx_fee=None,
                    token=None
                ))
        return transfers

    @classmethod
    def to_hex(cls, address: str) -> str:
        return base58.b58decode_check(address).hex().upper()

    @classmethod
    def from_hex(cls, address: str) -> str:
        if len(address) < 40:  # noqa: PLR2004
            address = address.zfill(40)
        if len(address) == 40:  # noqa: PLR2004
            address = '41' + address
        return base58.b58encode_check(bytes.fromhex(address)).decode()

    @classmethod
    def extract_data_from_transaction(cls,
                                      tx_data: str,
                                      contract_address: str) -> Tuple[str, str, Union[int, Decimal], int, str]:
        if tx_data[:8] in cls.token_method_ids:
            if tx_data[:8] == cls.withdraw_token_method_id:
                from_address = cls.from_hex(tx_data[8:72].lstrip('0').lower())
            else:
                salt = tx_data[8:72].lstrip('0')
                from_address = create2_simulator.generate_contract_addresses(contract_address, salt)
            token = cls.from_hex(tx_data[72:136].lstrip('0').lower())
            currency = TRC20_contract_currency.get(cls.network_mode).get(token)
            if not currency:
                return None, None, None, None, None
            amount_raw = tx_data[136:200].lstrip('0').lower()
            contract_info = TRC20_contract_info.get(cls.network_mode).get(currency)
            amount = BlockchainUtilsMixin.from_unit(int(amount_raw, 16), contract_info.get('decimals'))
            to_address = cls.from_hex(tx_data[200:264].lstrip('0').lower())
            symbol = contract_info.get('symbol')
        else:
            if tx_data[:8] == cls.withdraw_main_method_id:
                from_address = cls.from_hex(tx_data[8:72].lstrip('0').lower())
            else:
                salt = tx_data[8:72].lstrip('0')
                from_address = create2_simulator.generate_contract_addresses(contract_address, salt)
            amount_raw = tx_data[72:136].lstrip('0').lower()
            amount = BlockchainUtilsMixin.from_unit(int(amount_raw, 16), cls.precision)
            to_address = cls.from_hex(tx_data[136:200].lstrip('0').lower())
            currency = Currencies.trx
            symbol = cls.symbol

        return from_address, to_address, amount, currency, symbol


class TronFullNodeAPI(GeneralApi):
    # API docs: https://developers.tron.network/reference#api-overview
    parser = TronFullNodeParser
    symbol = 'TRX'
    cache_key = 'trx'
    _base_url = 'https://nodes6.nobitex1.ir/trx-fullnode'
    # http://52.53.189.99:8090
    # http://34.220.77.106:8090
    # http://3.225.171.164:8090
    # http://35.180.51.163:8090
    # https://go.getblock.io/7d0e9c9af0e04ba187ed6fbd4b04eef6
    # https://trx.getblock.io/1650135f-4f85-4b81-8aef-3cf710a04f1f/mainnet/
    # https://winter-divine-valley.tron-mainnet.quiknode.pro/0111a5be017c36993776529a1d329ebc290947a8
    SUPPORT_BATCH_GET_BLOCKS = True
    supported_requests = {
        'get_balance': '/wallet/getaccount',
        'get_token_balance': '/wallet/triggersmartcontract',
        'get_blocks_txs': '/wallet/getblockbylimitnext',
        'get_block_head': '/wallet/getnowblock',
    }

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        return {'content-type': 'application/json'}

    @classmethod
    def get_block_head(cls) -> any:
        return cls.request(request_method='get_block_head', body=cls.get_block_head_body(), force_post=True,
                           headers=cls.get_headers(), apikey=cls.get_api_key(), timeout=cls.timeout)

    @classmethod
    def get_balance_body(cls, address: str) -> str:
        data = {
            'address': address,
            'visible': True
        }
        return json.dumps(data)

    @classmethod
    def get_token_balance_body(cls, address: str, contract_info: dict) -> str:
        address_hex = cls.parser.to_hex(address)
        data = {
            'contract_address': cls.parser.to_hex(contract_info.get('address')),
            'function_selector': 'balanceOf(address)',
            'parameter': address_hex.rjust(64, '0'),
            'owner_address': address_hex
        }
        return json.dumps(data)

    @classmethod
    def get_blocks_txs_body(cls, from_block: int, to_block: int) -> str:
        data = {
            'startNum': from_block - 1,
            'endNum': to_block
        }
        return json.dumps(data)
