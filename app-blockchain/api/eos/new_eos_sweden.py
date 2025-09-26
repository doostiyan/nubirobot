import json
from typing import List
from decimal import Decimal

from django.conf import settings

from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseValidator, ResponseParser

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class EosSwedenResponseValidator(ResponseValidator):
    symbol = 'EOS'
    min_valid_tx_amount = Decimal('0.0005')

    @classmethod
    def validate_general_response(cls, response):
        if not response:
            return False
        return True

    @classmethod
    def validate_balance_response(cls, balances_response) -> bool:
        if not cls.validate_general_response(balances_response):
            return False
        if not balances_response.get('account_name'):
            return False
        if (not balances_response.get('core_liquid_balance')
                or not isinstance(balances_response.get('core_liquid_balance'), str)
                or not (' EOS') in balances_response.get('core_liquid_balance')):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False
        if not tx_details_response.get('actions'):
            return False
        if not tx_details_response.get('executed'):
            return False
        if not tx_details_response.get('trx_id'):
            return False
        if tx_details_response.get('last_indexed_block') is None:
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False
        if not address_txs_response.get('actions') or not isinstance(address_txs_response.get('actions'), list):
            return False
        if address_txs_response.get('last_indexed_block') is None:
            return False
        return True

    @classmethod
    def validate_transfer(cls, transfer) -> bool:
        if not any(transfer.get(field) for field in
                   ['act', '@timestamp', 'block_id', 'block_num', 'trx_id']):
            return False
        act = transfer.get('act')
        if not any(act.get(field) for field in
                   ['name', 'data', 'account', 'authorization']):
            return False
        if act.get('name') == 'onerror':
            return False
        if act.get('name') != 'transfer' or act.get('account') != 'eosio.token':
            return False
        if not isinstance(act.get('data'), dict):
            return False
        act_data = act.get('data')
        if not any(act_data.get(field) for field in
                   ['from', 'to', 'symbol', 'quantity']):
            return False
        if act_data.get('symbol') != cls.symbol:
            return False
        if (not isinstance(act_data.get('quantity'), str)
                or not (' EOS') in act_data.get('quantity')):
            return False
        value = act_data.get('quantity').replace(' EOS', '').strip()
        if Decimal(str(value)) < cls.min_valid_tx_amount:
            return False
        if act_data.get('from') == act_data.get('to'):
            return False
        authorizations = act.get('authorization')
        for auth in authorizations:
            account_from = act.get('data').get('from')
            if account_from == auth.get('actor') and auth.get('permission') in ['active', 'owner']:
                break
        else:
            return False
        return True


class EosSwedenResponseParser(ResponseParser):
    validator = EosSwedenResponseValidator
    symbol = 'EOS'
    currency = Currencies.eos

    @classmethod
    def parse_balance_response(cls, balance_response) -> Decimal:
        if cls.validator.validate_balance_response(balance_response):
            value = balance_response.get('core_liquid_balance').replace(' EOS', '').strip()
            return Decimal(value)
        return Decimal('0')

    @classmethod
    def parse_transfer(cls, block_head, transfer):
        act_data = transfer.get('act').get('data')
        memo = act_data.get('memo') or ''
        tx_hash = transfer.get('trx_id')
        block_num = transfer.get('block_num')
        block_id = transfer.get('block_id')
        confirmations = block_head - block_num
        date = parse_iso_date(transfer.get('@timestamp') + 'Z')
        from_address = act_data.get('from')
        to_address = act_data.get('to')
        value = Decimal(str(act_data.get('quantity').replace(' EOS', '').strip()))
        transfer_tx = TransferTx(
            success=True,
            tx_hash=tx_hash,
            symbol=cls.symbol,
            from_address=from_address,
            to_address=to_address,
            value=value,
            date=date,
            block_hash=block_id,
            block_height=block_num,
            memo=memo,
            confirmations=confirmations
        )
        return transfer_tx

    @classmethod
    def parse_tx_details_response(cls, tx_details_response, block_head) -> List[TransferTx]:
        transfer_txs: List[TransferTx] = []
        if cls.validator.validate_tx_details_response(tx_details_response):
            block_head = tx_details_response.get('last_indexed_block')
            transfers = tx_details_response.get('actions')
            for transfer in transfers:
                if (cls.validator.validate_transfer(transfer)
                        and transfer.get('trx_id').casefold() == tx_details_response.get('trx_id').casefold()):
                    transfer_tx = cls.parse_transfer(block_head, transfer)
                    transfer_txs.append(transfer_tx)
        return transfer_txs

    @classmethod
    def parse_address_txs_response(cls, address, address_txs_response, block_head) -> List[TransferTx]:
        address_transfer_txs: List[TransferTx] = []
        if cls.validator.validate_address_txs_response(address_txs_response):
            block_head = address_txs_response.get('last_indexed_block')
            transfers = address_txs_response.get('actions')
            for transfer in transfers:
                if cls.validator.validate_transfer(transfer):
                    transfer_tx = cls.parse_transfer(block_head, transfer)
                    address_transfer_txs.append(transfer_tx)
        return address_transfer_txs


class EosSwedenApi(GeneralApi):
    parser = EosSwedenResponseParser
    _base_url = 'https://eos.eosusa.io'
    testnet_url = 'https://jungle.eosn.io'
    cache_key = 'eos'
    rate_limit = 0
    need_block_head_for_confirmation = False
    supported_requests = {
        'get_address_txs': '/v2/history/get_actions?account={address}&limit=50',
        'get_balance': '/v1/chain/get_account',
        'get_tx_details': '/v2/history/get_transaction?id={tx_hash}',
    }

    @classmethod
    def get_headers(cls):
        return {
            'User-Agent': 'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/95.0'
        } if not settings.IS_VIP else {
            'User-Agent': 'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/109.0'
        }

    @classmethod
    def get_balance_body(cls, address):
        return json.dumps({'account_name': address})
