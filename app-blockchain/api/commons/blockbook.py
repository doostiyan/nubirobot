from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union

import pytz
from django.conf import settings

from exchange.blockchain.api.general.dtos.dtos import Balance, TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class BlockBookValidator(ResponseValidator):
    # In some networks, it is important to check status of the block so this code is added.
    # Also, we have ignore_warning and ignore_sync which can be important fields for some networks.
    ignore_not_sync = True
    ignore_warnings = False

    @classmethod
    def validate_general_response(cls, response: any) -> bool:
        if not response:
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: Dict[str, any]) -> bool:
        if not block_head_response or not isinstance(block_head_response, dict):
            return False
        if not block_head_response.get('blockbook') or not isinstance(block_head_response.get('blockbook'), dict):
            return False
        if not block_head_response.get('backend') or not isinstance(block_head_response.get('backend'), dict):
            return False
        if not cls.ignore_not_sync and not block_head_response.get('blockbook', {}).get('inSync', False):
            return False
        if (block_head_response.get('blockbook').get('bestHeight') is None or
                not isinstance(block_head_response.get('blockbook').get('bestHeight'), int)):
            return False
        if not cls.ignore_warnings and block_head_response.get('backend').get('warnings'):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False
        if tx_details_response.get('vin') is None:
            return False
        if tx_details_response.get('vout') is None:
            return False
        if not tx_details_response.get('ethereumSpecific'):
            return cls.validate_transaction(tx_details_response)

        return tx_details_response.get('ethereumSpecific').get('status') == 1

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False
        if not address_txs_response.get('transactions'):
            return False
        return True

    @classmethod
    def validate_transfer(cls, transfer: Dict[str, any]) -> bool:
        if transfer.get('ethereumSpecific') and transfer.get('ethereumSpecific').get('status') != 1:
            return False

        data = transfer.get('ethereumSpecific').get('data')
        if transfer.get('tokenTransfers'):
            if data and not data.startswith('0xa9059cbb'):
                return False
        elif data and data != '0x':
            return False
        return True

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, any]) -> bool:
        if not transaction.get('txid'):
            return False
        if not transaction.get('blockHash'):
            return False
        if not transaction.get('blockHeight'):
            return False
        if not transaction.get('confirmations'):
            return False
        if not transaction.get('blockTime'):
            return False
        if not transaction.get('fees'):
            return False
        return True

    @classmethod
    def validate_balance_response(cls, balance_response: Dict[str, any]) -> bool:
        return cls.validate_general_response(balance_response)

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(block_txs_response):
            return False
        if block_txs_response.get('error'):
            return False
        return True

    @classmethod
    def validate_token_txs_response(cls, token_txs_response: Dict[str, Any]) -> bool:
        if token_txs_response is None:
            return False
        if not token_txs_response.get('transactions'):
            return False
        if not isinstance(token_txs_response.get('transactions'), list):
            return False
        return True

    @classmethod
    def validate_token_txs_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if not transaction.get('tokenTransfers') or not isinstance(transaction.get('tokenTransfers'), list):
            return False
        return cls.validate_transaction(transaction) and cls.validate_transfer(transaction)

    @classmethod
    def validate_token_tx_details_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if not transaction.get('tokenTransfers') or not isinstance(transaction.get('tokenTransfers'), list):
            return False
        return cls.validate_transaction(transaction) and cls.validate_transfer(transaction)

    @classmethod
    def validate_token_tx_transfer(cls, transaction: Dict[str, Any]) -> bool:
        if not transaction.get('contract') or not isinstance(transaction.get('contract'), str):
            return False
        if not transaction.get('from') or not isinstance(transaction.get('from'), str):
            return False
        if not transaction.get('to') or not isinstance(transaction.get('to'), str):
            return False
        if not transaction.get('value') or not isinstance(transaction.get('value'), str):
            return False
        return True

    @classmethod
    def validate_block_txs_raw_response(cls, block_txs_raw_response: Optional[Dict[str, any]]) -> bool:
        if not block_txs_raw_response or not isinstance(block_txs_raw_response, dict):
            return False
        if not block_txs_raw_response.get('txs') or not isinstance(block_txs_raw_response.get('txs'), list):
            return False
        return True


