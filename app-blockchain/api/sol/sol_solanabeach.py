import random
from decimal import Decimal
from typing import Any, Optional, Union

from django.conf import settings

from exchange.base.models import Currencies
from exchange.base.parsers import parse_timestamp
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.utils import AddressNotExist, APIError, BlockchainUtilsMixin


class SolanaBeachAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    solanabeach API explorer.
    supported coins: solana
    API docs: https://app.swaggerhub.com/apis-docs/V2261/solanabeach-backend_api/0.0.1
    Explorer:
    """

    _base_url = 'https://api.solanabeach.io/'
    rate_limit = 0.1  # (100 req/sec)

    symbol = 'SOL'
    cache_key = 'sol'
    active = True
    currency = Currencies.sol
    PRECISION = 9

    supported_requests = {
        'get_balance': 'v1/account/{address}',
        'get_tx': 'v1/transaction/{tx_hash}',
        'get_txs': 'v1/account/{address}/transactions?limit={limit}',
        'get_status': 'v1/health',
        'get_stake_account': 'v1/account/{address}/stakes?limit=1&offset=0',
    }

    def get_name(self) -> str:
        return 'beach_api'

    def get_api_key(self) -> str:
        return random.choice(settings.SOLANABEACH_API_KEY)

    def get_header(self) -> dict:
        return {
            'accept': 'application/json',
            'Authorization': 'Bearer ' + self.get_api_key(),
        }

    def get_balance(self, address: str) -> dict:
        response = self.request('get_balance', address=address, headers=self.get_header(), apikey=self.get_api_key())
        if not response:
            raise APIError('[SolanaBeachAPI][GetBalance] Response is None.')
        if response.get('error'):
            message = '[SolanaBeachAPI][GetBalance]' + response.get('error').get('message')
            raise APIError(message)

        amount = self.from_unit(response.get('value').get('base').get('balance'))
        return {
            self.currency: {
                'amount': amount,
                'unconfirmed_amount': Decimal('0'),
                'address': address
            }
        }

    def get_tx_details(self, tx_hash: str) -> dict:
        response = self.request('get_tx', tx_hash=tx_hash, headers=self.get_header(), apikey=self.get_api_key())
        if not response:
            raise APIError('[SolanaBeachAPI][get_tx]Response is none')
        current_block = self.get_current_block()
        return self.parse_tx_without_address(response, current_block)

    def parse_tx_without_address(self, tx: dict, current_block: int) -> dict:
        transfers = []
        err = tx.get('meta').get('err', None)
        status = bool(err is None and tx.get('valid'))

        if not status:
            return {
                'hash': tx.get('transactionHash'),
                'success': False,
                'is_valid': False,
                'transfers': transfers,
                'inputs': [],
                'outputs': [],
                'raw': tx,
            }
        date = parse_timestamp(tx.get('blocktime').get('absolute'))

        block = tx.get('blockNumber')
        confirmation = current_block - block
        for transaction in tx.get('instructions'):
            if transaction.get('parsed') is None:
                continue
            if transaction.get('programId').get('name') == 'System Program' and \
                    transaction.get('parsed').get('Transfer', None):
                amount = self.from_unit(int(transaction.get('parsed').get('Transfer').get('lamports')))
                if amount == 0:
                    continue
                from_address = transaction.get('parsed').get('Transfer').get('account').get('address')
                to_address = transaction.get('parsed').get('Transfer').get('recipient').get('address')
                if from_address == to_address:
                    continue
                transfers.append({
                    'type': 'MainCoin',
                    'symbol': self.symbol,
                    'currency': self.currency,
                    'from': from_address,
                    'to': to_address,
                    'value': amount,
                    'is_valid': True,
                })
        return {
            'hash': tx.get('transactionHash'),
            'success': status,
            'is_valid': status,
            'transfers': transfers,
            'inputs': [],
            'outputs': [],
            'block': block,
            'confirmations': confirmation,
            'date': date,
            'raw': tx,
        }

    def parse_tx(self, tx: dict, address: str, current_block: int) -> list:
        direction = 'incoming'
        transfers = []
        err = tx.get('meta').get('err', None)
        status = bool(err is None and tx.get('valid'))

        if not status:
            return None
        date = parse_timestamp(tx.get('blocktime').get('absolute'))

        block = tx.get('blockNumber')
        tx_hash = tx.get('transactionHash')
        if block > 143835685:  # noqa: PLR2004
            tx_hash = tx_hash.strip()
        confirmation = current_block - block
        for transaction in tx.get('instructions'):
            if transaction.get('parsed') is None:
                continue
            if transaction.get('programId').get('name') == 'System Program' and \
                    transaction.get('programId').get('address') == '11111111111111111111111111111111' and \
                    transaction.get('parsed').get('Transfer', None):
                amount = self.from_unit(int(transaction.get('parsed').get('Transfer').get('lamports')))
                from_address = transaction.get('parsed').get('Transfer').get('account').get('address')
                to_address = transaction.get('parsed').get('Transfer').get('recipient').get('address')
                if from_address == to_address:
                    continue
                if address == from_address:
                    amount = - amount
                    direction = 'outgoing'
                elif address != to_address:
                    continue
                transfers.append({
                    'block': block,
                    'date': date,
                    'confirmations': confirmation,
                    'hash': tx_hash,
                    'from_address': from_address,
                    'to_address': to_address,
                    'amount': amount,
                    'direction': direction,
                    'raw': tx
                })
        return transfers

    def get_txs(self, address: str, limit: int = 20) -> list:
        response = self.request('get_txs', address=address, limit=limit, headers=self.get_header(),
                                apikey=self.get_api_key())
        current_block = self.get_current_block()
        transfers = []
        for tx in response:
            try:
                transfer = self.parse_tx(tx, address, current_block)
            except APIError:
                continue
            if transfer:
                transfers.extend(transfer)
        return transfers

    def get_current_block(self) -> Any:
        response = self.request('get_status', headers=self.get_header(), apikey=self.get_api_key())
        if not response:
            raise APIError('[SolanaBeachAPI][get_current_block] response is None')

        if response.get('currentSlot', None) is None:
            raise APIError('[SolanaBeachAPI][get_current_block] response is None')

        return response.get('currentSlot')

    def get_stake_account_info(self, address: str) -> str:
        response = self.request('get_stake_account', address=address, headers=self.get_header(),
                                apikey=self.get_api_key())
        try:
            if not response.get('data'):
                raise AddressNotExist(
                    '[SolanaBeachAPI][get_stake_account_info] Address does NOT support stake address!')
            stake_address = response.get('data')[0].get('pubkey').get('address')
        except AttributeError as e:
            raise APIError(f'{self.symbol} API: Failed to get stake address.') from e

        return stake_address

    def get_delegated_balance(self, address: str) -> Optional[Union[int, Decimal]]:
        response = self.request('get_txs', address=address, limit=25, headers=self.get_header(),
                                apikey=self.get_api_key())
        if not response:
            raise APIError('[SolanaBeachAPI][get_delegated_balance] response is None')
        try:
            for tx in response:
                if self.validate_staking_transaction(tx):
                    return self.parse_staking_tx(tx, address)
            return None
        except AttributeError as e:
            raise APIError(f'{self.symbol} API: Failed to get delegated balance.') from e

    def parse_staking_tx(self, tx: dict, address: str) -> Union[int, Decimal]:
        for index, account in enumerate(tx.get('accounts')):
            if account.get('account').get('address') == address:
                break
            index += 1  # noqa: PLW2901
        try:
            # post balance is the balance after the transaction has occurred and
            # the amount have been added to account's balance
            post_balance = tx.get('meta').get('postBalances')[index]
            # pre balance is the account balance before this transaction
            pre_balance = tx.get('meta').get('preBalances')[index]
            delegated_value = post_balance - pre_balance
        except IndexError as e:
            raise APIError(f'{self.symbol} API: Failed to parse staking transaction.') from e
        return self.from_unit(delegated_value)

    @staticmethod
    def validate_staking_transaction(tx: dict) -> bool:
        if tx.get('mostImportantInstruction').get('name') == 'Delegate':
            return True
        return False
