from decimal import Decimal
from typing import Dict, List, Optional

from exchange.base.models import Currencies
from exchange.base.parsers import parse_utc_timestamp_ms
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.contracts_conf import TRC20_contract_currency, TRC20_contract_info
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin


class TronscanAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: tron
    API docs: https://github.com/tronscan/tronscan-frontend/blob/dev2019/document/api.md
    Explorer: https://tronscan.org
    """

    active = True

    symbol = 'TRX'
    _base_url = 'https://apilist.tronscan.org/api'
    rate_limit = 0
    PRECISION = 6
    max_items_per_page = None
    page_offset_step = None
    confirmed_num = None
    min_valid_tx_amount = Decimal('0.001')
    USE_PROXY = False

    supported_requests = {
        'get_balance': '/account?address={address}',
        'get_transactions':
            '/transfer?sort=-timestamp&count=true&limit={limit}&start={start}&token={token}&address={address}',
        'get_token_txs': '/token_trc20/transfers?limit=40&start=0&sort=-timestamp&count=true&relatedAddress={address}',
        'get_tx_details': '/transaction-info?hash={tx_hash}',
        'get_latest_block': '/block/statistic'

    }

    def get_name(self) -> str:
        return 'trx_tronscan'

    @property
    def contract_currency_list(self) -> dict:
        return TRC20_contract_currency.get(self.network)

    @property
    def contract_info_list(self) -> dict:
        return TRC20_contract_info.get(self.network)

    def contract_currency(self, token_address: str) -> dict:
        return self.contract_currency_list.get(token_address)

    def contract_info(self, currency: int) -> dict:
        return self.contract_info_list.get(currency)

    def get_account_info(self, address: str) -> dict:
        self.validate_address(address)
        response = self.request('get_balance', address=address)
        if response is None:
            raise APIError(f'[TronscanAPI][{self.symbol}][Get Balance] response is None')
        if response.get('error'):
            raise APIError(f'[TronscanAPI][{self.symbol}][Get Balance] unsuccessful')
        return {
            'balance': response.get('balance'),
            'staked_balance': response.get('totalFrozen'),
            'reward': response.get('rewardNum')
        }

    def get_staking_info(self, address: str) -> dict:
        account_info = self.get_account_info(address)
        if (account_info.get('balance') is None
                or account_info.get('staked_balance') is None
                or account_info.get('reward') is None):
            raise APIError(f'[TronscanAPI][{self.symbol}][Get Staking Info] unsuccessful')
        return {
            'balance': self.from_unit(account_info.get('balance')),
            'staked_balance': self.from_unit(account_info.get('staked_balance')),
            'reward': self.from_unit(account_info.get('reward'))
        }

    def get_balance(self, address: str) -> dict:
        raw_balance = self.get_account_info(address).get('balance')
        if raw_balance is None:
            raise APIError(f'[TronscanAPI][{self.symbol}][Get Balance] unsuccessful')
        return {
            'amount': self.from_unit(raw_balance)
        }

    def get_txs(self, address: str) -> List[Dict[str, any]]:
        self.validate_address(address)
        response = self.request('get_transactions', address=address, limit=25, start=0, token='_')  # noqa: S106
        if response is None:
            raise APIError(f'[TronscanAPI][{self.symbol}][Get Transactions] response is None')
        txs = response.get('data')
        if txs is None:
            return []

        transactions = []
        for tx in txs:
            parsed_tx = self.parse_tx(tx, address)
            if parsed_tx is not None:
                transactions.append(parsed_tx)
        return transactions

    def parse_tx(self, tx: dict, address: str) -> Optional[Dict[str, any]]:
        if tx.get('contractRet') != 'SUCCESS' or tx.get('revert'):
            return None
        if tx.get('tokenName') != '_':  # token: '_' shows only TRX transfers;
            return None

        raw_value = tx.get('amount')
        if not raw_value:
            return None
        value = self.from_unit(raw_value)
        if value < self.min_valid_tx_amount:
            return None
        if tx.get('transferFromAddress') == address:  # is send.
            value = -value
        elif tx.get('transferToAddress') == address:  # is receive.
            pass
        else:
            return None
        if tx.get('transferFromAddress') == tx.get('transferToAddress'):
            return None

        if tx.get('transferFromAddress') in ['TM9RwJndZHmDVLSZcY6J76ci22AzPp2krj',
                                             'TVCAuYMw5afP96y5Wep866AXVWZJRH8fdo']:
            return None

        confirmations = 20 if tx.get('confirmed') else 0
        return {
            'hash': tx.get('transactionHash'),
            'from_address': tx.get('transferFromAddress'),
            'date': parse_utc_timestamp_ms(tx.get('timestamp')),
            'amount': value,
            'confirmations': confirmations,
            'block': tx.get('block'),
            'raw': tx,
            'memo': None
        }

    def parse_token_txs(self, data: dict) -> any:
        return data.get('token_transfers')

    def validate_token_transaction(self, tx: dict, currency: int) -> bool:
        if tx.get('contract_type') != 'trc20':
            return False
        if tx.get('contractRet') != 'SUCCESS' or tx.get('finalResult') != 'SUCCESS':
            return False
        if not tx.get('confirmed'):
            return False
        if tx.get('revert'):
            return False
        if not tx.get('trigger_info'):
            return False
        if tx.get('trigger_info').get('methodName') != 'transfer':
            return False
        if tx.get('trigger_info').get('data')[:8] != 'a9059cbb':  # Indicates 'transfer' transactions
            return False

        contract_currency = self.contract_currency(tx.get('trigger_info').get('contract_address'))
        if contract_currency is None:
            return False
        if contract_currency != currency:
            return False
        contract = self.contract_info(currency)
        if contract.get('address') != tx.get('trigger_info').get('contract_address'):
            return False
        if contract.get('address') != tx.get('contract_address'):
            return False

        return True

    def parse_token_tx(self, tx: dict, address: str) -> Optional[dict]:
        if (tx.get('trigger_info').get('parameter').get('_to') or tx.get('trigger_info').get('parameter').get(
                'dst')) != address:
            return None
        if tx.get('to_address') != address:
            return None

        deposit_black_list_addresses = ['TM9RwJndZHmDVLSZcY6J76ci22AzPp2krj', 'TVCAuYMw5afP96y5Wep866AXVWZJRH8fdo']
        if tx.get('from_address') in deposit_black_list_addresses:
            return None

        currency = self.contract_currency(tx.get('trigger_info').get('contract_address'))
        if currency is None:
            return None
        contract_info = self.contract_info(currency)

        value = (tx.get('trigger_info').get('parameter').get('_value')
                 or tx.get('trigger_info').get('parameter').get('sad'))
        if not value:
            return None
        return {
            'hash': tx.get('transaction_id'),
            'from_address': tx.get('from_address'),
            'date': parse_utc_timestamp_ms(tx.get('block_ts')),
            'amount': self.from_unit(int(value), contract_info.get('decimals')),
            'confirmations': 20 if tx.get('confirmed') else 0,
            'block': tx.get('block'),
            'raw': tx,
            'memo': None
        }

    def get_tx_details(self, tx_hash: str) -> dict:
        response = self.request('get_tx_details', tx_hash=tx_hash)
        if not response:
            raise APIError('Response is none')
        return self.parse_tx_details(response)

    def parse_tx_details(self, tx_info: dict) -> dict:
        transfers = []
        amount = tx_info.get('contractData', {}).get('amount')
        success = True
        if tx_info.get('contractRet') != 'SUCCESS' or tx_info.get('revert'):
            success = False
        if amount and not tx_info.get('contractData', {}).get('tokenInfo'):
            transfers.append({
                'type': 'MainCoin',
                'symbol': self.symbol,
                'currency': Currencies.trx,
                'from': tx_info.get('ownerAddress'),
                'to': tx_info.get('toAddress'),
                'value': self.from_unit(amount, self.PRECISION),
                'is_valid': success,
            })
        for transfer in tx_info.get('trc20TransferInfo', []):
            if transfer.get('type') == 'Transfer' and tx_info.get('contract_type') == 'trc20':
                currency = self.contract_currency(transfer.get('contract_address'))
                contract_info = self.contract_info(currency)
                if not currency:
                    continue
                transfers.append({
                    'type': 'TRC20',
                    'symbol': transfer.get('symbol'),
                    'currency': currency,
                    'from': transfer.get('from_address'),
                    'to': transfer.get('to_address'),
                    'value': self.from_unit(int(transfer.get('amount_str')), contract_info.get('decimals')),
                    'token': transfer.get('contract_address'),
                    'name': transfer.get('name', ''),
                    'is_valid': success
                })
        return {
            'hash': tx_info.get('hash'),
            'success': success,
            'is_valid': len(transfers) > 0,
            'revert': tx_info.get('revert'),
            'inputs': [],
            'outputs': [],
            'transfers': transfers,
            'block': tx_info.get('block'),
            'confirmations': tx_info.get('confirmations'),
            'fees': self.from_unit(tx_info.get('cost').get('energy_usage_total') or 0),
            'date': parse_utc_timestamp_ms(tx_info.get('timestamp')),
        }

    def check_block_status(self) -> dict:
        response = self.request('get_latest_block')
        if not response:
            raise APIError('[TronscanAPI][CheckStatus] Response is None.')
        return {'blockNum': response.get('whole_block_count')}

    def get_block_head(self) -> any:
        block = self.check_block_status()
        return block.get('blockNum')