class BlockBookParser(ResponseParser):
    validator = BlockBookValidator
    precision = 8
    TOKEN_NETWORK = False

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, any]) -> Optional[str]:
        if not cls.validator.validate_block_head_response(block_head_response):
            return None
        return block_head_response.get('blockbook').get('bestHeight')

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, any]) -> Balance:
        if not cls.validator.validate_balance_response(balance_response):
            return Balance(
                balance=Decimal('0'),
                unconfirmed_balance=Decimal('0')
            )
        return Balance(
            balance=BlockchainUtilsMixin.from_unit(
                number=int(balance_response.get('balance', 0)),
                precision=cls.precision
            ),
            unconfirmed_balance=BlockchainUtilsMixin.from_unit(
                number=int(balance_response.get('unconfirmedBalance', 0)),
                precision=cls.precision,
                negative_value=True
            ),
        )

    @classmethod
    def parse_account_base_tx_details(cls, tx_details_response: Dict[str, any]) -> List[TransferTx]:
        txs: List[TransferTx] = []
        tx_hash = tx_details_response.get('txid')
        from_address = tx_details_response.get('vin')[0].get('addresses')[0]
        if from_address in cls.validator.invalid_from_addresses_for_ETH_like:
            return txs
        to_address = tx_details_response.get('vout')[0].get('addresses')[0]
        value = BlockchainUtilsMixin.from_unit(int(tx_details_response.get('value')), cls.precision)
        if Decimal(value) < cls.validator.min_valid_tx_amount:
            return txs
        confirmations = tx_details_response.get('confirmations')
        block_height = tx_details_response.get('blockHeight')
        date = datetime.fromtimestamp(tx_details_response.get('blockTime'), tz=pytz.utc)
        tx_fee = BlockchainUtilsMixin.from_unit(int(tx_details_response.get('fees')), cls.precision)
        txs.append(TransferTx(
            tx_hash=tx_hash,
            success=True,
            from_address=from_address,
            to_address=to_address,
            value=value,
            symbol=cls.symbol,
            confirmations=confirmations,
            block_height=block_height,
            tx_fee=tx_fee,
            date=date,
            block_hash=None,
            memo=None,
            token=None,
        ))
        return txs

    @classmethod
    def parse_utxo_base_tx_details(cls, tx_details_response: Dict[str, any]) -> List[TransferTx]:
        txs: List[TransferTx] = []
        for vin in tx_details_response.get('vin'):
            if vin.get('isAddress'):
                from_address = cls.convert_address(vin.get('addresses')[0])
                value = BlockchainUtilsMixin.from_unit(int(vin.get('value')), cls.precision)
                for tx in txs:
                    if tx.from_address.casefold() == from_address.casefold():
                        tx.value += value
                        break
                else:
                    txs.append(
                        TransferTx(
                            tx_hash=tx_details_response.get('txid'),
                            success=True,
                            from_address=from_address,
                            to_address='',
                            value=value,
                            symbol=cls.symbol,
                            confirmations=tx_details_response.get('confirmations'),
                            block_height=tx_details_response.get('blockHeight'),
                            block_hash=None,
                            date=datetime.fromtimestamp(tx_details_response.get('blockTime'), tz=pytz.utc),
                            memo=None,
                            tx_fee=BlockchainUtilsMixin.from_unit(int(tx_details_response.get('fees')), cls.precision),
                            token=None
                        )
                    )
        for vout in tx_details_response.get('vout'):
            if vout.get('isAddress'):
                to_address = cls.convert_address(vout.get('addresses')[0])
                value = BlockchainUtilsMixin.from_unit(int(vout.get('value')), cls.precision)
                for tx in txs:
                    if tx.from_address.casefold() == to_address.casefold():
                        tx.value -= value
                        break
                    if tx.to_address.casefold() == to_address.casefold():
                        tx.value += value
                        break
                else:
                    txs.append(
                        TransferTx(
                            tx_hash=tx_details_response.get('txid'),
                            success=True,
                            from_address='',
                            to_address=to_address,
                            value=value,
                            symbol=cls.symbol,
                            confirmations=tx_details_response.get('confirmations'),
                            block_height=tx_details_response.get('blockHeight'),
                            block_hash=None,
                            date=datetime.fromtimestamp(tx_details_response.get('blockTime'), tz=pytz.utc),
                            memo=None,
                            tx_fee=BlockchainUtilsMixin.from_unit(int(tx_details_response.get('fees')), cls.precision),
                            token=None
                        )
                    )
        return txs

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Dict[str, any], _: int) -> List[TransferTx]:
        if not cls.validator.validate_tx_details_response(tx_details_response):
            return []
        txs: List[TransferTx] = []

        # if not vins[0].get("value") then transaction is account based transaction otherwise it"s UTXO"s type.
        if not tx_details_response.get('vin')[0].get('value'):
            if (tx_details_response.get('vin')[0].get('isAddress')
                    and tx_details_response.get('vout')[0].get('isAddress')):
                txs = cls.parse_account_base_tx_details(tx_details_response=tx_details_response)
        else:
            txs = cls.parse_utxo_base_tx_details(tx_details_response=tx_details_response)
        for transfer in tx_details_response.get('tokenTransfers', []):
            contract_address = transfer.get('token')
            if not contract_address:
                continue
            currency = cls.get_currency_by_contract(contract_address.lower())
            if currency:
                contract_info = cls.get_currency_info_by_contract(currency, contract_address)
                if transfer.get('from') in cls.validator.invalid_from_addresses_for_ETH_like:
                    continue
                if Decimal(BlockchainUtilsMixin.from_unit(
                        int(transfer.get('value')),
                        contract_info.get('decimals')
                )) < cls.validator.min_valid_tx_amount:
                    continue
                txs.append(
                    TransferTx(
                        tx_hash=tx_details_response.get('txid'),
                        success=True,
                        from_address=transfer.get('from'),
                        to_address=transfer.get('to'),
                        value=BlockchainUtilsMixin.from_unit(int(transfer.get('value')), contract_info.get('decimals')),
                        symbol=cls.symbol,
                        confirmations=tx_details_response.get('confirmations'),
                        block_height=tx_details_response.get('blockHeight'),
                        block_hash=None,
                        date=datetime.fromtimestamp(tx_details_response.get('blockTime'), tz=pytz.utc),
                        memo=None,
                        tx_fee=BlockchainUtilsMixin.from_unit(int(tx_details_response.get('fees')), cls.precision),
                        token=transfer.get('token')
                    )
                )
        return txs

    @classmethod
    def parse_address_txs_response(cls, address: str, address_txs_response: Dict[str, any], _: int) -> List[TransferTx]:
        txs = []
        if not cls.validator.validate_address_txs_response(address_txs_response):
            return []

        for tx in address_txs_response.get('transactions'):
            if cls.validator.validate_transaction(tx):
                input_output_info = cls.parse_input_output_tx(tx, include_info=True)
                if not input_output_info:
                    return []
                input_addresses, inputs_info, output_addresses, outputs_info = input_output_info
                to_address = set(output_addresses).difference(input_addresses)
                to_address = list(to_address)[0] if to_address else ''
                from_address = set(input_addresses).difference(output_addresses)
                from_address = list(from_address)[0] if from_address else ''

                for input_address in input_addresses:
                    if input_address.casefold() == address.casefold():
                        if not inputs_info.get(cls.convert_address(input_address)):
                            continue
                        for currency, value in inputs_info.get(cls.convert_address(input_address)).items():
                            if currency != Currencies.__getattr__(cls.symbol.lower()):
                                continue
                            contract_address = value.get('contract_address')
                            if contract_address:
                                continue
                            tx_hash = tx.get('txid')
                            txs.append(
                                TransferTx(
                                    tx_hash=tx_hash,
                                    success=True,
                                    from_address=input_address,
                                    to_address=to_address if cls.TOKEN_NETWORK else '',
                                    value=value.get('value'),
                                    symbol=cls.symbol,
                                    confirmations=tx.get('confirmations'),
                                    block_height=int(tx.get('blockHeight')),
                                    block_hash=tx.get('blockHash'),
                                    date=datetime.fromtimestamp(tx.get('blockTime'), pytz.utc),
                                    memo=None,
                                    tx_fee=BlockchainUtilsMixin.from_unit(int(tx.get('fees')), cls.precision),
                                    token=contract_address
                                )
                            )
                for output_address in output_addresses:
                    if output_address.casefold() == address.casefold():
                        for currency, value in outputs_info.get(cls.convert_address(output_address)).items():
                            if currency != Currencies.__getattr__(cls.symbol.lower()):
                                continue
                            contract_address = value.get('contract_address')
                            if contract_address:
                                continue
                            tx_hash = tx.get('txid')
                            for transfer in txs:
                                if (transfer.from_address.casefold() == output_address.casefold() and
                                        transfer.tx_hash == tx_hash):
                                    transfer.value -= value.get('value')
                                    break
                            else:
                                txs.append(
                                    TransferTx(
                                        tx_hash=tx_hash,
                                        success=True,
                                        from_address=from_address if cls.TOKEN_NETWORK else '',
                                        to_address=output_address,
                                        value=value.get('value'),
                                        symbol=cls.symbol,
                                        confirmations=tx.get('confirmations'),
                                        block_height=int(tx.get('blockHeight')),
                                        block_hash=None,
                                        date=datetime.fromtimestamp(tx.get('blockTime'), pytz.utc),
                                        memo=None,
                                        tx_fee=BlockchainUtilsMixin.from_unit(int(tx.get('fees')), cls.precision),
                                        token=contract_address
                                    )
                                )
        return txs

    @classmethod
    def check_transaction_exists(cls, txs_dict: Dict[str, any], address: str, tx_hash: str) -> bool:
        transactions = txs_dict.get(address, [])
        return any(transaction.tx_hash == tx_hash for transaction in transactions)

    @classmethod
    def parse_block_txs_response(cls, block_txs_response: Dict[str, any]) -> List[TransferTx]:
        if not cls.validator.validate_block_txs_response(block_txs_response):
            return []
        txs_dict = {}

        currency_map = {v: k for k, v in Currencies._identifier_map.items()}  # noqa: SLF001

        for tx in block_txs_response.get('txs', []):
            input_output_info = cls.parse_input_output_tx(tx, include_info=True)
            if input_output_info is None:
                continue
            input_addresses, inputs_info, output_addresses, outputs_info = input_output_info
            tx_hash = tx.get('txid')
            if not tx_hash:
                continue
            for input_address in input_addresses:
                if inputs_info.get(cls.convert_address(input_address)) is None:
                    continue
                for currency, value in inputs_info.get(cls.convert_address(input_address)).items():
                    if txs_dict.get(input_address) and cls.check_transaction_exists(txs_dict, input_address, tx_hash):
                        break
                    tx_fee = BlockchainUtilsMixin.from_unit(int(tx.get('fees')), cls.precision)
                    transfer_object = TransferTx(
                        tx_hash=tx.get('txid'),
                        success=True,
                        from_address=input_address,
                        to_address='',
                        value=value.get('value') - tx_fee if not cls.TOKEN_NETWORK else value.get('value'),
                        symbol=currency_map.get(currency, '').upper(),
                        confirmations=tx.get('confirmations'),
                        block_height=int(tx.get('blockHeight')),
                        block_hash=None,
                        date=datetime.fromtimestamp(tx.get('blockTime'), pytz.utc),
                        memo=None,
                        tx_fee=tx_fee,
                        token=value.get('contract_address')
                    )
                    if txs_dict.get(input_address):
                        txs_dict[input_address].append(transfer_object)
                    else:
                        txs_dict[input_address] = [transfer_object]

            for output_address in output_addresses:
                if outputs_info.get(cls.convert_address(output_address)) is None:
                    continue
                for currency, value in outputs_info.get(cls.convert_address(output_address)).items():
                    if txs_dict.get(output_address) and cls.check_transaction_exists(txs_dict, output_address, tx_hash):
                        transactions = txs_dict.get(output_address, [])
                        for i in range(len(transactions)):
                            if txs_dict[output_address][i].tx_hash == tx_hash:
                                txs_dict[output_address][i].value -= value.get('value')
                        break
                    transfer_object = TransferTx(
                        tx_hash=tx.get('txid'),
                        success=True,
                        from_address='',
                        to_address=output_address,
                        value=value.get('value'),
                        symbol=currency_map.get(currency, '').upper(),
                        confirmations=tx.get('confirmations'),
                        block_height=int(tx.get('blockHeight')),
                        block_hash=None,
                        date=datetime.fromtimestamp(tx.get('blockTime'), pytz.utc),
                        memo=None,
                        tx_fee=BlockchainUtilsMixin.from_unit(int(tx.get('fees')), cls.precision),
                        token=value.get('contract_address')
                    )
                    if txs_dict.get(output_address):
                        txs_dict[output_address].append(transfer_object)
                    else:
                        txs_dict[output_address] = [transfer_object]
        return [tx for tx_list in txs_dict.values() for tx in tx_list]

    @classmethod
    def calculate_pages_from_block_response(cls, block_txs_response: Dict[str, any]) -> int:
        return block_txs_response.get('totalPages', 1)

    @classmethod
    def parse_input_tx(cls, tx: Dict[str, any], include_info: bool = False,
                       is_account_format: bool = False) -> Tuple[List[str], dict]:
        input_addresses = []
        inputs_details = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: 0)))

        for input_tx in tx.get('vin', []):
            if len(input_tx.get('addresses', [])) != 1:
                continue
            if not input_tx.get('isAddress'):
                continue
            address = cls.convert_address(input_tx.get('addresses')[0])
            if not address:
                continue
            if address not in input_addresses:
                input_addresses.append(address)

            if include_info:
                target_info = tx if is_account_format else input_tx
                if not target_info.get('value') or Decimal(
                        target_info.get('value')) <= cls.validator.min_valid_tx_amount:
                    continue
                inputs_details[address][cls.currency]['value'] += BlockchainUtilsMixin.from_unit(
                    number=int(target_info.get('value')),
                    precision=cls.precision)

        return input_addresses, inputs_details

    @classmethod
    def parse_output_tx(cls, tx: Dict[str, any], include_info: bool = False) -> Tuple[List[str], dict]:
        output_addresses = []
        outputs_details = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: 0)))

        for output_tx in tx.get('vout', []):
            if not output_tx.get('value') or Decimal(
                    output_tx.get('value')) <= cls.validator.min_valid_tx_amount:
                continue
            if not output_tx.get('addresses'):
                continue
            if len(output_tx.get('addresses', [])) != 1:
                continue
            if not output_tx.get('isAddress'):
                continue
            address = cls.convert_address(output_tx.get('addresses')[0])
            if not address:
                continue
            output_addresses.append(address)

            if include_info:
                outputs_details[address][cls.currency]['value'] += BlockchainUtilsMixin.from_unit(
                    number=int(output_tx.get('value')),
                    precision=cls.precision)

        return output_addresses, outputs_details

    @classmethod
    def parse_input_tx_token(cls, token_transfers: list, include_info: bool = False) -> Tuple[List[str], dict]:
        input_addresses = []
        inputs_details = defaultdict(lambda: defaultdict(dict))

        for token_transfer in token_transfers:
            if not token_transfer.get('value') or Decimal(
                    token_transfer.get('value')) <= cls.validator.min_valid_tx_amount:
                continue
            from_address = cls.convert_address(token_transfer.get('from'))
            if not from_address:
                continue
            input_addresses.append(from_address)

            if include_info:
                token_address = (token_transfer.get('token') or token_transfer.get('contract')).lower()
                currency, contract_address = cls.get_currency_by_contract(token_address)
                contract_info = cls.get_currency_info_by_contract(currency, contract_address)

                if contract_info:
                    if 'value' not in inputs_details[from_address][currency]:
                        inputs_details[from_address][currency] = {
                            'value': 0,
                            'contract_address': contract_address
                        }
                    inputs_details[from_address][currency]['value'] += BlockchainUtilsMixin.from_unit(
                        number=int(token_transfer.get('value')),
                        precision=contract_info.get('decimals'))

        return input_addresses, inputs_details

    @classmethod
    def parse_output_tx_token(cls, token_transfers: List[Dict[str, any]], include_info: bool = False) -> \
            Tuple[List[str], dict]:
        output_addresses = []
        outputs_details = defaultdict(lambda: defaultdict(dict))

        for token_transfer in token_transfers:
            if not token_transfer.get('value') or Decimal(
                    token_transfer.get('value')) <= cls.validator.min_valid_tx_amount:
                continue
            to_address = cls.convert_address(token_transfer.get('to'))
            if not to_address:
                continue
            output_addresses.append(to_address)

            if include_info:
                token_address = (token_transfer.get('token') or token_transfer.get('contract')).lower()
                currency, contract_address = cls.get_currency_by_contract(token_address)
                contract_info = cls.get_currency_info_by_contract(currency, contract_address)

                if contract_info:
                    if 'value' not in outputs_details[to_address][currency]:
                        outputs_details[to_address][currency] = {
                            'value': 0,
                            'contract_address': contract_address
                        }
                    outputs_details[to_address][currency]['value'] += BlockchainUtilsMixin.from_unit(
                        number=int(token_transfer.get('value')),
                        precision=contract_info.get('decimals'))

        return output_addresses, outputs_details

    @classmethod
    def convert_address(cls, address: str) -> str:
        return address

    @classmethod
    def parse_input_output_tx(cls, tx: Dict[str, any], include_info: bool = False) -> \
            Tuple[List[str], dict, List[str], dict]:
        # Get input and output addresses in transaction
        input_addresses = []
        output_addresses = []
        inputs_info = {}
        outputs_info = {}
        is_token = False

        if cls.TOKEN_NETWORK and cls.validator.validate_transfer(tx):
            token_transfers = tx.get('tokenTransfers')
            if token_transfers:
                is_token = True
                input_addresses, inputs_info = cls.parse_input_tx_token(token_transfers, include_info)
                output_addresses, outputs_info = cls.parse_output_tx_token(token_transfers, include_info)

        if not is_token:
            input_addresses, inputs_info = cls.parse_input_tx(tx, include_info, is_account_format=cls.TOKEN_NETWORK)
            output_addresses, outputs_info = cls.parse_output_tx(tx, include_info)

        return input_addresses, inputs_info, output_addresses, outputs_info

    @classmethod
    def parse_token_txs_response(cls,
                                 address: str,
                                 token_txs_response: Dict[str, Any],
                                 block_head: Optional[int],
                                 contract_info: Dict[str, Union[str, int]],
                                 direction: str = '') -> List[TransferTx]:
        transfers: List[TransferTx] = []

        if not cls.validator.validate_token_txs_response(token_txs_response):
            return transfers
        for transaction in token_txs_response.get('transactions', []):
            if not cls.validator.validate_token_txs_transaction(transaction):
                continue
            transfers += cls._parse_token_transfers(transaction)

        return transfers

    @classmethod
    def parse_token_tx_details_response(cls,
                                        token_tx_details_response: Any,
                                        block_head: Optional[int]) -> List[TransferTx]:
        if not cls.validator.validate_token_tx_details_transaction(token_tx_details_response):
            return []

        return cls._parse_token_transfers(token_tx_details_response)

    @classmethod
    def _parse_token_transfers(cls, transaction: Dict[str, Any]) -> List[TransferTx]:
        transfers: List[TransferTx] = []
        for transfer in transaction.get('tokenTransfers', []):
            if not cls.validator.validate_token_tx_transfer(transfer):
                continue
            currency, contract_address = cls.get_currency_by_contract(transfer.get('contract').lower())
            if currency is None:
                continue
            contract_info = cls.get_currency_info_by_contract(currency, contract_address)

            transfers.append(
                TransferTx(
                    tx_hash=transaction.get('txid'),
                    success=True,
                    from_address=cls.convert_address(transfer.get('from')),
                    to_address=cls.convert_address(transfer.get('to')),
                    value=BlockchainUtilsMixin.from_unit(
                        number=int(transfer.get('value')),
                        precision=contract_info.get('decimals')
                    ),
                    symbol=contract_info.get('symbol'),
                    confirmations=transaction.get('confirmations'),
                    block_height=transaction.get('blockHeight'),
                    block_hash=transaction.get('blockHash'),
                    date=datetime.fromtimestamp(transaction.get('blockTime'), tz=pytz.utc),
                    memo=None,
                    tx_fee=BlockchainUtilsMixin.from_unit(
                        number=int(transaction.get('fees')),
                        precision=cls.precision
                    ),
                    token=contract_info.get('address')
                )
            )
        return transfers

    @classmethod
    def to_explorer_address_format(cls, address: str) -> str:
        return address


