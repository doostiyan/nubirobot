import datetime
import random
from decimal import Decimal
from typing import Any, Dict, List

from django.conf import settings

from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class CardanoBlockFrostValidator(ResponseValidator):

    @classmethod
    def validate_general_response(cls, response: Any) -> bool:
        if not response:
            return False
        return True

    @classmethod
    def validate_balance_response(cls, balance_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(balance_response):
            return False
        if not balance_response.get('amount'):
            return False
        if not balance_response.get('address'):
            return False
        if not balance_response.get('amount')[0].get('quantity'):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(block_head_response):
            return False
        if not block_head_response.get('height'):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Dict[str, Any]) -> bool:
        if not tx_details_response.get('tx_info'):
            return False
        if not tx_details_response.get('tx_utxos'):
            return False
        if not tx_details_response.get('tx_info').get('hash'):
            return False
        if not tx_details_response.get('tx_info').get('block_height'):
            return False
        if not tx_details_response.get('tx_info').get('block_time'):
            return False
        if not tx_details_response.get('tx_info').get('fees'):
            return False
        if not tx_details_response.get('tx_utxos').get('inputs'):
            return False
        if not tx_details_response.get('tx_utxos').get('outputs'):
            return False
        return True

    @classmethod
    def validate_input_output_utxo(cls, utxo: Dict[str, Any]) -> bool:
        if not utxo.get('address'):
            return False
        if not utxo.get('amount'):
            return False
        return True

    @classmethod
    def validate_amount(cls, output_amount: Dict[str, Any]) -> bool:
        if output_amount.get('unit') != 'lovelace':
            return False
        if not output_amount.get('quantity'):
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: Any) -> bool:
        return cls.validate_general_response(address_txs_response)

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, Any]) -> bool:
        return cls.validate_tx_details_response(transaction)

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: Any) -> bool:
        return cls.validate_general_response(block_txs_response)


class CardanoBlockFrostParser(ResponseParser):
    validator = CardanoBlockFrostValidator
    precision = 6
    currency = Currencies.ada
    symbol = 'ADA'

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, Any]) -> Decimal:
        if not cls.validator.validate_balance_response(balance_response):
            return Decimal('0')
        return BlockchainUtilsMixin.from_unit(int(balance_response['amount'][0].get('quantity')), cls.precision)

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, Any]) -> int:
        if not cls.validator.validate_block_head_response(block_head_response):
            return False
        return block_head_response.get('height')

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Dict[str, Any], block_head: int) -> List[TransferTx]:
        input_addresses = []
        output_addresses = []
        transfers = []

        def process_utxos(utxos: List[Dict[str, Any]], is_input: bool) -> None:
            addresses = input_addresses if is_input else output_addresses
            for utxo in utxos:
                if not cls.validator.validate_input_output_utxo(utxo):
                    continue
                address = utxo.get('address')
                for amount in utxo.get('amount'):
                    if not cls.validator.validate_amount(amount):
                        continue
                    amount_value = BlockchainUtilsMixin.from_unit(int(amount.get('quantity')), cls.precision)
                    if address in addresses:
                        for transfer in transfers:
                            if ((is_input and transfer.from_address == address)
                                    or (not is_input and transfer.to_address == address)):
                                transfer.value += amount_value
                    elif not is_input and address in input_addresses:
                        for transfer in transfers:
                            if transfer.from_address == address:
                                transfer.value -= amount_value
                    else:
                        transfers.append(cls.make_transfer(tx_details_response, block_head, utxo, amount, is_input))
                        addresses.append(address)

        process_utxos(tx_details_response.get('tx_utxos').get('inputs'), is_input=True)
        process_utxos(tx_details_response.get('tx_utxos').get('outputs'), is_input=False)

        return transfers

    @classmethod
    def parse_address_txs_response(cls,
                                   address: str,
                                   address_txs_response: List[Dict[str, Any]],
                                   block_head: int) -> List[TransferTx]:
        transfers: List[TransferTx] = []

        if not cls.validator.validate_address_txs_response(address_txs_response):
            return transfers

        def process_utxos(utxos: List[Dict[str, Any]], is_input: bool, tx: Dict[str, Any]) -> None:
            for utxo in utxos:
                if not cls.validator.validate_input_output_utxo(utxo) or utxo.get('address') != address:
                    continue
                for amount in utxo.get('amount'):
                    if not cls.validator.validate_amount(amount):
                        continue
                    amount_value = BlockchainUtilsMixin.from_unit(int(amount.get('quantity')), cls.precision)
                    new_transfer = True
                    for transfer in transfers:
                        if transfer.tx_hash == tx.get('tx_info').get('hash'):
                            if is_input:
                                transfer.value += amount_value
                            elif transfer.from_address != '':
                                transfer.value -= amount_value
                            elif transfer.to_address != '':
                                transfer.value += amount_value
                            new_transfer = False
                            break
                    if new_transfer:
                        transfers.append(cls.make_transfer(tx, block_head, utxo, amount, is_input))

        for tx in address_txs_response:
            if not cls.validator.validate_transaction(tx):
                continue

            process_utxos(tx.get('tx_utxos').get('inputs'), is_input=True, tx=tx)
            process_utxos(tx.get('tx_utxos').get('outputs'), is_input=False, tx=tx)

        return transfers

    @classmethod
    def parse_block_txs_response(cls, block_txs_response: List[Dict[str, Any]]) -> List[TransferTx]:
        if not cls.validator.validate_block_txs_response(block_txs_response):
            return []
        input_addresses = []
        output_addresses = []
        transfers: List[TransferTx] = []

        def process_utxos(utxos: List[Dict[str, Any]], is_input: bool, data: Dict[str, Any]) -> None:
            addresses = input_addresses if is_input else output_addresses
            for utxo in utxos:
                if not cls.validator.validate_input_output_utxo(utxo):
                    continue
                for amount in utxo.get('amount'):
                    if not cls.validator.validate_amount(amount):
                        continue
                    address = utxo.get('address')
                    tx_hash = tx.get('tx_utxos').get('hash')
                    amount_value = BlockchainUtilsMixin.from_unit(int(amount.get('quantity')), cls.precision)
                    new_transfer = True
                    if address in addresses:
                        for transfer in transfers:
                            if (((is_input and transfer.from_address == address) or (
                                    not is_input and transfer.to_address == address))
                                    and transfer.tx_hash == tx_hash):
                                transfer.value += amount_value
                                new_transfer = False
                    elif address in input_addresses and not is_input:
                        for transfer in transfers:
                            if transfer.from_address == address and transfer.tx_hash == tx_hash:
                                transfer.value -= amount_value
                                new_transfer = False
                    if new_transfer:
                        transfers.append(cls.make_transfer(data, 0, utxo, amount, is_input))
                        addresses.append(address)

        for tx in block_txs_response:
            if not cls.validator.validate_transaction(tx):
                continue

            process_utxos(utxos=tx.get('tx_utxos').get('inputs'), is_input=True, data=tx)
            process_utxos(utxos=tx.get('tx_utxos').get('outputs'), is_input=False, data=tx)

        return transfers

    @classmethod
    def make_transfer(cls,
                      transfer: Dict[str, Any],
                      block_head: int,
                      utxo: Dict[str, Any],
                      amount: Dict[str, Any],
                      is_input: bool) -> TransferTx:
        return TransferTx(
            block_height=transfer.get('tx_info').get('block_height'),
            block_hash=transfer.get('tx_info').get('block'),
            tx_hash=transfer.get('tx_info').get('hash'),
            date=datetime.datetime.fromtimestamp(transfer.get('tx_info').get('block_time'), tz=datetime.timezone.utc),
            success=True,
            confirmations=block_head - transfer.get('tx_info').get('block_height') if block_head else 0,
            from_address=utxo.get('address') if is_input else '',
            to_address=utxo.get('address') if not is_input else '',
            value=BlockchainUtilsMixin.from_unit(int(amount.get('quantity')), cls.precision),
            symbol=cls.symbol,
            memo=None,
            tx_fee=BlockchainUtilsMixin.from_unit(int(transfer.get('tx_info').get('fees')), cls.precision),
            token=None,
        )


