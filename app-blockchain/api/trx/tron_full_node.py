import json
from collections import defaultdict
from decimal import Decimal
from typing import Dict, Optional, Tuple, Union

import base58
from django.core.cache import cache

from exchange.base.models import Currencies
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.api.trx import create2_simulator
from exchange.blockchain.contracts_conf import TRC20_contract_currency, TRC20_contract_info
from exchange.blockchain.metrics import metric_set
from exchange.blockchain.utils import AddressNotExist, APIError, BlockchainUtilsMixin


def from_hex(address: str) -> str:
    return base58.b58encode_check(bytes.fromhex(address))


class TronFullNodeAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: tron
    API docs: https://developers.tron.network/reference#api-overview
    Explorer: Full Node
    :exception ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut
    """

    active = True

    symbol = 'TRX'
    cache_key = 'trx'
    _base_url = 'https://nodes6.nobitex1.ir/trx-fullnode'
    # http://52.53.189.99:8090
    # https://trx.getblock.io/1650135f-4f85-4b81-8aef-3cf710a04f1f/mainnet/
    # http://34.220.77.106:8090
    # http://3.225.171.164:8090
    # http://35.180.51.163:8090
    # https://go.getblock.io/7d0e9c9af0e04ba187ed6fbd4b04eef6
    # https://winter-divine-valley.tron-mainnet.quiknode.pro/0111a5be017c36993776529a1d329ebc290947a8
    rate_limit = 0
    PRECISION = 6
    max_items_per_page = None  # None for get_balance
    page_offset_step = None
    confirmed_num = None
    currency = Currencies.trx
    USE_PROXY = False
    min_valid_tx_amount = Decimal('0.001')
    withdraw_token_method_id = 'c0a797d8'  # noqa: S105
    withdraw_main_method_id = '268a6de5'
    create_child_with_token_method_id = 'ba35d0b5'  # noqa: S105
    create_child_with_main_method_id = '6878bad9'
    main_method_ids = ['6878bad9', '268a6de5']
    token_method_ids = ['c0a797d8', 'ba35d0b5']

    supported_requests = {
        'get_balance': '/wallet/getaccount',
        'trigger_contract': '/wallet/triggersmartcontract',
        'get_blocks': '/wallet/getblockbylimitnext',
        'get_now_block': '/wallet/getnowblock',
    }

    def get_name(self) -> str:
        return 'trx_full_node'

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

    def get_balance(self, address: str) -> Dict[int, Dict[str, any]]:
        self.validate_address(address)
        data = {'address': address, 'visible': True}
        headers = {'content-type': 'application/json'}
        response = self.request('get_balance', body=json.dumps(data), headers=headers)
        if response is None:
            raise APIError('[TronFullNode][Get Balance] response is None')

        if response.get('Error', False):
            raise AddressNotExist(response.get('Error'))

        balance = response.get('balance', 0)

        main_balance = self.from_unit(int(balance))
        # Ignore asset balance and trc20 balance other than USDT
        return {
            self.currency: {
                'symbol': self.symbol,
                'amount': main_balance,
                'address': address
            }
        }

    def get_token_balance(
            self,
            address: str,
            contracts_info: Optional[Dict[int, Dict[str, Union[int, str]]]] = None
    ) -> Dict[int, Dict[str, any]]:
        self.validate_address(address)
        if contracts_info is None:
            contracts_info = TRC20_contract_info.get(self.network)
        balances = {}
        for currency, contract_info in contracts_info.items():
            address_hex = self.to_hex(address)
            contract_address = contract_info.get('address')
            contract_decimals = contract_info.get('decimals')
            data = {
                'contract_address': self.to_hex(contract_address),
                'function_selector': 'balanceOf(address)',
                'parameter': address_hex.rjust(64, '0'),
                'owner_address': address_hex
            }
            headers = {'content-type': 'application/json'}
            response = self.request('trigger_contract', body=json.dumps(data), headers=headers)
            if response is None:
                raise APIError('[TronFullNode][Get Balance TRC20] response is None')
            result = response.get('result')
            if result.get('code'):
                message = bytes.fromhex(result.get('message')).decode('utf-8')
                raise APIError(f"[TronFullNode][Get Balance TRC20] {result.get('code')}: {message}")

            if not result.get('result'):
                raise APIError(f'[TronFullNode][Get Balance TRC20] result is not True: {json.dumps(response)}')

            constant_result = response.get('constant_result', [0])
            if not constant_result:
                constant_result = ['0']
            balance = int(constant_result[0], 16)
            balance = self.from_unit(int(balance), precision=contract_decimals)
            balances[currency] = {
                'amount': balance,
                'address': contract_address,
            }
        return balances

    def get_block_head(self) -> int:
        headers = {'content-type': 'application/json'}
        response = self.request('get_now_block', force_post=True, headers=headers)
        if not response:
            raise APIError('[TronFullNode][Get Now Block] response is None')
        return int(
            response.get('block_header', {}).get('raw_data', {}).get('number')) - 500

    def extract_data_from_transaction(self,
                                      tx_data: str,
                                      contract_address: str) -> Tuple[
        Optional[str], Optional[str], Optional[Union[int, Decimal]], Optional[int], Optional[str]]:
        if tx_data[:8] in self.token_method_ids:
            if tx_data[:8] == self.withdraw_token_method_id:
                from_address = self.from_hex(tx_data[8:72].lstrip('0').lower())
            else:
                salt = tx_data[8:72].lstrip('0')
                from_address = create2_simulator.generate_contract_addresses(contract_address, salt)
            token = self.from_hex(tx_data[72:136].lstrip('0').lower())
            currency = TRC20_contract_currency.get(self.network).get(token)
            if not currency:
                return None, None, None, None, None
            amount_raw = tx_data[136:200].lstrip('0').lower()
            contract_info = TRC20_contract_info.get(self.network).get(currency)
            amount = self.from_unit(int(amount_raw, 16), contract_info.get('decimals'))
            to_address = self.from_hex(tx_data[200:264].lstrip('0').lower())
            symbol = contract_info.get('symbol')
        else:
            if tx_data[:8] == self.withdraw_main_method_id:
                from_address = self.from_hex(tx_data[8:72].lstrip('0').lower())
            else:
                salt = tx_data[8:72].lstrip('0')
                from_address = create2_simulator.generate_contract_addresses(contract_address, salt)
            amount_raw = tx_data[72:136].lstrip('0').lower()
            amount = self.from_unit(int(amount_raw, 16))
            to_address = self.from_hex(tx_data[136:200].lstrip('0').lower())
            currency = Currencies.trx
            symbol = self.symbol

        return from_address, to_address, amount, currency, symbol

    def get_latest_block(self, after_block_number: Optional[int] = None, to_block_number: Optional[int] = None,
                         include_inputs: bool = False, include_info: bool = False) -> Tuple[
        Dict[str, set], Dict[str, dict], int]:
        """ Retrieve block from blockbook by trezor.io
        :return: Set of addresses output transactions with pay to public key hash
        in last block processed until the last block mined
        API Document: https://developers.tron.network/docs
        """
        headers = {'content-type': 'application/json'}
        mother_contract_address = 'TFdko4yMVrKZarYLkC8XKgjrRmhsu9D7iA'
        if not after_block_number:
            latest_block_height_processed = cache.get('latest_block_height_processed_trx')
            if latest_block_height_processed is None:
                response = self.request('get_now_block', force_post=True, headers=headers)
                if not response:
                    raise APIError('[TronFullNode][Get Now Block] response is None')
                latest_block_height_processed = int(
                    response.get('block_header', {}).get('raw_data', {}).get('number')) - 500
        else:
            latest_block_height_processed = after_block_number

        latest_block_height_mined = to_block_number if to_block_number else latest_block_height_processed + 100

        if latest_block_height_mined > latest_block_height_processed:
            min_height = latest_block_height_processed + 1
        else:
            min_height = latest_block_height_mined + 1
        max_height = latest_block_height_mined + 1
        max_height = min(max_height, min_height + 100)
        data = {
            'startNum': min_height,
            'endNum': max_height
        }
        blocks_info = self.request('get_blocks', body=json.dumps(data), headers=headers)
        if not blocks_info:
            raise APIError('[TronFullNode][Get Blocks] response is None')

        if not blocks_info.get('block'):
            return set(), None, 0

        blocks = blocks_info.get('block') or []
        if not blocks:
            return set(), None, 0
        # input_addresses ~ outgoing_txs and output_addresses ~ incoming_txs
        transactions_addresses = {'input_addresses': set(), 'output_addresses': set()}
        transactions_info = {'outgoing_txs': defaultdict(lambda: defaultdict(list)),
                             'incoming_txs': defaultdict(lambda: defaultdict(list))}
        for block in blocks:
            transactions = block.get('transactions') or []
            for tx_info in transactions:
                ret_status_info = tx_info.get('ret') or [{}]
                if ret_status_info[0].get('contractRet') != 'SUCCESS':
                    continue
                raw_data = tx_info.get('raw_data') or {}
                contract = raw_data.get('contract') or [{}]
                block_height = int(block.get('block_header', {}).get('raw_data', {}).get('number'))
                tx_type = contract[0].get('type')
                if tx_type == 'TriggerSmartContract':
                    tx_contract_info = contract[0].get('parameter', {}).get('value', {})
                    tx_data = tx_contract_info.get('data')
                    if not tx_data:
                        continue
                    contract_address = self.from_hex(tx_contract_info.get('contract_address'))
                    if tx_data[:8] != 'a9059cbb':
                        if (tx_data[:8] in (
                                self.token_method_ids + self.main_method_ids)
                                and contract_address == mother_contract_address):
                            from_address, to_address, amount, currency, symbol = self.extract_data_from_transaction(
                                tx_data,
                                contract_address)
                            if not currency:
                                continue
                        else:
                            continue
                    else:
                        try:
                            to_address = self.from_hex(tx_data[8:72].lstrip('0').lower())
                        except ValueError:
                            continue
                        currency = TRC20_contract_currency.get(self.network).get(contract_address)
                        if not currency:
                            continue
                        contract_info = TRC20_contract_info.get(self.network).get(currency)
                        from_address = self.from_hex(tx_contract_info.get('owner_address', ''))
                        amount_raw = tx_data[72:136] or '0'
                        symbol = contract_info.get('symbol')
                        try:
                            amount = self.from_unit(int(amount_raw, 16), contract_info.get('decimals'))
                        except ValueError:
                            continue

                elif tx_type == 'TransferContract':
                    try:
                        to_address = self.from_hex(contract[0].get('parameter', {}).get('value', {}).get('to_address'))
                        from_address = self.from_hex(
                            contract[0].get('parameter', {}).get('value', {}).get('owner_address'))
                        currency = Currencies.trx
                        symbol = self.symbol
                    except AttributeError:
                        continue
                    amount = self.from_unit(int(contract[0].get('parameter', {}).get('value', {}).get('amount')))
                    if amount < self.min_valid_tx_amount:
                        continue
                else:
                    continue
                if from_address in ['TM9RwJndZHmDVLSZcY6J76ci22AzPp2krj', 'TVCAuYMw5afP96y5Wep866AXVWZJRH8fdo']:
                    continue

                transactions_addresses['output_addresses'].add(to_address)
                if include_inputs:
                    transactions_addresses['input_addresses'].add(from_address)

                if include_info:
                    transactions_info['incoming_txs'][to_address][currency].append({
                        'tx_hash': tx_info.get('txID'),
                        'value': amount,
                        'symbol': symbol,
                        'block_height': block_height,
                        'contract_address': None
                    })

                    if include_inputs:
                        transactions_info['outgoing_txs'][from_address][currency].append({
                            'tx_hash': tx_info.get('txID'),
                            'value': amount,
                            'symbol': symbol,
                            'block_height': block_height,
                            'contract_address': None
                        })

        last_block_height = int(blocks[-1].get('block_header', {}).get('raw_data', {}).get('number'))
        metric_set(name='latest_block_processed', labels=[self.symbol.lower()], amount=last_block_height)
        cache.set('latest_block_height_processed_trx', last_block_height, 86400)
        return transactions_addresses, transactions_info, last_block_height
