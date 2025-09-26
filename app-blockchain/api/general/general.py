from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, NoReturn, Optional, Tuple, Union

from django.conf import settings

from exchange.blockchain.api.general.dtos.dtos import (
    Balance,
    NewBalancesV2,
    SelectedCurrenciesBalancesRequest,
    TransferTx,
)
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.blockchain.utils import APIError, RateLimitError, Service


class ResponseValidator:
    min_valid_tx_amount = Decimal(0)
    invalid_from_addresses_for_ETH_like = ['0x70Fd2842096f451150c5748a30e39b64e35A3CdF',  # noqa: N815
                                           '0x491fe5F4724e642C90372B0B95b60c4aC8d13F1c',
                                           '0xB256caa23992e461E277CfA44a2FD72E2d6d2344',
                                           '0x06cC26db08674CbD9FF4d52444712E23cA3d046d',
                                           '0x4752B9bD4E73E2f52323E18137F0E66CDDF3f6C9']

    @classmethod
    def validate_general_response(cls, response: any) -> bool:
        return False

    @classmethod
    def validate_balance_response(cls, balance_response: Union[dict, int]) -> bool:
        return False

    @classmethod
    def validate_balances_response(cls, balances_response: float) -> bool:
        return False

    @classmethod
    def validate_token_balances_response(cls, token_balances_response: dict) -> bool:
        return False

    @classmethod
    def validate_token_balance_response(cls, token_balance_response: Union[dict, int]) -> bool:
        return False

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: dict) -> bool:
        return False

    @classmethod
    def validate_tx_receipt_response(cls, tx_receipt_response: dict) -> bool:
        return False

    @classmethod
    def validate_address_tx_receipt_transaction(cls, address_tx_receipt_transaction: dict) -> bool:
        return False

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: dict) -> bool:
        return False

    @classmethod
    def validate_block_txs_raw_response(cls, block_txs_raw_response: dict) -> bool:
        return True

    @classmethod
    def validate_batch_block_txs_response(cls, batch_block_txs_response: dict) -> bool:
        return False

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: dict) -> bool:
        return False

    @classmethod
    def validate_block_head_response(cls, block_head_response: dict) -> bool:
        return False

    @classmethod
    def validate_transaction(cls, transaction: dict) -> bool:
        return False

    @classmethod
    def validate_token_transaction(cls, transaction: dict, contract_info: dict, direction: str = '') -> bool:
        return False

    @classmethod
    def validate_tx_details_transaction(cls, transaction: dict) -> bool:
        return False

    @classmethod
    def validate_batch_tx_details_response(cls, batch_tx_details_response: dict) -> bool:
        return False

    @classmethod
    def validate_token_tx_details_transaction(cls, transaction: dict) -> bool:
        return False

    @classmethod
    def validate_batch_token_tx_details_response(cls, batch_token_tx_details_response: dict) -> bool:
        return False

    @classmethod
    def validate_address_tx_transaction(cls, transaction: dict) -> bool:
        return False

    @classmethod
    def validate_block_tx_transaction(cls, transaction: dict) -> bool:
        return False

    @classmethod
    def validate_transfer(cls, transfer: dict) -> bool:
        return False

    @classmethod
    def validate_token_transfer(cls, transfer: dict, contract_info: dict) -> bool:
        return False

    @classmethod
    def validate_token_txs_response(cls, token_txs_response: dict) -> bool:
        return False


