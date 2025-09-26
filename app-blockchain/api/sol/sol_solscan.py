import random
from decimal import Decimal
from typing import Any, List, Optional

from django.conf import settings

from exchange.base.models import Currencies
from exchange.base.parsers import parse_timestamp
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin


class SolScanAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    solscan API explorer.
    supported coins: solana
    API docs:
    https://public-api.solscan.io/docs/
    Explorer:
    https://solscan.io/
    """

    _base_url = 'https://public-api.solscan.io'
    rate_limit = 0.2  # (5 req/sec)

    symbol = 'SOL'
    cache_key = 'sol'
    active = True
    currency = Currencies.sol
    PRECISION = 9

    max_limit = 50  # 50 for account transactions history

    supported_requests = {
        'get_balance': '/account/{address}',
        'get_tx': '/transaction/{tx_hash}',
        'get_txs': '/account/solTransfers?account={address}&offset={offset}&limit={limit}',
        'get_status': '/chaininfo/',
        'get_stake_account': '/account/stakeAccounts?account={address}'
    }

    def get_name(self) -> str:
        return 'scan_api'

    def get_header(self) -> dict:
        return {
            'accept': 'application/json',
            'token': random.choice(settings.SOLSCAN_APIKEY)
        }

    def get_balance(self, address: str) -> dict:
        response = self.request('get_balance', address=address, headers=self.get_header())
        if not response:
            raise APIError('[SolscanAPI][GetBalance] Response is None.')
        if response.get('error'):
            message = '[SolscanAPI][GetBalance]' + response.get('error').get('message')
            raise APIError(message)

        amount = self.from_unit(response.get('lamports'))
        return {
            self.currency: {
                'amount': amount,
                'unconfirmed_amount': Decimal('0'),
                'address': address
            }
        }

    def get_tx_details(self, tx_hash: str) -> dict:
        response = self.request('get_tx', tx_hash=tx_hash, headers=self.get_header())
        is_valid = False
        success = False
        if not response:
            raise APIError('[SolscanAPI][get_tx]Response is none')
        if response.get('status') == 'Success':
            success = True
        if response.get('solTransfers'):
            is_valid = True
        return self.parse_tx_details(response, is_valid, success)

    def parse_tx_details(self, tx: dict, is_valid: bool, success: bool) -> dict:
        current_block = self.get_current_block()
        transfers = []
        for transfer in tx.get('solTransfers'):
            transfer_information = {
                'type': 'MainCoin',
                'symbol': self.symbol,
                'currency': self.currency,
                'from': transfer.get('source'),
                'to': transfer.get('destination'),
                'value': self.from_unit(int(transfer.get('amount'))),
                'is_valid': is_valid,
            }
            transfers.append(transfer_information)
        return {
            'hash': tx.get('txHash'),
            'success': success,
            'is_valid': success and is_valid,
            'transfers': transfers,
            'inputs': [],
            'outputs': [],
            'block': tx.get('slot'),
            'confirmations': current_block - tx.get('slot'),
            'fees': self.from_unit(tx.get('fee')),
            'date': parse_timestamp(tx.get('blockTime')),
            'raw': tx,
        }

    def get_txs(self, address: str, limit: int = 25, offset: int = 0) -> List[dict]:
        transfers = []
        if limit > self.max_limit:
            raise APIError('[SolscanAPI][get_txs]More than possible limit requested')

        response = self.request('get_txs', address=address, offset=offset, limit=limit, headers=self.get_header())
        if not response:
            raise APIError('[SolscanAPI][get_txs]Response is none')

        transactions = response.get('data')
        if not transactions:
            return []

        block_head = self.get_current_block()
        for transfer in transactions:
            parsed_transfer = self.parse_tx(transfer, address, block_head)
            if parsed_transfer:
                transfers.append(parsed_transfer)
        return transfers

    def parse_tx(self, transfer: dict, address: str, block_head: int) -> Optional[dict]:
        direction = 'incoming'
        if transfer.get('status') != 'Success':
            return None
        amount = self.from_unit(int(transfer.get('lamport')))
        if amount == 0:
            return None
        if transfer.get('src') == transfer.get('dst'):
            return None
        if address == transfer.get('src'):
            amount = - amount
            direction = 'outgoing'
        elif address != transfer.get('dst'):
            return None
        return {
            'from_address': transfer.get('src'),
            'to_address': transfer.get('dst'),
            'amount': amount,
            'block': transfer.get('slot'),
            'confirmations': block_head - transfer.get('slot'),
            'date': parse_timestamp(transfer.get('blockTime')),
            'hash': transfer.get('txHash'),
            'direction': direction,
            'raw': transfer
        }

    def get_current_block(self) -> Any:
        response = self.request('get_status', headers=self.get_header())
        if not response:
            raise APIError('[SolScanAPI][get_current_block] response is None')
        block = response.get('absoluteSlot')
        if not block:
            raise APIError('[SolScanAPI][get_current_block] Empty info')
        return block

    def get_stake_account_info(self, address: str) -> List[Any]:
        response = self.request('get_stake_account', address=address, headers=self.get_header())
        if not response:
            raise APIError(f'{self.symbol} [get_stake_account_info] Response is None!')
        try:
            stake_addresses = list(response)
        except AttributeError as e:
            raise APIError(f'{self.symbol} API: Failed to get stake address!') from e
        return stake_addresses
