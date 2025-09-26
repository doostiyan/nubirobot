from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union

from django.conf import settings

from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.api.general.dtos import Balance, TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.models import CurrenciesNetworkName, get_token_code
from exchange.blockchain.utils import BlockchainUtilsMixin


class BlockScanResponseValidator(ResponseValidator):
    valid_batch_transfer_types = ['0xe6930a22']
    TOKEN_TRANSFER_INPUT_PREFIX = '0xa9059cbb'  # noqa: S105
    TOKEN_TRANSFER_INPUT_LENGTH = 138
    precision = 18

    @classmethod
    def validate_general_response(cls, response: Optional[Dict[str, any]]) -> bool:
        if not response:
            return False
        if isinstance(response, dict) and 'result' not in response:
            return False
        if response.get('message') and response.get('message').casefold() == 'NOTOK'.casefold():
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: Dict[str, any]) -> bool:
        return cls.validate_general_response(block_head_response)

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: Dict[str, any]) -> bool:
        return cls.validate_general_response(block_txs_response)

    @classmethod
    def validate_block_txs_raw_response(cls, block_txs_raw_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(block_txs_raw_response):
            return False
        if not isinstance(block_txs_raw_response.get('result'), dict):
            return False
        if not block_txs_raw_response.get('result').get('transactions'):
            return False
        return True

    @classmethod
    def validate_common_transaction_checks(cls, transaction: dict) -> bool:
        if transaction.get('from') == transaction.get('to'):
            return False

        if not cls._validate_from_address_transaction(transaction=transaction):
            return False

        return True

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, any]) -> bool:
        if not cls.validate_common_transaction_checks(transaction=transaction):
            return False
        if not transaction.get('from') or not transaction.get('to'):
            return False
        if not transaction.get('hash'):
            return False
        if not cls._validate_input_data(transaction.get('input')):
            return False
        return True

    @classmethod
    def validate_transaction_receipt(cls, tx_receipt: Dict[str, any]) -> bool:
        return tx_receipt.get('status') == '0x1'

    @classmethod
    def validate_token_transaction(cls, transaction: Dict[str, any], contract_info: Dict[str, Union[int, str]],
                                   _: str = '') -> bool:
        if not cls.validate_common_transaction_checks(transaction=transaction):
            return False
        if ((contract_address := transaction.get('contractAddress')) and
                contract_address != contract_info.get('address')):
            return False
        if not cls._validate_from_address_transaction(transaction):
            return False
        return True

    @classmethod
    def validate_address_tx_transaction(cls, transaction: Dict[str, any]) -> bool:
        if not cls.validate_transaction(transaction):
            return False
        if transaction.get('txreceipt_status') != '1' or transaction.get('isError') != '0':
            return False
        if BlockchainUtilsMixin.from_unit(int(transaction.get('value', 0)), cls.precision) <= cls.min_valid_tx_amount:
            return False
        if not cls._validate_from_address_transaction(transaction):
            return False
        return True

    @classmethod
    def _validate_from_address_transaction(cls, transaction: Dict[str, any]) -> bool:
        if any(
                cls._are_addresses_equal(transaction.get('from'), address)
                for address in cls.invalid_from_addresses_for_ETH_like
        ):
            return False

        return True

    @classmethod
    def _is_valid_native_currency_input_address(cls, input_data: str) -> bool:
        return input_data in ['0x', '0x0000000000000000000000000000000000000000']

    @classmethod
    def _validate_input_data(cls, input_data: str) -> bool:
        if cls._is_valid_native_currency_input_address(input_data=input_data):
            return True
        if input_data[0:10] == cls.TOKEN_TRANSFER_INPUT_PREFIX and len(input_data) == cls.TOKEN_TRANSFER_INPUT_LENGTH:
            return True
        if input_data[0:10] in cls.valid_batch_transfer_types:
            return True
        return False

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False
        if address_txs_response.get('message') != 'OK':
            return False
        return True

    @classmethod
    def validate_balance_response(cls, balance_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(balance_response):
            return False
        if balance_response.get('status') == '0' or balance_response.get('message') == 'NOTOK':
            return False
        return True

    @staticmethod
    def _are_addresses_equal(addr1: Optional[str], addr2: Optional[str]) -> bool:
        if not addr1 or not addr2:
            return False
        addr1 = addr1.lower()
        if not addr1.startswith('0x'):
            addr1 = '0x' + addr1
        addr2 = addr2.lower()
        if not addr2.startswith('0x'):
            addr2 = '0x' + addr2
        return addr1 == addr2


class BlockScanResponseParser(ResponseParser):
    validator = BlockScanResponseValidator
    precision = 18
    symbol = None
    currency = None
    valid_batch_transfer_types = ['0xe6930a22']

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, any]) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response):
            return int(block_head_response.get('result'), 16)
        return None

    @classmethod
    def parse_block_txs_response(cls, block_txs_response: Dict[str, any]) -> List[TransferTx]:
        if not cls.validator.validate_block_txs_response(block_txs_response):
            return []

        filtered_txs = cls._filter_block_transactions(block_txs_response.get('result').get('transactions'))
        block_txs_list: List[TransferTx] = []
        for tx in filtered_txs:
            if block_txs := cls._parse_block_and_detail_tx(tx=tx):
                block_txs_list.extend(block_txs)
        return block_txs_list

    @classmethod
    def _parse_block_and_detail_tx(cls, tx: Dict[str, any], block_head: Optional[int] = None) -> [TransferTx]:
        transfer_txs: List[TransferTx] = []
        input_data = tx.get('input')
        block_height = int(tx.get('blockNumber'), 16)
        confirmations = int(tx.get('confirmations', 0))
        if not confirmations and block_head:
            confirmations = block_head - block_height
        token = None

        if input_data in ['0x', '0x0000000000000000000000000000000000000000']:
            value = BlockchainUtilsMixin.from_unit(int(tx.get('value'), 16), precision=cls.precision)
            to_address = tx.get('to')
            from_address = tx.get('from')
            symbol = cls.symbol
            return [cls._create_transfer_tx(tx, block_height, confirmations, token,
                                            from_address, to_address, value, symbol)]

        transfers = cls._get_transfers(input_data, tx.get('from'), tx.get('to'))
        if transfers:
            for transfer in transfers:
                transfer_txs.append(cls._create_transfer_tx(tx, block_height, confirmations, **transfer))
        return transfer_txs

    @classmethod
    def _create_transfer_tx(cls, tx: Dict[str, any], block_height: int, confirmations: int, token: Optional[str],
                            from_address: Optional[str] = None,
                            to_address: Optional[str] = None, value: Optional[Decimal] = None,
                            symbol: Optional[str] = None) -> TransferTx:
        return TransferTx(
            block_height=block_height,
            block_hash=tx.get('blockHash'),
            tx_hash=tx.get('hash'),
            success=True,
            confirmations=confirmations,
            from_address=from_address,
            to_address=to_address,
            date=parse_utc_timestamp(tx.get('timeStamp')),
            value=value,
            symbol=symbol,
            token=token,
        )

    @classmethod
    def _get_transfers(cls, input_data: str, from_address: str, contract_address: str) -> \
            Optional[List[Dict[str, any]]]:
        transfers = []
        if input_data[0:10] == '0xa9059cbb':
            transfers = cls.parse_token_transfer_erc20_input_data(input_data, from_address, contract_address)
        elif input_data[0:10] in cls.valid_batch_transfer_types:
            transfers = cls.parse_batch_transfer_erc20_input_data(input_data, contract_address)
        return transfers

    @classmethod
    def parse_batch_transfer_erc20_input_data(cls, input_data: str, from_address: str) -> List[Dict[str, any]]:
        _, tokens, addresses, values = input_data.split(input_data[10:][192:256])
        transfers_count = len(tokens)
        transfers = []
        for i in range(0, transfers_count, 64):
            token = '0x' + tokens[i: i + 64][24:64]
            currency, contract_address = cls.contract_currency(token.lower())
            if not currency:
                continue
            contract_info = cls.contract_info(currency, contract_address)
            if not contract_info:
                continue

            transfers.append({
                'from_address': from_address.lower(),
                'to_address': '0x' + addresses[i: i + 64][24:64].lower(),
                'value': BlockchainUtilsMixin.from_unit(int(values[i: i + 64], 16), contract_info.get('decimals')),
                'symbol': contract_info.get('symbol'),
                'token': contract_info.get('address')
            })
        return transfers

    @classmethod
    def parse_token_transfer_erc20_input_data(cls, input_data: str, from_address: str, contract_address: str) -> \
            Optional[List[Dict[str, any]]]:
        currency, _ = cls.contract_currency(contract_address)  # tx.get("to")
        if currency is None:
            return None
        amount = int(input_data[74:138], 16)
        to_address = '0x' + input_data[34:74]
        contract_info = cls.contract_info(currency, contract_address)
        if not contract_info:
            return None
        if currency == get_token_code('1b_babydoge', 'bep20'):
            amount -= amount * 0.1
        amount = BlockchainUtilsMixin.from_unit(amount, contract_info.get('decimals'))
        return [{
            'from_address': from_address.lower(),
            'to_address': to_address.lower(),
            'value': amount,
            'symbol': contract_info.get('symbol'),
            'token': contract_info.get('address')
        }]

    @classmethod
    def _filter_block_transactions(cls, block_txs_response: List[Dict[str, any]]) -> List[Dict[str, any]]:
        return list(
            filter(lambda tx: cls.validator.validate_transaction(tx), block_txs_response))

    @classmethod
    def contract_currency(cls, token_address: str) -> Tuple[Optional[int], Optional[str]]:
        currency_with_default_contract = cls.contract_currency_list().get(token_address)
        if currency_with_default_contract:
            return currency_with_default_contract, None
        if token_address in CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS:
            return CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(token_address, {}).get(
                'destination_currency'), token_address
        return None, None

    @classmethod
    def contract_info(cls, currency: int, contract_address: Optional[str] = None) -> \
            Optional[Dict[str, Union[str, int]]]:
        if contract_address in CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS:
            return CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(contract_address, {}).get('info')
        return cls.contract_info_list().get(currency)

    @classmethod
    def parse_tx_details_response(cls,
                                  tx_details_response: Dict[str, any],
                                  block_head: Optional[int]) -> List[TransferTx]:
        if (cls.validator.validate_general_response(tx_details_response) and
                cls.validator.validate_transaction(tx_details_response.get('result'))):
            return cls._parse_block_and_detail_tx(tx_details_response.get('result'), block_head)
        return []

    @classmethod
    def parse_tx_receipt_response(cls, tx_receipt_response: dict) -> Optional[bool]:
        if cls.validator.validate_general_response(tx_receipt_response):
            return cls.validator.validate_transaction_receipt(tx_receipt=tx_receipt_response.get('result'))
        return None

    @classmethod
    def parse_address_txs_response(cls, _: str, address_txs_response: Dict[str, any], __: int) -> List[TransferTx]:
        if not cls.validator.validate_address_txs_response(address_txs_response):
            return []

        # Parse transactions
        transfers = []
        for tx in address_txs_response.get('result'):
            if not cls.validator.validate_address_tx_transaction(tx):
                continue
            parsed_address_tx = cls._parse_address_and_token_tx(tx)
            if parsed_address_tx is not None:
                transfers.append(parsed_address_tx)
        return transfers

    @classmethod
    def _parse_address_and_token_tx(cls, tx: Dict[str, any]) -> TransferTx:
        if tx.get('contractAddress'):
            currency, contract_address = cls.contract_currency(tx.get('contractAddress'))
            contract_info = cls.contract_info(currency, contract_address)
            value = BlockchainUtilsMixin.from_unit(int(tx.get('value')), contract_info.get('decimals'))
            symbol = contract_info.get('symbol')
        else:
            value = BlockchainUtilsMixin.from_unit(int(tx.get('value', 0)), cls.precision)
            symbol = cls.symbol

        return TransferTx(
            block_height=int(tx.get('blockNumber')),
            block_hash=tx.get('blockHash'),
            tx_hash=tx.get('hash'),
            success=True,
            confirmations=int(tx.get('confirmations', 0)),
            from_address=tx.get('from'),
            to_address=tx.get('to'),
            date=parse_utc_timestamp(tx.get('timeStamp')),
            value=value,
            symbol=symbol,
            tx_fee=BlockchainUtilsMixin.from_unit(int(tx.get('gas')) * int(tx.get('gasPrice')),
                                                  precision=cls.precision))

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, any]) -> Decimal:
        if not cls.validator.validate_balance_response(balance_response):
            return Decimal(0)
        return BlockchainUtilsMixin.from_unit(int(balance_response.get('result', 0)), precision=cls.precision)

    @classmethod
    def parse_balances_response(cls, balances_response: Dict[str, any]) -> List[Balance]:
        if not cls.validator.validate_balance_response(balances_response):
            return []

        balances = []
        for balance in balances_response.get('result'):
            balances.append(
                Balance(
                    balance=BlockchainUtilsMixin.from_unit(int(balance.get('balance', 0)), precision=cls.precision),
                    address=balance.get('account')
                )
            )
        return balances

    @classmethod
    def parse_token_balance_response(cls, balance_response: Dict[str, any], contract_info: dict) -> Decimal:
        if not cls.validator.validate_balance_response(balance_response):
            return Decimal(0)
        return BlockchainUtilsMixin.from_unit(int(balance_response.get('result', 0)),
                                              precision=contract_info.get('decimals'))

    @classmethod
    def parse_token_txs_response(cls,
                                 _: str,
                                 token_txs_response: Dict[str, any],
                                 __: int,
                                 contract_info: Dict[str, Union[int, str]],
                                 ___: str = '') -> List[TransferTx]:
        if not cls.validator.validate_address_txs_response(token_txs_response):
            return []
        transactions = token_txs_response.get('result')
        token_txs: List[TransferTx] = []
        for transaction in transactions:
            if cls.validator.validate_token_transaction(transaction, contract_info):
                token_tx = cls._parse_address_and_token_tx(transaction)
                token_txs.append(token_tx)
        return token_txs


