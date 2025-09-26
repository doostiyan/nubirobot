import json
from typing import Dict, List, Optional

import base58

from exchange.base.calendar import ir_now
from exchange.base.parsers import parse_utc_timestamp_ms
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin


def to_hex(address: str) -> str:
    return base58.b58decode_check(address).hex().upper()


def from_hex(address: str) -> str:
    if len(address) < 40: # noqa: PLR2004
        address = address.zfill(40)
    if len(address) == 40: # noqa: PLR2004
        address = '41' + address
    return base58.b58encode_check(bytes.fromhex(address)).decode()


class TronSolidityNodeAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: tron
    API docs: https://developers.tron.network/reference#api-overview
    Explorer: Full Node
    :exception ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut
    """
    active = True

    symbol = 'TRX'
    _base_url = 'http://47.90.247.237:8091'
    rate_limit = 0
    PRECISION = 6
    max_items_per_page = 50  # 50 for transactions history
    page_offset_step = None
    confirmed_num = None

    supported_requests = {
        'get_txs_from': '/walletextension/gettransactionsfromthis',
        'get_txs_to': '/walletextension/gettransactionstothis',
    }

    def get_name(self) -> str:
        return 'solidity_node_api'

    def get_balance(self, _: str) -> list:
        return []

    def get_txs(self, address: str, offset: int = 0, limit: int = 50, unconfirmed: bool = False, tx_type: str = 'all',  # noqa: ARG002
                contract_info: Optional[dict] = None) -> List[Dict[str, any]]:
        """ Get account transaction from Solidity node

        :param contract_info: contract you want to
        :param offset: Fingerprint in previous transaction result
        :param limit: Limit in the number of transaction in each response
        :param unconfirmed: False|True. True if you want to return unconfirmed transactions too.
        :param tx_type: normal|trc20|all. If you set all return both normal and trc20 transactions.
        :return: List of transactions
        """
        self.validate_address(address)
        txs = self._get_txs(address, offset, limit)

        result = []
        for tx in txs:
            parsed_tx = self.parse_tx(tx, address, tx_type, contract_info)
            if parsed_tx is not None:
                result.append(parsed_tx)
        return result

    def _get_txs(self, address: str, offset: int = 0, limit: int = 50) -> any:

        data = {
            'account': {
                'address': to_hex(address)
            },
            'limit': limit,
            'offset': offset,
        }
        headers = {'content-type': 'application/json'}
        response = self.request('get_txs_to', body=json.dumps(data), headers=headers)
        if not response:
            raise APIError('[TronSolidityNode][Get Transactions] response is None')

        return response.get('transaction')

    @classmethod
    def equal_address(cls, address_1: str, address_2: str) -> bool:
        return from_hex(address_1).lower() == from_hex(address_2).lower()

    def parse_tx(self, tx: dict, address: str, tx_type: str = 'all', contract_info: Optional[dict] = None) -> Optional[
        Dict[str, any]]:
        if contract_info is None:
            contract_info = {
                '41a614f803b6fd780986a42c78ec9c7f77e6ded13c': {
                    'symbol': 'USDT',
                    'precision': 6
                }
            }
        tx_result = tx.get('ret', [{}])
        if tx_result is None or tx_result == [] or tx_result[0].get('contractRet') != 'SUCCESS':
            return None

        contracts = tx.get('raw_data', {}).get('contract', [{}])
        if contracts is None or contracts == []:
            contracts = [{}]
        main_contract_detail = contracts[0]
        main_contract_params = main_contract_detail.get('parameter', {})
        main_contract_value = main_contract_params.get('value', {})

        contract_data = None
        contract_address = None

        tx_tp = main_contract_detail.get('type')
        direction = 'incoming'
        # TODO: Support TransferAssetContract and CreateSmartContract
        if tx_tp == 'TriggerSmartContract' and tx_type in ['trc20', 'all']:
            tx_data = main_contract_value.get('data')
            if tx_data[:8] != 'a9059cbb':
                return None
            to_address = tx_data[8:72].lstrip('0').lower()
            from_address = main_contract_value.get('owner_address', '').lower()
            if not self.equal_address(to_address, to_hex(address)):
                if not self.equal_address(from_address, to_hex(address)):
                    return None
                direction = 'outgoing'
            contract_addr = main_contract_value.get('contract_address', '').lower()
            ct_info = contract_info.get(contract_addr)
            if ct_info is None:
                return None
            symbol = ct_info.get('symbol')
            amount = self.from_unit(int(tx_data[72:136], 16), ct_info.get('precision'))
            contract_address = from_hex(contract_addr)
            contract_data = ct_info
        elif tx_tp == 'TransferContract' and tx_type in ['normal', 'all']:
            to_address = main_contract_value.get('to_address').lower()
            from_address = main_contract_value.get('owner_address').lower()
            if not self.equal_address(to_address, to_hex(address)):
                if not self.equal_address(from_address, to_hex(address)):
                    return None
                direction = 'outgoing'
            symbol = self.symbol
            amount = self.from_unit(int(main_contract_value.get('amount')))
        else:
            return None

        try:
            date = parse_utc_timestamp_ms(int(tx.get('raw_data', {}).get('timestamp')))
        except TypeError:
            date = parse_utc_timestamp_ms(int(tx.get('raw_data', {}).get('expiration')))
        except OverflowError:
            date = ir_now()

        return {
            'symbol': symbol,
            'date': date,
            'from_address': from_hex(from_address),
            'to_address': from_hex(to_address),
            'contract_address': contract_address,
            'amount': amount,
            'hash': tx.get('txID'),
            'confirmations': None,
            'confirmed': None,
            'type': tx_type,
            'kind': 'transaction',
            'direction': direction,
            'contract_data': contract_data,
            'raw': tx
        }
