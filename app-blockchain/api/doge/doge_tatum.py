import random
from decimal import Decimal
from typing import List
from django.conf import settings

from exchange.blockchain.api.general.general import GeneralApi, ResponseValidator, ResponseParser

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from blockchain.parsers import parse_timestamp
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.parsers import parse_timestamp
    from exchange.base.models import Currencies

from exchange.blockchain.api.general.dtos.dtos import TransferTx


class DogeTatumResponseValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.0005')

    @classmethod
    def validate_block_head_response(cls, block_head_response) -> bool:
        if not block_head_response or not isinstance(block_head_response, dict):
            return False
        if not block_head_response.get('headers') or not isinstance(block_head_response.get('headers'), int):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response) -> bool:
        if not tx_details_response or not isinstance(tx_details_response, dict):
            return False
        if not tx_details_response.get('vin') or not isinstance(tx_details_response.get('vin'), list):
            return False
        if not tx_details_response.get('vout') or not isinstance(tx_details_response.get('vout'), list):
            return False
        return True

    @classmethod
    def validate_transfer(cls, transfer) -> bool:
        if not transfer or not isinstance(transfer, dict):
            return False
        if not transfer.get('value'):
            return False
        if not transfer.get('scriptPubKey') or not isinstance(transfer.get('scriptPubKey'), dict):
            return False
        if not transfer.get('scriptPubKey').get('type') or not isinstance(transfer.get('scriptPubKey').get('type'),
                                                                          str):
            return False
        if transfer.get('scriptPubKey').get('type') != 'pubkeyhash':
            return False
        if not transfer.get('scriptPubKey').get('addresses') or not isinstance(
                transfer.get('scriptPubKey').get('addresses'), list):
            return False
        if len(transfer.get('scriptPubKey').get('addresses')) > 1:
            return False
        if (not transfer.get('scriptPubKey').get('addresses')[0] or
                not isinstance(transfer.get('scriptPubKey').get('addresses')[0], str)):
            return False
        return True

    @classmethod
    def validate_input_transfer(cls, transfer):
        if not transfer or not isinstance(transfer, dict):
            return False
        if transfer.get('vout') is None or not isinstance(transfer.get('vout'), int):
            return False
        if not transfer.get('scriptSig') or not isinstance(transfer.get('scriptSig'), dict):
            return False
        if not transfer.get('scriptSig').get('hex') or not isinstance(transfer.get('scriptSig').get('hex'), str):
            return False
        return True


class DogeTatumResponseParser(ResponseParser):
    validator = DogeTatumResponseValidator
    symbol = 'DOGE'
    currency = Currencies.doge
    min_valid_tx_amount = Decimal('0.0005')

    @classmethod
    def get_tatum_api(cls):
        return DogeTatumApi

    @classmethod
    def parse_block_head_response(cls, block_head_response):
        if cls.validator.validate_block_head_response(block_head_response):
            return block_head_response.get('headers')

    @classmethod
    def parse_input_transfers(cls, transfer):
        tatum_api = cls.get_tatum_api()
        previous_hash = transfer.get('txid')
        address_index = transfer.get('vout')
        previous_tx_details = tatum_api.get_tx_details(previous_hash)
        if cls.validator.validate_tx_details_response(previous_tx_details):
            if (previous_tx_details.get('vout')[address_index] and
                    cls.validator.validate_transfer(previous_tx_details.get('vout')[address_index])):
                from_address = previous_tx_details.get('vout')[address_index].get('scriptPubKey').get('addresses')[0]
                value = Decimal(str(previous_tx_details.get('vout')[address_index].get('value')))
                return from_address, value

        return None, None

    @classmethod
    def parse_tx_details_response(cls, tx_details_response, block_head) -> List[TransferTx]:
        transfers: List[TransferTx] = []
        input_addresses = []
        output_addresses = []
        if cls.validator.validate_tx_details_response(tx_details_response):
            tx_hash = tx_details_response.get('hash')
            inputs = tx_details_response.get('vin')
            outputs = tx_details_response.get('vout')
            for vin in inputs:
                if cls.validator.validate_input_transfer(vin):
                    from_address, value = cls.parse_input_transfers(vin)
                    if from_address and value:
                        if from_address in input_addresses:
                            for transfer in transfers:
                                if transfer.from_address == from_address:
                                    transfer.value += value
                        else:
                            transfer = TransferTx(
                                tx_hash=tx_hash,
                                success=True,
                                from_address=from_address,
                                to_address='',
                                value=value,
                                symbol=cls.symbol,
                                memo=''
                            )
                            transfers.append(transfer)
                            input_addresses.append(from_address)
            for vout in outputs:
                if cls.validator.validate_transfer(vout):
                    value = Decimal(str(vout.get('value')))
                    to_address = vout.get('scriptPubKey').get('addresses')[0]
                    if to_address in input_addresses:
                        for transfer in transfers:
                            if transfer.from_address == to_address:
                                transfer.value -= value
                    elif (to_address in output_addresses) and (to_address not in input_addresses):
                        for transfer in transfers:
                            if transfer.to_address == to_address:
                                transfer.value += value
                    else:
                        transfer = TransferTx(
                            tx_hash=tx_hash,
                            success=True,
                            from_address='',
                            to_address=to_address,
                            value=value,
                            symbol=cls.symbol,
                            memo=''
                        )
                        transfers.append(transfer)
                        output_addresses.append(to_address)
        return transfers


class DogeTatumApi(GeneralApi):
    symbol = 'DOGE'
    cache_key = 'doge'
    currency = Currencies.doge
    parser = DogeTatumResponseParser
    _base_url = 'https://api.tatum.io/v3/dogecoin/'
    supported_requests = {
        'get_block_head': 'info',
        'get_tx_details': 'transaction/{tx_hash}'
    }
    need_block_head_for_confirmation = False

    @classmethod
    def get_headers(cls):
        return {
            'Content-Type': 'application/json',
            'X-API-KEY': cls.get_api_key()
        }

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.DOGE_TATUM_API_KEYS)