class BlockScanAPI(GeneralApi):
    parser = BlockScanResponseParser
    rate_limit = 0.2
    SUPPORT_GET_BALANCE_BATCH = True
    chain_id: Optional[int] = None
    _base_url = 'https://api.etherscan.io'

    supported_requests = {
        'get_address_txs': '/v2/api?module=account&action=txlist&address={address}&page=1&offset=50&sort=desc&apikey={'
                           'apikey}&chainid={chainid}',
        'get_tx_details': '/v2/api?module=proxy&action=eth_getTransactionByHash&txhash={tx_hash}&'
                          'apikey={apikey}&chainid={chainid}',
        'get_balance': '/v2/api?module=account&action=balance&address={address}&tag=latest&apikey={apikey}'
                       '&chainid={chainid}',
        'get_balances': '/v2/api?module=account&action=balancemulti&address={addresses}&tag=latest&apikey={apikey}'
                        '&chainid={chainid}',
        'get_block_head': '/v2/api?module=proxy&action=eth_blockNumber&apikey={apikey}&chainid={chainid}',
        'get_block_txs': '/v2/api?module=proxy&action=eth_getBlockByNumber&tag={height}&boolean=true&apikey={apikey}'
                         '&chainid={chainid}',
        'get_token_balance': '/v2/api?module=account&action=tokenbalance&contractaddress={contract_address}&address={'
                             'address}&tag=latest&apikey={apikey}&chainid={chainid}',
        'get_token_txs': '/v2/api?module=account&action=tokentx&contractaddress={contract_address}&address={'
                         'address}&page=1&offset=50&sort=desc&apikey={apikey}&chainid={chainid}',
        'get_tx_receipt': '/v2/api?module=proxy&action=eth_getTransactionReceipt&txhash={tx_hash}&apikey={apikey}'
                          '&chainid={chainid}',
    }

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        return {
            'User-Agent': 'Mozilla/5.0' if not settings.IS_VIP else
            'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/95.0'
        }

    @classmethod
    def get_balance(cls, address: str) -> Any:
        return cls.request(request_method='get_balance', body=cls.get_balance_body(address),
                           headers=cls.get_headers(), address=address, apikey=cls.get_api_key(), chainid=cls.chain_id)

    @classmethod
    def get_balances(cls, addresses: List[str]) -> Any:
        separator = ','
        formatted_addresses = separator.join(addresses)
        return cls.request(request_method='get_balances', body=cls.get_balances_body(addresses),
                           headers=cls.get_headers(), addresses=formatted_addresses, apikey=cls.get_api_key(),
                           chainid=cls.chain_id)

    @classmethod
    def get_block_txs(cls, block_height: int) -> Optional[str]:
        return cls.request('get_block_txs', height=hex(block_height), apikey=cls.get_api_key(),
                           headers=cls.get_headers(), chainid=cls.chain_id)

    @classmethod
    def get_token_balance(cls, address: str, contract_info: Dict[str, Union[str, int]]) -> Any:
        return cls.request(request_method='get_token_balance',
                           body=cls.get_token_balance_body(address, contract_info),
                           headers=cls.get_headers(), contract_address=contract_info.get('address'),
                           address=address, apikey=cls.get_api_key(), chainid=cls.chain_id)

    @classmethod
    def get_tx_receipt(cls, tx_hash: str) -> Any:
        return cls.request(request_method='get_tx_receipt', body=cls.get_tx_receipt_body(tx_hash),
                           headers=cls.get_headers(), tx_hash=tx_hash, apikey=cls.get_api_key(), chainid=cls.chain_id)

    @classmethod
    def get_address_txs_receipt(cls, tx_hash: str) -> Any:
        return cls.request(request_method='get_address_tx_receipt', body=cls.get_address_txs_receipt_body(tx_hash),
                           headers=cls.get_headers(), tx_hash=tx_hash, apikey=cls.get_api_key(), chainid=cls.chain_id)

    @classmethod
    def get_token_txs(cls, address: str, contract_info: Dict[str, Union[str, int]], direction: str = '',
                      start_date: Optional[int] = None, end_date: Optional[int] = None) -> Any:
        if start_date and end_date:
            return cls.get_token_txs_time(address, contract_info, start_date, end_date)
        return cls.request(request_method='get_token_txs', body=cls.get_token_txs_body(address, contract_info),
                           headers=cls.get_headers(), address=address,
                           contract_address=contract_info.get('address'),
                           apikey=cls.get_api_key(), timeout=cls.timeout, chainid=cls.chain_id)

    @classmethod
    def get_block_head(cls) -> Any:
        return cls.request(request_method='get_block_head', body=cls.get_block_head_body(),
                           headers=cls.get_headers(), apikey=cls.get_api_key(), timeout=cls.timeout,
                           chainid=cls.chain_id)

    @classmethod
    def get_address_txs(cls, address: str, **kwargs: Any) -> Any:
        return cls.request(request_method='get_address_txs', body=cls.get_address_txs_body(address),
                           headers=cls.get_headers(), address=address, apikey=cls.get_api_key(), timeout=cls.timeout,
                           chainid=cls.chain_id)

    @classmethod
    def get_tx_details(cls, tx_hash: str) -> Any:
        return cls.request(request_method='get_tx_details', body=cls.get_tx_details_body(tx_hash),
                           headers=cls.get_headers(), tx_hash=tx_hash, apikey=cls.get_api_key(),
                           timeout=cls.timeout, chainid=cls.chain_id)
