from decimal import Decimal
from typing import List

from exchange.base.models import get_currency_codename
from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.explorer.utils.blockchain import get_currency_symbol_from_currency_code
from exchange.explorer.utils.dto import BaseDTOCreator


class TransactionDTOCreator(BaseDTOCreator):
    DTO_CLASS = TransferTx

    @classmethod
    def normalize_transfer_data(cls, data: dict) -> dict:
        data = super().normalize_data(data)
        return {
            'from_address': data.get('from'),
            'to_address': data.get('to'),
            'value': data.get('value'),
            'symbol': data.get('symbol'),
            'token': data.get('token'),
            'memo': data.get('memo'),
        }

    @classmethod
    def normalize_input_data(cls, data: dict) -> dict:
        data = super().normalize_data(data)
        return {
            'from_address': data.get('address'),
            'value': data.get('value'),
            'symbol': get_currency_codename(data.get('currency'))
        }

    @classmethod
    def normalize_output_data(cls, data: dict) -> dict:
        data = super().normalize_data(data)
        return {
            'to_address': data.get('address'),
            'value': data.get('value'),
            'symbol': get_currency_codename(data.get('currency'))
        }

    @classmethod
    def normalize_tx_details_data(cls, data: dict) -> List[dict]:
        data = super().normalize_data(data)

        tx_details_data = {'tx_hash': data.get('hash'), 'success': data.get('success'),
                           'date': data.get('date'), 'confirmations': data.get('confirmations'),
                           'block_height': data.get('block'), 'tx_fee': data.get('fees')}

        transfers_data = [{**cls.normalize_transfer_data(transfer_data), **tx_details_data}
                          for transfer_data in data.get('transfers', [])]

        inputs_data = [{**cls.normalize_input_data(transfer_data), **tx_details_data}
                       for transfer_data in data.get('inputs', [])]

        outputs_data = [{**cls.normalize_output_data(transfer_data), **tx_details_data}
                        for transfer_data in data.get('outputs', [])]

        return transfers_data + inputs_data + outputs_data

    @classmethod
    def normalize_address_tx_data(cls, data) -> list:
        data = super().normalize_data(data)
        value = data.get('value')
        if value > 0:
            to_address = data.get('address')
        else:
            to_address = None
        common_data = {
            'tx_hash': data.get('hash'),
            'success': True,
            'to_address': to_address or '',
            'value': value,
            'confirmations': data.get('confirmations'),
            'block_height': data.get('block') or 0,
            'block_hash': None,
            'date': data.get('timestamp'),
            'memo': data.get('tag'),
            'tx_fee': data.get('fees', None),
            'token': data.get('contract_address', None),
            'index': data.get('index') or 0,
        }

        address_tx_data = [common_data]
        if data.get('from_address'):
            address_tx_data = [
                {
                    **common_data,
                    'from_address': from_address or ''
                } for from_address in data.get('from_address')
            ]
        return address_tx_data

    @classmethod
    def normalize_submodule_block_txs_data(cls, data) -> list:
        data = super().normalize_data(data)
        block_txs_data = []
        for tx_direction, addresses in data.items():
            for address, currencies in addresses.items():
                for currency, txs in currencies.items():
                    currency_symbol = get_currency_symbol_from_currency_code(currency)
                    for tx in txs:
                        block_txs_data.append({
                            'success': True,
                            'from_address': address if tx_direction == 'outgoing_txs' else '',
                            'to_address': address if tx_direction == 'incoming_txs' else '',
                            'tx_hash': tx.get('tx_hash'),
                            'symbol': currency_symbol,
                            'value': tx.get('value'),
                            'block_height': tx.get('block_height'),
                            'token': tx.get('contract_address'),
                            'index': tx.get('index') or 0,
                            'memo': '',
                        })
        return block_txs_data

    @classmethod
    def normalize_db_txs_data(cls, data) -> list:
        normalized_data = []
        for tx in data:
            if tx.value:
                tx.value = Decimal(tx.value)
            if tx.tx_fee:
                tx.tx_fee = Decimal(tx.tx_fee)

            tx = cls.normalize_data(tx)
            # deprecated:
            # tx['from_address'] = tx.pop('_from_address')
            # tx['to_address'] = tx.pop('_to_address')

            tx['from_address'] = tx.pop('from_address_str') or None
            tx['to_address'] = tx.pop('to_address_str') or None
            normalized_data.append(tx)
        return normalized_data

    @classmethod
    def get_tx_details_dto(cls, data, **kwargs):
        normalized_data = cls.normalize_tx_details_data(data=data)
        return [cls.get_dto(data, **kwargs) for data in normalized_data]

    @classmethod
    def get_db_txs_dto(cls, data, **kwargs):
        data = cls.normalize_db_txs_data(data)
        return cls.get_dtos(data, **kwargs)

    @classmethod
    def get_address_txs_dto(cls, data, **kwargs):
        normalized_data = cls.normalize_address_tx_data(data)
        return [cls.get_dto(data, **kwargs) for data in normalized_data]

    @classmethod
    def get_block_txs_dto(cls, data, serialize=True, **kwargs):
        source = kwargs.pop('source', '')
        if source == 'submodule':
            data = cls.normalize_submodule_block_txs_data(data)
        else:
            data = cls.normalize_db_txs_data(data)
        return [cls.get_dto(tx_data, serialize=serialize, **kwargs) for tx_data in data]
