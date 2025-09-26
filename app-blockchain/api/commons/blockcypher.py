import random
from decimal import Decimal
from typing import Dict, List, Optional

from django.conf import settings

from exchange.blockchain.api.general.dtos.dtos import Balance, TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from blockchain.parsers import parse_iso_date
else:
    from exchange.base.parsers import parse_iso_date


class BlockcypherValidator(ResponseValidator):
    # We also have this script type for some transfers: pay-to-script-hash.
    # These transfers are validated in block_book( not specifically by this script type, maybe sth else).
    # I think if it's good to have this type to if it doesn't make problems.
    # The reason is that we are gathering transfers values in our new method and missing some of these transfers
    # will destruct our new method.
    valid_script_types = ['pay-to-pubkey-hash', 'pay-to-witness-script-hash', 'pay-to-witness-pubkey-hash']

    @classmethod
    def validate_balance_response(cls, balance_response: any) -> bool:
        if not balance_response or not isinstance(balance_response, dict):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Optional[Dict[str, any]]) -> bool:
        if not tx_details_response or not isinstance(tx_details_response, dict):
            return False
        if not tx_details_response.get('block_hash') or not isinstance(tx_details_response.get('block_hash'), str):
            return False
        if not tx_details_response.get('block_height') or not isinstance(tx_details_response.get('block_height'), int):
            return False
        if tx_details_response.get('block_height') == -1:
            return False
        if not tx_details_response.get('confirmations') or not isinstance(tx_details_response.get('confirmations'),
                                                                          int):
            return False
        if tx_details_response.get('confirmations') < 1:
            return False
        if not tx_details_response.get('hash') or not isinstance(tx_details_response.get('hash'), str):
            return False
        if tx_details_response.get('fees') is None or not isinstance(tx_details_response.get('fees'), int):
            return False
        if tx_details_response.get('execution_error'):
            return False
        if not tx_details_response.get('confirmed') or not isinstance(tx_details_response.get('confirmed'), str):
            return False
        if (tx_details_response.get('double_spend') is None or
                not isinstance(tx_details_response.get('double_spend'), bool)):
            return False
        if tx_details_response.get('double_spend'):
            return False
        if not tx_details_response.get('inputs') or not isinstance(tx_details_response.get('inputs'), list):
            return False
        if not tx_details_response.get('outputs') or not isinstance(tx_details_response.get('outputs'), list):
            return False
        return True

    @classmethod
    def validate_transfer(cls, transfer: Dict[str, any]) -> bool:
        if not transfer.get('addresses') or not isinstance(transfer.get('addresses'), list):
            return False
        if not transfer.get('addresses')[0] or not isinstance(transfer.get('addresses')[0], str):
            return False
        if not transfer.get('script_type') or not isinstance(transfer.get('script_type'), str):
            return False
        if transfer.get('script_type') not in cls.valid_script_types:
            return False
        if transfer.get('output_value') and isinstance(transfer.get('output_value'), int):
            return True

        return transfer.get('value') and isinstance(transfer.get('value'), int)


class BlockcypherParser(ResponseParser):
    validator = BlockcypherValidator
    precision = 8

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, any]) -> Balance:
        if cls.validator.validate_balance_response(balance_response):
            return Balance(
                balance=BlockchainUtilsMixin.from_unit(
                    number=balance_response.get('balance', 0),
                    precision=cls.precision
                ),
                unconfirmed_balance=BlockchainUtilsMixin.from_unit(
                    number=balance_response.get('unconfirmed_balance', 0),
                    precision=cls.precision,
                    negative_value=True
                ),
            )
        return Balance(
            balance=Decimal('0'),
            unconfirmed_balance=Decimal('0')
        )

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Dict[str, any], _: int) -> List[TransferTx]:
        transfers: List[TransferTx] = []
        if cls.validator.validate_tx_details_response(tx_details_response):
            block_hash = tx_details_response.get('block_hash')
            block_height = tx_details_response.get('block_height')
            tx_hash = tx_details_response.get('hash')
            tx_fee = BlockchainUtilsMixin.from_unit(tx_details_response.get('fees'), cls.precision)
            date = parse_iso_date(tx_details_response.get('confirmed'))
            confirmations = tx_details_response.get('confirmations')
            for transfer in tx_details_response.get('inputs'):
                if cls.validator.validate_transfer(transfer):
                    from_address = transfer.get('addresses')[0]
                    value = BlockchainUtilsMixin.from_unit(transfer.get('output_value'), cls.precision)
                    for tx in transfers:
                        if tx.from_address == from_address:
                            tx.value += value
                            break
                    else:
                        transfers.append(
                            TransferTx(
                                tx_hash=tx_hash,
                                success=True,
                                from_address=from_address,
                                to_address='',
                                value=value,
                                symbol=cls.symbol,
                                confirmations=confirmations,
                                block_height=block_height,
                                block_hash=block_hash,
                                date=date,
                                tx_fee=tx_fee,
                            )
                        )
            for transfer in tx_details_response.get('outputs'):
                if cls.validator.validate_transfer(transfer):
                    to_address = transfer.get('addresses')[0]
                    value = BlockchainUtilsMixin.from_unit(transfer.get('value'), cls.precision)
                    for tx in transfers:
                        if tx.from_address == to_address:
                            tx.value -= value
                            break
                        if tx.to_address == to_address:
                            tx.value += value
                            break
                    else:
                        transfers.append(
                            TransferTx(
                                tx_hash=tx_hash,
                                success=True,
                                from_address='',
                                to_address=to_address,
                                value=value,
                                symbol=cls.symbol,
                                confirmations=confirmations,
                                block_height=block_height,
                                block_hash=block_hash,
                                date=date,
                                tx_fee=tx_fee,
                            )
                        )
        return transfers


class BlockcypherApi(GeneralApi):
    """coins: Doge, Btc, Ltc, Eth, Dash."""

    parser = BlockcypherParser
    _base_url = 'https://api.blockcypher.com'
    need_block_head_for_confirmation = False
    supported_requests = {
        'get_balance': '/v1/{network}/main/addrs/{address}/full?limit=1',
        'get_tx_details': '/v1/{network}/main/txs/{tx_hash}?outstart=0&limit=5000&token={token}',
    }
    rate_limit = 0.34
    XPUB_SUPPORT = False

    def get_name(self) -> str:
        return f'{self.symbol.lower()}_blockcypher'

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice(settings.BLOCKCYPHER_API_KEYS)

    @classmethod
    def get_balance(cls, address: str) -> Optional[str]:
        return cls.request(request_method='get_balance', address=address, network=cls.parser.symbol.lower())

    @classmethod
    def get_tx_details(cls, tx_hash: str) -> Optional[str]:
        token = cls.get_api_key()
        return cls.request(request_method='get_tx_details', tx_hash=tx_hash, network=cls.parser.symbol.lower(),
                           token=token)
