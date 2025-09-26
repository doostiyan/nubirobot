import json
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from exchange.base.models import Currencies
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.general.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.api.ton.utils import TonAddressConvertor
from exchange.blockchain.contracts_conf import ton_contract_currency, ton_contract_info
from exchange.blockchain.utils import BlockchainUtilsMixin


class PolarisValidatorResponse(ResponseValidator):
    min_valid_tx_amount = Decimal('0.00')

    @classmethod
    def validate_general_response(cls, response: Any) -> bool:
        if not response:
            return False
        return True

    @classmethod
    def validate_batch_token_tx_details_response(cls, batch_token_tx_details_response: list) -> bool:
        if not cls.validate_general_response(batch_token_tx_details_response):
            return False
        if not isinstance(batch_token_tx_details_response, list):
            return False
        return True

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if not transaction or not isinstance(transaction, dict):
            return False
        if not transaction.get('transferReceipts') or not isinstance(transaction['transferReceipts'], list):
            return False
        return True

    @classmethod
    def validate_token_transfer(cls, transfer: Dict[str, Any], contract_info: Dict[str, Union[str, int]]) -> bool:
        if not transfer or not isinstance(transfer, dict):
            return False
        key2check = ['transactionHash', 'rootHash', 'aborted', 'source', 'destination', 'fee', 'tokenAmount',
                     'timestamp', 'tokenMaster']
        for key in key2check:
            if transfer.get(key) is None:
                return False
        if transfer.get('aborted') is True:
            return False
        if contract_info.get('address') != transfer.get('tokenMaster'):
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: list) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False
        if not isinstance(address_txs_response, list):
            return False
        return True


class PolarisParserResponse(ResponseParser):
    validator = PolarisValidatorResponse
    symbol = 'TON'
    average_block_time = 5
    precision = 9
    currency = Currencies.ton

    @classmethod
    def parse_token_txs_response(cls,
                                 _: str,
                                 token_txs_response: List[Dict[str, Any]],
                                 __: Optional[int],
                                 contract_info: Dict[str, Union[str, int]],
                                 ___: str = '') -> List[TransferTx]:
        transfers: List[TransferTx] = []
        if cls.validator.validate_address_txs_response(token_txs_response):
            transfers = cls.parse_token_transactions(token_txs_response, contract_info)
        return transfers

    @classmethod
    def parse_batch_token_tx_details_response(cls,
                                              batch_token_tx_details_response: List[Dict[str, Any]],
                                              contract_info: Dict[str, Union[str, int]],
                                              _: Optional[int]) -> List[TransferTx]:
        transfers: List[TransferTx] = []
        if cls.validator.validate_batch_token_tx_details_response(batch_token_tx_details_response):
            for tx in batch_token_tx_details_response:
                if cls.validator.validate_transaction(tx):
                    transfers.extend(cls.parse_token_transactions(tx.get('transferReceipts'), contract_info))
        return transfers

    @classmethod
    def parse_token_transactions(cls,
                                 response: List[Dict[str, Any]],
                                 contract_info: Dict[str, Union[str, int]]) -> List[TransferTx]:
        transfers = []
        for transfer in response:
            if cls.validator.validate_token_transfer(transfer, contract_info):
                transfers.append(
                    TransferTx(
                        tx_hash=transfer.get('rootHash'),
                        success=True,
                        from_address=cls.convert_address(transfer.get('source')),
                        to_address=cls.convert_address(transfer.get('destination')),
                        value=Decimal(str(transfer.get('tokenAmount'))),
                        symbol=contract_info.get('symbol'),
                        confirmations=cls.calculate_tx_confirmations(transfer.get('timestamp')),
                        block_height=0,
                        block_hash=None,
                        date=parse_iso_date(transfer.get('timestamp') + 'Z'),
                        memo=transfer.get('comment', None),
                        tx_fee=BlockchainUtilsMixin.from_unit(
                            int(transfer.get('fee')), precision=contract_info.get('decimals')),
                        token=transfer.get('tokenMaster'),
                    )
                )
        return transfers

    @classmethod
    def contract_info_list(cls) -> Dict[int, Dict[str, Union[str, int]]]:
        return ton_contract_info.get(cls.network_mode)

    @classmethod
    def contract_currency_list(cls) -> Dict[str, int]:
        return ton_contract_currency.get(cls.network_mode)

    @classmethod
    def convert_address(cls, address: str) -> str:
        return TonAddressConvertor.convert_hex_to_bounceable(address[2:].lower())

    @classmethod
    def calculate_tx_confirmations(cls, tx_date: str) -> int:
        from datetime import datetime
        tx_datetime = datetime.strptime(tx_date, '%Y-%m-%dT%H:%M:%S').timestamp()
        current_time_in_s = time.time()
        diff = current_time_in_s - tx_datetime
        return int(diff / cls.average_block_time)


class PolarisTonApi(GeneralApi):
    parser = PolarisParserResponse
    symbol = 'TON'
    cache_key = 'ton'
    _base_url = 'https://indexer.ton.polareum.com/api'
    need_block_head_for_confirmation = False
    SUPPORT_GET_BATCH_TOKEN_TX_DETAILS = True
    GET_TX_DETAILS_MAX_NUM = 100
    supported_requests = {
        'get_batch_token_tx_details': '/batch-transfer-summary',
        'get_token_txs': '/token-transfers?BlockchainRef=Ton&NetworkRef=Mainnet&TokenMaster={contract_address}'
                         '&Address={address}&Pagination=1'
    }

    @classmethod
    def get_api_key(cls) -> str:
        return '6638643e-692a-4368-9910-cab1ca5f865a'

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        return {
            'X-API-Key': cls.get_api_key(),
            'Content-Type': 'application/json'

        }

    @classmethod
    def get_batch_token_tx_details_body(cls, hashes: List[str], contract_info: Dict[str, Union[str, int]]) -> str:
        data = {
            'TransactionHash': hashes,
            'NetworkRef': 'Mainnet',
            'BlockchainRef': 'Ton',
            'TokenMaster': contract_info.get('address')
        }
        return json.dumps(data)