class CardanoBlockFrostApi(GeneralApi):
    parser = CardanoBlockFrostParser
    _base_url = 'https://cardano-mainnet.blockfrost.io/api/v0'
    testnet_url = 'https://cardano-testnet.blockfrost.io/api/v0'

    symbol = 'ADA'
    cache_key = 'ada'
    currency = Currencies.ada
    rate_limit = 0.1
    address_tx_limit = 25

    supported_requests = {
        'get_balance': '/addresses/{address}',
        'get_address_txs': '/addresses/{address}/transactions?order=desc',
        'get_tx': '/txs/{tx_hash}',
        'get_utxos': '/txs/{tx_hash}/utxos',
        'get_block_head': '/blocks/latest',
        'get_block_txs': '/blocks/{block_height}/txs',
        'get_tx_details': '/txs/{tx_hash}'
    }

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice(settings.BLOCKFROST_API_KEY)

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        return {
            'project_id': random.choice(settings.BLOCKFROST_API_KEY)
        }

    @classmethod
    def get_tx_details(cls, tx_hash: str) -> Dict[str, Any]:
        tx_info = cls.request(request_method='get_tx_details', headers=cls.get_headers(), tx_hash=tx_hash,
                              apikey=cls.get_api_key(), timeout=cls.timeout)
        tx_utxos = cls.request(request_method='get_utxos', headers=cls.get_headers(), tx_hash=tx_hash,
                               apikey=cls.get_api_key(), timeout=cls.timeout)

        return {'tx_info': tx_info, 'tx_utxos': tx_utxos}

    @classmethod
    def get_address_txs(cls, address: str, **kwargs: Any) -> List[Dict[str, Any]]:
        response = cls.request(request_method='get_address_txs', headers=cls.get_headers(), address=address,
                               apikey=cls.get_api_key(), timeout=cls.timeout)
        transactions_data = []
        for tx in response[:cls.address_tx_limit]:
            tx_info = cls.request(request_method='get_tx', headers=cls.get_headers(), tx_hash=tx.get('tx_hash'),
                                  apikey=cls.get_api_key(), timeout=cls.timeout)
            tx_utxos = cls.request(request_method='get_utxos', headers=cls.get_headers(),
                                   tx_hash=tx.get('tx_hash'), apikey=cls.get_api_key(), timeout=cls.timeout)
            transactions_data.append({'tx_info': tx_info, 'tx_utxos': tx_utxos})
        return transactions_data

    @classmethod
    def get_block_txs(cls, block_height: int) -> List[Dict[str, Any]]:
        response = cls.request(request_method='get_block_txs', headers=cls.get_headers(),
                               block_height=block_height, apikey=cls.get_api_key(), timeout=cls.timeout)
        transactions_data = []
        for tx_hash in response:
            tx_info = cls.request(request_method='get_tx', headers=cls.get_headers(),
                                  tx_hash=tx_hash, apikey=cls.get_api_key(), timeout=cls.timeout)
            tx_utxos = cls.request(request_method='get_utxos', headers=cls.get_headers(),
                                   tx_hash=tx_hash, apikey=cls.get_api_key(), timeout=cls.timeout)
            transactions_data.append({'tx_info': tx_info, 'tx_utxos': tx_utxos})
        return transactions_data