class BlockBookApi(GeneralApi):
    """Blockbook API explorer.

    supported coins: bitcoin, litecoin, and 30 other coins
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    """
    XPUB_ADDRESS_LENGTH = 111
    GET_BLOCK_ADDRESSES_MAX_NUM = 300
    need_block_head_for_confirmation = False
    last_blocks = 0
    """
        Check status of blockbook API. Maybe it has warning, maybe it is not sync.
                :param only_check_status: If set true, only check info every one hours.
                :return: Blockbook API info
    """
    ignore_not_sync = True
    ignore_warnings = False
    XPUB_SUPPORT = True
    supported_requests = {
        'get_balance': '/api/v2/address/{address}?details={details}&from={from_block}&pageSize=50',
        'get_balance_xpub': '/api/v2/xpub/{address}?details={details}',
        'get_utxo': '/api/v2/utxo/{address}?confirmed={confirmed}',
        'get_address_txs': '/api/v2/address/{address}?details=txs&from={from_block}&pageSize=50',
        'get_tx_details': '/api/v2/tx/{tx_hash}',
        'get_block_txs': '/api/v2/block/{block}?page={page}',
        'get_block_head': '/api/',
        'get_token_txs': '/api/v2/address/{address}?pageSize=50&from={from_block}&details=txs&contract={contract}',
        'get_token_tx_details': '/api/v2/tx/{tx_hash}'
    }

    def get_name(self) -> str:
        return f'{self.symbol.lower()}_blockbook'

    @classmethod
    def get_balance(cls, address: str) -> Optional[str]:
        if len(address) == cls.XPUB_ADDRESS_LENGTH:
            return cls.request(request_method='get_balance_xpub', address=address, details='txslight',
                               from_block=None, body=cls.get_balance_body(address), headers=cls.get_headers(),
                               apikey=cls.get_api_key())
        return cls.request(request_method='get_balance', address=address, details='txslight',
                           from_block=None, body=cls.get_balance_body(address), headers=cls.get_headers(),
                           apikey=cls.get_api_key())

    @classmethod
    def get_block_txs(cls, block_height: int, page: int) -> Optional[str]:
        return cls.request(request_method='get_block_txs', body=cls.get_block_txs_body(block_height),
                           headers=cls.get_headers(), block=block_height, page=page, apikey=cls.get_api_key())

    @classmethod
    def get_address_txs(cls, address: str, **kwargs: Any) -> Optional[str]:
        info = cls.get_block_head()
        block_head = cls.parser.parse_block_head_response(info)
        if not block_head:
            return None
        from_block = None
        if cls.last_blocks:
            from_block = block_head - cls.last_blocks
        return cls.request('get_address_txs',
                           address=address,
                           from_block=from_block, headers=cls.get_headers())

    @classmethod
    def get_token_txs(cls,
                      address: str,
                      contract_info: Dict[str, Union[str, int]],
                      direction: str = '',
                      _: Optional[int] = None,
                      __: Optional[int] = None) -> Any:

        info = cls.get_block_head()
        block_head = cls.parser.parse_block_head_response(info)
        if not block_head:
            return None

        from_block = None
        if cls.last_blocks:
            from_block = block_head - cls.last_blocks

        return cls.request(request_method='get_token_txs', address=address, from_block=from_block,
                           contract=contract_info.get('address'))
