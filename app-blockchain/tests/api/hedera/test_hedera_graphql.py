from unittest import TestCase
from unittest.mock import Mock

import pytest
from _decimal import Decimal
from django.conf import settings

from exchange.blockchain.explorer_original import BlockchainExplorer

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.hedera.hedera_explorer_interface import HederaExplorerInterface
from exchange.blockchain.api.hedera.hedera_graphql import GraphqlHederaApi


@pytest.mark.slow
class TestGraphQlHederaApiCalls(TestCase):
    api = GraphqlHederaApi
    general_api = HederaExplorerInterface.get_api()

    addresses_of_account = ['0.0.38674']
    # hash of transactions in order of success,invalid,failed
    hash_of_transactions = ['0.0.1070126-1662368439-606540089', '0.0.1199492-1662207708-502359890',
                            '0.0.14622-1662367091-224352244',
                            '0.0.911748-1661769086-456664222']
    address_txs = ['0.0.407219', '0.0.38674']

    @classmethod
    def check_general_response(cls, response, keys):
        if set(response.keys()).issubset(keys):
            return True
        return False

    def test_get_balance_api(self):
        keys = {'account', 'alias', 'auto_renew_period', 'balance', 'created_timestamp', 'decline_reward', 'deleted',
                'ethereum_nonce', 'evm_address', 'expiry_timestamp', 'key', 'max_automatic_token_associations', 'memo',
                'pending_reward', 'receiver_sig_required', 'staked_account_id', 'staked_node_id', 'stake_period_start',
                'transactions', 'links'}
        balance_keys = {'timestamp', 'balance', 'tokens'}
        for address in self.addresses_of_account:
            get_balance_result = self.api.get_balance(address)
            assert self.check_general_response(get_balance_result, keys)
            assert len(get_balance_result.get('balance')) > 0
            assert self.check_general_response(get_balance_result.get('balance'), balance_keys)
            assert isinstance(get_balance_result.get('balance').get('balance'), int)

    def test_get_address_txs_api(self):
        address_keys = {'account', 'alias', 'auto_renew_period', 'balance', 'created_timestamp', 'decline_reward',
                        'deleted',
                        'ethereum_nonce', 'evm_address', 'expiry_timestamp', 'key', 'max_automatic_token_associations',
                        'memo',
                        'pending_reward', 'receiver_sig_required', 'staked_account_id', 'staked_node_id',
                        'stake_period_start',
                        'transactions', 'links'}
        transaction_keys = {'bytes', 'charged_tx_fee', 'consensus_timestamp', 'entity_id', 'max_fee', 'memo_base64',
                            'name',
                            'nft_transfers', 'node', 'nonce', 'parent_consensus_timestamp', 'result', 'scheduled',
                            'staking_reward_transfers', 'token_transfers', 'transaction_hash', 'transaction_id',
                            'transfers',
                            'valid_duration_seconds', 'valid_start_timestamp'}
        transfer_keys = {'account', 'amount', 'is_approval'}
        for address in self.addresses_of_account:
            get_address_txs_response = self.api.get_address_txs(address)
            assert self.check_general_response(get_address_txs_response, address_keys)
            assert len(get_address_txs_response) > 0
            if get_address_txs_response.get('transactions'):
                for transaction in get_address_txs_response.get('transactions'):
                    if len(transaction.get('transfers')) != 0:
                        assert self.check_general_response(transaction, transaction_keys)
                        for transfer in transaction.get('transfers'):
                            assert self.check_general_response(transfer, transfer_keys)

    def test_get_tx_details_api(self):
        transaction_keys = {'bytes', 'charged_tx_fee', 'consensus_timestamp', 'entity_id', 'max_fee', 'memo_base64',
                            'name',
                            'nft_transfers', 'node', 'nonce', 'parent_consensus_timestamp', 'result', 'scheduled',
                            'staking_reward_transfers', 'token_transfers', 'transaction_hash', 'transaction_id',
                            'transfers',
                            'valid_duration_seconds', 'valid_start_timestamp'}
        transfer_keys = {'account', 'amount', 'is_approval'}
        for tx_hash in self.hash_of_transactions:
            get_tx_details_response = self.api.get_tx_details(tx_hash)
            assert len(get_tx_details_response.get('transactions')) != 0
            assert len(get_tx_details_response.get('transactions')[0]) != 0
            if len(get_tx_details_response.get('transactions')[0].get('transfers')) != 0:
                assert self.check_general_response(get_tx_details_response.get('transactions')[0], transaction_keys)
                for transfer in get_tx_details_response.get('transactions')[0].get('transfers'):
                    assert self.check_general_response(transfer, transfer_keys)


class TestGraphQlHederaFromExplorer(TestCase):
    api = GraphqlHederaApi
    currency = 112
    addresses_of_account = ['0.0.38674']

    def test_get_balance(self):
        balance_mock_response = [
            {'account': '0.0.38674', 'alias': None, 'auto_renew_period': 7890000,
             'balance': {'balance': 99822707, 'timestamp': '1693293025.965282550', 'tokens': []},
             'created_timestamp': '1585151076.224539000', 'decline_reward': False, 'deleted': False,
             'ethereum_nonce': 0, 'evm_address': '0x0000000000000000000000000000000000009712',
             'expiry_timestamp': '1593041076.224539000',
             'key': {'_type': 'ED25519', 'key': '0fcd6d40e313a3aa2cbd9f34104e57fc4f55883367a46984eb8e8b6a6b8c3565'},
             'max_automatic_token_associations': 0, 'memo': '', 'pending_reward': 0, 'receiver_sig_required': None,
             'staked_account_id': None, 'staked_node_id': None, 'stake_period_start': None, 'transactions': [
                {'bytes': None, 'charged_tx_fee': 177293, 'consensus_timestamp': '1693071002.765298003',
                 'entity_id': None, 'max_fee': '500000', 'memo_base64': '', 'name': 'CRYPTOTRANSFER',
                 'nft_transfers': [], 'node': '0.0.12', 'nonce': 0, 'parent_consensus_timestamp': None,
                 'result': 'SUCCESS', 'scheduled': False, 'staking_reward_transfers': [], 'token_transfers': [],
                 'transaction_hash': 'TPw9HwmOQWtJkDzaAYXQcZILd2U52cc7Afzvbon/QkgiYSSNi7pfES6UINSu5x5O',
                 'transaction_id': '0.0.38674-1693070991-154468439',
                 'transfers': [{'account': '0.0.12', 'amount': 7181, 'is_approval': False},
                               {'account': '0.0.98', 'amount': 170112, 'is_approval': False},
                               {'account': '0.0.38674', 'amount': -2809388810589, 'is_approval': False},
                               {'account': '0.0.1454258', 'amount': 2809388633296, 'is_approval': False}],
                 'valid_duration_seconds': '120', 'valid_start_timestamp': '1693070991.154468439'}],
             'links': {'next': '/api/v1/accounts/0.0.38674?limit=1&timestamp=lt:1693071002.765298003'}}]
        self.api.request = Mock(side_effect=balance_mock_response)
        HederaExplorerInterface.balance_apis[0] = self.api
        balances = BlockchainExplorer.get_wallets_balance({'HBAR': self.addresses_of_account}, Currencies.hbar)
        expected_balances = [
            {'address': '0.0.38674', 'balance': Decimal('0.99822707'), 'received': Decimal('0.99822707'),
             'rewarded': Decimal('0'), 'sent': Decimal('0')}]
        for balance, expected_balance in zip(balances.get(Currencies.hbar), expected_balances):
            assert balance == expected_balance