class ResponseParser:
    validator = ResponseValidator
    symbol = ''
    currency = None
    precision = None
    network_mode = 'mainnet'

    @classmethod
    def parse_balance_response(cls, balance_response: any) -> Decimal:
        return balance_response

    @classmethod
    def parse_balances_response(cls, balances_response: any) -> List[Balance]:
        return balances_response

    @classmethod
    def parse_token_balance_response(cls, balance_response: any, contract_info: Dict[str, Union[str, int]]) -> Decimal:
        return balance_response

    @classmethod
    def parse_token_balances_response(cls, token_balances_response: any) -> List[Balance]:
        return token_balances_response

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: any, block_head: int) -> List[TransferTx]:
        return tx_details_response

    @classmethod
    def parse_batch_tx_details_response(cls, batch_tx_details_response: any, block_head: int) -> List[TransferTx]:
        return batch_tx_details_response

    @classmethod
    def parse_token_tx_details_response(cls, token_tx_details_response: any, block_head: int) -> List[TransferTx]:
        return token_tx_details_response

    @classmethod
    def parse_batch_token_tx_details_response(cls,
                                              batch_token_tx_details_response: any,
                                              contract_info: dict,
                                              block_head: int) -> List[TransferTx]:
        return batch_token_tx_details_response

    @classmethod
    def parse_tx_receipt_response(cls, tx_receipt_response: dict) -> bool:
        return False

    @classmethod
    def parse_address_txs_receipt(cls, address_txs_receipt: dict, block_head: int) -> List[TransferTx]:
        raise NotImplementedError

    @classmethod
    def parse_token_txs_receipt(cls, token_txs_receipt: dict, contract_info: dict, block_head: int) -> List[TransferTx]:
        raise NotImplementedError

    @classmethod
    def parse_block_txs_response(cls, block_txs_response: any) -> List[TransferTx]:
        return block_txs_response

    @classmethod
    def parse_batch_block_txs_response(cls, batch_block_txs_response: any) -> List[TransferTx]:
        return batch_block_txs_response

    @classmethod
    def parse_address_txs_response(cls, address: str, address_txs_response: any, block_head: int) -> List[TransferTx]:
        return address

    @classmethod
    def parse_token_txs_response(cls,
                                 address: str,
                                 token_txs_response: any,
                                 block_head: int,
                                 contract_info: dict,
                                 direction: str = '') -> List[TransferTx]:
        return token_txs_response

    @classmethod
    def parse_block_head_response(cls, block_head_response: any) -> str:
        return block_head_response

    @classmethod
    def contract_currency_list(cls) -> Dict[str, int]:
        return {}

    @classmethod
    def contract_info_list(cls) -> Dict[int, Dict[str, Union[str, int]]]:
        return {}

    @classmethod
    def get_currency_by_contract(cls, contract_address: str) -> Tuple[Optional[int], Optional[str]]:
        if cls.contract_currency_list().get(contract_address):
            return cls.contract_currency_list().get(contract_address), None
        if CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(contract_address, {}).get('destination_currency'):
            return CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(contract_address, {}).get(
                'destination_currency'), contract_address
        return None, None

    @classmethod
    def get_currency_info_by_contract(cls,
                                      currency: int,
                                      contract_address: str) -> Optional[Dict[str, Union[int, str]]]:
        if contract_address:
            return CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(contract_address, {}).get('info')
        if currency:
            return cls.contract_info_list().get(currency)
        return None

    @classmethod
    def calculate_pages_from_block_response(cls, block_txs_response: any) -> int:
        return block_txs_response

    @classmethod
    def convert_address(cls, address: str) -> str:
        return address


