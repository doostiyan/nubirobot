import json
import random
import time
from decimal import Decimal
from typing import Any, Optional

from django.conf import settings

from exchange.base.models import Currencies
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin


class FlowFlipsidecrypto(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: Flow
    API docs: https://docs.flipsidecrypto.com/shroomdk-sdk
    """
    rate_limit = 1.2  # 250 in 5 min
    PRECISION = 8
    min_valid_tx_amount = Decimal('0.0')
    symbol = 'FLOW'
    currency = Currencies.flow
    valid_contract = ['A.1654653399040a61.FlowToken']
    BLOCK_TIME = 2
    excluded_addresses = ['0x1bf2b9d59ad1ba04']
    supported_requests = {
        'get_query': '',
        'get_query_result': '/{query_token}',
    }

    _base_url = 'https://node-api.flipsidecrypto.com/queries'

    def get_api_key(self) -> str:
        return random.choice(settings.FLOW_SHROOM_API_KEYS)

    @property
    def headers(self) -> dict:
        return {'Accept': 'application/json', 'Content-Type': 'application/json', 'x-api-key': self.get_api_key()}

    def get_txs(self, address: str, **_: Any) -> list:
        txs = []
        query = f"""
            select * from flow.core.ez_token_transfers where RECIPIENT='{address}' order by BLOCK_HEIGHT DESC LIMIT 25
        """  # noqa: S608
        data = json.dumps({
            'sql': query,
            'ttlMinutes': 15
        })
        query_token = self.request('get_query', body=data)
        time.sleep(0.2)
        query_result = self.request('get_query_result', query_token=query_token.get('token'))
        if query_result.get('status') != 'finished':
            raise APIError(f'{self.symbol} API: Get Txs. Getting query result is not finished yet.')
        if query_result.get('results') is None:
            raise APIError(f'{self.symbol} API: Get Txs response is None')

        for tx in query_result.get('results'):
            if self.validate_transaction(tx):
                parsed_tx = self.parse_tx(tx, address)
                if parsed_tx:
                    txs.append(parsed_tx)
        return txs

    def validate_transaction(self, tx: list, _: Optional[str] = None) -> Any:
        if tx[5] not in self.valid_contract:
            return False
        #  Check self tx
        if tx[3] == tx[4]:
            return False
        if not self.validate_tx_amount(Decimal(str(tx[6]))):
            return False
        return tx[7]

    def parse_tx(self, tx: list, address: str, _: Optional[int] = None) -> dict:
        date = parse_iso_date(tx[1].replace(' ', 'T') + 'Z')
        amount = Decimal(str(tx[6]))
        if address == tx[3]:
            direction = 'outgoing'
            amount = -amount
        elif address == tx[4]:
            direction = 'incoming'
        else:
            return None
        if tx[3] in self.excluded_addresses:
            return None
        return {
            self.currency: {
                'address': address,
                'hash': tx[2],
                'from_address': [tx[3]],
                'to_address': tx[4],
                'amount': amount,
                'block': tx[0],
                'date': date,
                'confirmations': self.estimate_confirmation_by_date(date),
                'direction': direction,
                'raw': tx
            }
        }