class GeneralApi(Service):
    need_block_head_for_confirmation = True
    need_transaction_receipt = False
    NEED_ADDRESS_TRANSACTION_RECEIPT = False
    NEED_TOKEN_TRANSACTION_RECEIPT = False
    parser = ResponseParser
    cache_key = ''
    USE_PROXY = False
    TRANSACTIONS_LIMIT = 50
    GET_BALANCES_MAX_ADDRESS_NUM = 1000
    GET_BLOCK_ADDRESSES_MAX_NUM = 100
    GET_TX_DETAILS_MAX_NUM = 200
    SUPPORT_BATCH_GET_BLOCKS = False
    SUPPORT_GET_BALANCE_BATCH = False
    SUPPORT_GET_TOKEN_BALANCE_BATCH = False
    SUPPORT_GET_BATCH_TOKEN_TX_DETAILS = False
    BALANCES_NOT_INCLUDE_ADDRESS = False
    TRANSACTION_DETAILS_BATCH = False
    instance = None
    block_height_offset = 0
    timeout = 30
    SUPPORT_PAGING = False
    max_workers_for_get_block = 1

    @classmethod
    def get_instance(cls, *args: any, **kwargs: any) -> 'GeneralApi':
        if cls.instance is None or cls.instance.__class__ != cls:
            cls.instance = cls()
        return cls.instance

    @classmethod
    def get_headers(cls) -> Optional[dict]:
        pass

    @classmethod
    def get_api_key(cls) -> Optional[str]:
        pass

    @classmethod
    def get_all_currencies_balances(cls, addresses: List[str]) -> List[NewBalancesV2]:
        pass

    @classmethod
    def get_selected_currencies_balances(cls,
                                         user_token_pairs: List[SelectedCurrenciesBalancesRequest]
                                         ) -> List[NewBalancesV2]:
        pass

    @classmethod
    def get_balance(cls, address: str) -> Any:
        return cls.request(request_method='get_balance', body=cls.get_balance_body(address),
                           headers=cls.get_headers(), address=address, apikey=cls.get_api_key())

    @classmethod
    def get_balance_body(cls, address: str) -> Optional[str]:
        pass

    @classmethod
    def get_balances(cls, addresses: List[str]) -> Any:
        separator = ','
        formatted_addresses = separator.join(addresses)
        return cls.request(request_method='get_balances', body=cls.get_balances_body(addresses),
                           headers=cls.get_headers(), addresses=formatted_addresses, apikey=cls.get_api_key())

    @classmethod
    def get_balances_body(cls, addresses: List[str]) -> Optional[str]:
        pass

    @classmethod
    def get_token_balance(cls, address: str, contract_info: Dict[str, Union[str, int]]) -> Any:
        return cls.request(request_method='get_token_balance',
                           body=cls.get_token_balance_body(address, contract_info),
                           headers=cls.get_headers(), contract_address=contract_info.get('address'),
                           address=address, apikey=cls.get_api_key())

    @classmethod
    def get_token_balance_body(cls, address: str, contract_info: Dict[str, Union[str, int]]) -> Optional[str]:
        pass

    @classmethod
    def get_token_balances(cls, addresses: List[str]) -> Any:
        separator = ','
        formatted_addresses = separator.join(addresses)
        return cls.request(request_method='get_token_balances',
                           body=cls.get_token_balances_body(addresses),
                           headers=cls.get_headers(), addresses=formatted_addresses,
                           apikey=cls.get_api_key())

    @classmethod
    def get_token_balances_body(cls, addresses: List[str]) -> Optional[str]:
        pass

    @classmethod
    def get_tx_details(cls, tx_hash: str) -> Any:
        return cls.request(request_method='get_tx_details', body=cls.get_tx_details_body(tx_hash),
                           headers=cls.get_headers(), tx_hash=tx_hash, apikey=cls.get_api_key(),
                           timeout=cls.timeout)

    @classmethod
    def get_tx_details_batch(cls, tx_hashes: List[str]) -> Any:
        return cls.request(request_method='get_batch_tx_details', body=cls.get_tx_details_batch_body(tx_hashes),
                           headers=cls.get_headers(), tx_hashes=tx_hashes, apikey=cls.get_api_key())

    @classmethod
    def get_token_tx_details(cls, tx_hash: str) -> Any:
        return cls.request(request_method='get_token_tx_details', body=cls.get_token_tx_details_body(tx_hash),
                           headers=cls.get_headers(), tx_hash=tx_hash, apikey=cls.get_api_key(),
                           timeout=cls.timeout)

    @classmethod
    def get_batch_token_tx_details(cls, hashes: List[str], contract_info: Dict[str, Union[str, int]]) -> Any:
        return cls.request(request_method='get_batch_token_tx_details', headers=cls.get_headers(),
                           body=cls.get_batch_token_tx_details_body(hashes, contract_info),
                           hashes=hashes, apikey=cls.get_api_key(), timeout=cls.timeout)

    @classmethod
    def get_batch_token_tx_details_body(cls,
                                        hashes: List[str],
                                        contract_info: Dict[str, Union[str, int]]) -> Optional[str]:
        pass

    @classmethod
    def get_tx_details_body(cls, tx_hash: str) -> Optional[str]:
        pass

    @classmethod
    def get_tx_details_batch_body(cls, tx_hashes: List[str]) -> Optional[str]:
        pass

    @classmethod
    def get_token_tx_details_body(cls, tx_hash: str) -> Optional[str]:
        pass

    @classmethod
    def get_tx_receipt(cls, tx_hash: str) -> Any:
        return cls.request(request_method='get_tx_receipt', body=cls.get_tx_receipt_body(tx_hash),
                           headers=cls.get_headers(), tx_hash=tx_hash, apikey=cls.get_api_key())

    @classmethod
    def get_address_txs_receipt(cls, tx_hash: str) -> Any:
        return cls.request(request_method='get_address_tx_receipt', body=cls.get_address_txs_receipt_body(tx_hash),
                           headers=cls.get_headers(), tx_hash=tx_hash, apikey=cls.get_api_key())

    @classmethod
    def get_token_txs_receipt(cls, tx_hash: str) -> Any:
        return cls.request(request_method='get_token_tx_receipt', body=cls.get_token_txs_receipt_body(tx_hash),
                           headers=cls.get_headers(), tx_hash=tx_hash, apikey=cls.get_api_key())

    @classmethod
    def get_address_txs_receipt_body(cls, tx_hash: str) -> Optional[str]:
        raise NotImplementedError

    @classmethod
    def get_token_txs_receipt_body(cls, tx_hash: str) -> Optional[str]:
        raise NotImplementedError

    @classmethod
    def get_tx_receipt_body(cls, tx_hash: str) -> Optional[str]:
        pass

    @classmethod
    def get_address_txs(cls, address: str, **kwargs: Any) -> Any:
        return cls.request(request_method='get_address_txs', body=cls.get_address_txs_body(address),
                           headers=cls.get_headers(), address=address, apikey=cls.get_api_key(),
                           timeout=cls.timeout)

    @classmethod
    def get_address_txs_body(cls, address: str) -> Optional[str]:
        pass

    @classmethod
    def get_token_txs(cls, address: str, contract_info: Dict[str, Union[str, int]], direction: str = '',
                      start_date: Optional[int] = None, end_date: Optional[int] = None) -> Any:
        if start_date and end_date:
            return cls.get_token_txs_time(address, contract_info, start_date, end_date)
        return cls.request(request_method='get_token_txs', body=cls.get_token_txs_body(address, contract_info),
                           headers=cls.get_headers(), address=address,
                           contract_address=contract_info.get('address'),
                           apikey=cls.get_api_key(), timeout=cls.timeout)

    @classmethod
    def get_token_txs_time(cls, address: str, contract_info: Dict[str, Union[str, int]], start_date: Optional[int],
                           end_date: Optional[int], direction: str = '') -> NoReturn:
        raise NotImplementedError

    @classmethod
    def get_token_txs_body(cls, address: str, contract_info: Dict[str, Union[str, int]]) -> Optional[str]:
        pass

    @classmethod
    def get_block_txs(cls, block_height: int, page: Optional[int] = None) -> Any:
        return cls.request(request_method='get_block_txs', body=cls.get_block_txs_body(block_height),
                           headers=cls.get_headers(), height=block_height, apikey=cls.get_api_key(), timeout=60)

    @classmethod
    def get_block_txs_body(cls, block_height: int) -> Optional[str]:
        pass

    @classmethod
    def get_batch_block_txs(cls, from_block: int, to_block: int) -> Any:
        return cls.request(request_method='get_blocks_txs',
                           body=cls.get_blocks_txs_body(from_block, to_block),
                           headers=cls.get_headers(),
                           from_block=from_block,
                           to_block=to_block, timeout=cls.timeout)

    @classmethod
    def get_blocks_txs_body(cls, from_block: int, to_block: int) -> Optional[str]:
        pass

    @classmethod
    def get_block_head(cls) -> Any:
        return cls.request(request_method='get_block_head', body=cls.get_block_head_body(),
                           headers=cls.get_headers(), apikey=cls.get_api_key(), timeout=cls.timeout)

    @classmethod
    def get_block_head_body(cls) -> Optional[str]:
        pass

    @classmethod
    def request(cls, request_method: str, with_rate_limit: bool = True,
                body: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None,
                timeout: int = 30, proxies: Optional[Dict[str, str]] = None,
                force_post: bool = False, **params: Any) -> Dict[str, Any]:
        try:
            if proxies is None and cls.USE_PROXY:
                proxies = settings.DEFAULT_PROXY
            if cls.get_instance().backoff > datetime.now():
                diff = (cls.get_instance().backoff - datetime.now()).total_seconds()
                raise RateLimitError(f'Remaining {diff} seconds of backoff')
            return super(GeneralApi, cls.get_instance()).request(
                request_method=request_method, with_rate_limit=with_rate_limit,
                body=body, headers=headers, timeout=timeout, proxies=proxies,
                force_post=force_post, **params)
        except ConnectionError as e:
            raise APIError(f'{cls.parser.symbol} API: Failed to {request_method}, connection error') from e
