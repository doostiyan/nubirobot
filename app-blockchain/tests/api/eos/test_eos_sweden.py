import datetime
from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

import pytest
from django.conf import settings
from pytz import UTC

from exchange.blockchain.apis_conf import APIS_CONF

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.explorer_original import BlockchainExplorer
from exchange.blockchain.api.eos.eos_explorer_interface import EosExplorerInterface

from exchange.blockchain.api.eos.new_eos_sweden import EosSwedenApi


@pytest.mark.slow
class TestEosSwedenApiCalls(TestCase):
    api = EosSwedenApi
    addresses_of_account = ['geytmmrvgene',
                            'axygsk5vbquz',
                            ]
    hash_of_transactions = ['139a3feebed6eb9a93be9d5e64eca5ce6265022715584384f20d6d2635c43591',
                            '1b613521679c3c51de24b50a1b5c1b707ff1991d922781dfdfa26d53bd6c26b9',
                            '2062e1b8ca7832cd3f442c56228d430885b9ff6a413906b30638ee90bed90b25',
                            '4f2287a8f7fb63b241100738a030ea9e3a5634b188cce299fa9d0ab9d1534406',
                            ]

    @classmethod
    def check_general_response(cls, response, keys):
        if set(response.keys()).issubset(keys):
            return True
        return False

    def test_get_balance_api(self):

        keys = {'account_name', 'head_block_num', 'head_block_time', 'privileged', 'last_code_update', 'created',
                'core_liquid_balance', 'ram_quota', 'net_weight', 'cpu_weight', 'net_limit', 'cpu_limit', 'ram_usage',
                'permissions', 'total_resources', 'self_delegated_bandwidth', 'refund_request', 'voter_info',
                'rex_info', 'subjective_cpu_bill_limit', 'eosio_any_linked_actions'}
        for address in self.addresses_of_account:
            get_balance_result = self.api.get_balance(address)
            assert isinstance(get_balance_result, dict)
            assert self.check_general_response(get_balance_result, keys)
            assert isinstance(get_balance_result.get('core_liquid_balance'), str)

    def test_get_address_txs_api(self):

        address_keys = {'query_time_ms', 'cached', 'lib', 'last_indexed_block', 'last_indexed_block_time', 'total',
                        'actions'}
        action_keys = {'@timestamp', 'timestamp', 'block_num', 'block_id', 'trx_id', 'act', 'receipts',
                       'global_sequence', 'account_ram_deltas', 'producer', 'action_ordinal', 'creator_action_ordinal',
                       'cpu_usage_us', 'net_usage_words', 'signatures'}
        act_keys = {'account', 'name', 'authorization', 'data'}
        for address in self.addresses_of_account:
            get_address_txs_response = self.api.get_address_txs(address)
            assert isinstance(get_address_txs_response, dict)
            assert self.check_general_response(get_address_txs_response, address_keys)
            assert len(get_address_txs_response.get('actions')) > 0
            for transaction in get_address_txs_response.get('actions'):
                assert self.check_general_response(transaction, action_keys)
                assert self.check_general_response(transaction.get('act'), act_keys)

    def test_get_tx_details_api(self):
        response_keys = {'query_time_ms', 'executed', 'trx_id', 'lib', 'cached_lib', 'actions', 'last_indexed_block',
                         'last_indexed_block_time'}
        act_keys = {'account', 'name', 'authorization', 'data'}
        actions_keys = {'action_ordinal', 'creator_action_ordinal', 'act', 'elapsed', 'account_ram_deltas',
                        '@timestamp', 'block_num', 'block_id', 'producer', 'trx_id', 'global_sequence', 'cpu_usage_us',
                        'net_usage_words', 'signatures', 'inline_count', 'inline_filtered', 'receipts', 'code_sequence',
                        'abi_sequence', 'act_digest', 'timestamp'}
        for tx_hash in self.hash_of_transactions:
            get_tx_details_response = self.api.get_tx_details(tx_hash)
            assert self.check_general_response(get_tx_details_response, response_keys)
            if get_tx_details_response.get('actions'):
                for transaction in get_tx_details_response.get('actions'):
                    assert self.check_general_response(transaction, actions_keys)
                    assert self.check_general_response(transaction.get('act'), act_keys)


class TestEosSwedenFromExplorer(TestCase):
    api = EosSwedenApi
    currency = Currencies.eos
    addresses = ['geytmmrvgene',
                 'axygsk5vbquz',
                 ]
    symbol = 'EOS'

    hash_of_transactions = ['139a3feebed6eb9a93be9d5e64eca5ce6265022715584384f20d6d2635c43591',
                            '1b613521679c3c51de24b50a1b5c1b707ff1991d922781dfdfa26d53bd6c26b9',
                            '2062e1b8ca7832cd3f442c56228d430885b9ff6a413906b30638ee90bed90b25',
                            '4f2287a8f7fb63b241100738a030ea9e3a5634b188cce299fa9d0ab9d1534406',
                            ]

    def test_get_balance(self):
        APIS_CONF[self.symbol]['get_balances'] = 'eos_explorer_interface'
        balance_mock_response = [
            {'account_name': 'geytmmrvgene', 'head_block_num': 353618671, 'head_block_time': '2024-01-23T09:51:47.500',
             'privileged': False, 'last_code_update': '1970-01-01T00:00:00.000', 'created': '2018-06-09T13:15:03.500',
             'core_liquid_balance': '0.0317 EOS', 'ram_quota': 9545, 'net_weight': 0, 'cpu_weight': 1,
             'net_limit': {'used': 185, 'available': 0, 'max': 0, 'last_usage_update_time': '2023-06-11T16:04:51.500',
                           'current_used': 0},
             'cpu_limit': {'used': 2472, 'available': 0, 'max': 0, 'last_usage_update_time': '2023-06-11T16:04:51.500',
                           'current_used': 0}, 'ram_usage': 4253, 'permissions': [
                {'perm_name': 'active', 'parent': 'owner', 'required_auth': {'threshold': 1, 'keys': [
                    {'key': 'EOS8deqAHNBuwrGs5X9KzWXdFDQ2e4d9CvvtyLa6tk2aasYdadxAJ', 'weight': 1}], 'accounts': [],
                                                                             'waits': []}, 'linked_actions': []},
                {'perm_name': 'owner', 'parent': '', 'required_auth': {'threshold': 1, 'keys': [
                    {'key': 'EOS8deqAHNBuwrGs5X9KzWXdFDQ2e4d9CvvtyLa6tk2aasYdadxAJ', 'weight': 1}], 'accounts': [],
                                                                       'waits': []}, 'linked_actions': []}],
             'total_resources': {'owner': 'geytmmrvgene', 'net_weight': '0.0000 EOS', 'cpu_weight': '0.0001 EOS',
                                 'ram_bytes': 8145},
             'self_delegated_bandwidth': {'from': 'geytmmrvgene', 'to': 'geytmmrvgene', 'net_weight': '0.0000 EOS',
                                          'cpu_weight': '0.0001 EOS'},
             'refund_request': {'owner': 'geytmmrvgene', 'request_time': '2023-06-11T16:04:51',
                                'net_amount': '1.0000 EOS', 'cpu_amount': '2.5283 EOS'},
             'voter_info': {'owner': 'geytmmrvgene', 'proxy': 'cpuauthority', 'producers': [], 'staked': 2,
                            'last_vote_weight': '24044952.97997795417904854',
                            'proxied_vote_weight': '0.00000000000000000', 'is_proxy': 0, 'flags1': 0, 'reserved2': 0,
                            'reserved3': '0.0000 EOS'},
             'rex_info': {'version': 0, 'owner': 'geytmmrvgene', 'vote_stake': '0.0000 EOS',
                          'rex_balance': '0.0000 REX', 'matured_rex': 0, 'rex_maturities': []},
             'subjective_cpu_bill_limit': {'used': 0, 'available': 0, 'max': 0,
                                           'last_usage_update_time': '2000-01-01T00:00:00.000', 'current_used': 0},
             'eosio_any_linked_actions': []},
            {'account_name': 'axygsk5vbquz', 'head_block_num': 353618695, 'head_block_time': '2024-01-23T09:51:59.500',
             'privileged': False, 'last_code_update': '1970-01-01T00:00:00.000', 'created': '2021-08-20T19:22:09.500',
             'core_liquid_balance': '459.5351 EOS', 'ram_quota': 7533, 'net_weight': 0, 'cpu_weight': 0,
             'net_limit': {'used': 225, 'available': 0, 'max': 0, 'last_usage_update_time': '2023-11-19T21:03:35.000',
                           'current_used': 0},
             'cpu_limit': {'used': 4144, 'available': 0, 'max': 0, 'last_usage_update_time': '2023-11-19T21:03:35.000',
                           'current_used': 0}, 'ram_usage': 3124, 'permissions': [
                {'perm_name': 'active', 'parent': 'owner', 'required_auth': {'threshold': 1, 'keys': [
                    {'key': 'EOS7hupExLJutT81ugzAAdeNgo8hqKVaCUhUmvryNLkFRZxoEhit3', 'weight': 1}], 'accounts': [],
                                                                             'waits': []}, 'linked_actions': []},
                {'perm_name': 'owner', 'parent': '', 'required_auth': {'threshold': 1, 'keys': [
                    {'key': 'EOS7hupExLJutT81ugzAAdeNgo8hqKVaCUhUmvryNLkFRZxoEhit3', 'weight': 1}], 'accounts': [],
                                                                       'waits': []}, 'linked_actions': []}],
             'total_resources': {'owner': 'axygsk5vbquz', 'net_weight': '0.0000 EOS', 'cpu_weight': '0.0000 EOS',
                                 'ram_bytes': 6133}, 'self_delegated_bandwidth': None, 'refund_request': None,
             'voter_info': None, 'rex_info': None, 'subjective_cpu_bill_limit': {'used': 0, 'available': 0, 'max': 0,
                                                                                 'last_usage_update_time': '2000-01-01T00:00:00.000',
                                                                                 'current_used': 0},
             'eosio_any_linked_actions': []}]
        self.api.request = Mock(side_effect=balance_mock_response)
        EosExplorerInterface.balance_apis[0] = self.api
        balances = BlockchainExplorer.get_wallets_balance({'EOS': self.addresses}, Currencies.eos)
        expected_balances = [
            {'address': 'geytmmrvgene', 'balance': Decimal('0.0317'), 'received': Decimal('0.0317'),
             'rewarded': Decimal('0'), 'sent': Decimal('0')},
            {'address': 'axygsk5vbquz', 'balance': Decimal('459.5351'), 'received': Decimal('459.5351'),
             'rewarded': Decimal('0'), 'sent': Decimal('0')}
        ]
        for balance, expected_balance in zip(balances.get(Currencies.eos), expected_balances):
            assert balance == expected_balance

    def test_get_tx_details(self):
        APIS_CONF[self.symbol]['txs_details'] = 'eos_explorer_interface'
        tx_details_mock_responses = [
            {'query_time_ms': 3.275, 'executed': True,
             'trx_id': '139a3feebed6eb9a93be9d5e64eca5ce6265022715584384f20d6d2635c43591', 'lib': 353618659,
             'cached_lib': False, 'actions': [{'action_ordinal': 1, 'creator_action_ordinal': 0,
                                               'act': {'account': 'eosio.token', 'name': 'transfer', 'authorization': [
                                                   {'actor': 'axygsk5vbquz', 'permission': 'active'}],
                                                       'data': {'from': 'axygsk5vbquz', 'to': 'eostexpriwh1',
                                                                'amount': 418.3748, 'symbol': 'EOS',
                                                                'memo': '1390163949', 'quantity': '418.3748 EOS'}},
                                               'elapsed': '73',
                                               'account_ram_deltas': [{'account': 'axygsk5vbquz', 'delta': '128'},
                                                                      {'account': 'exodussignup', 'delta': '-128'}],
                                               '@timestamp': '2023-11-19T21:03:35.000', 'block_num': 342475516,
                                               'block_id': '1469c2fc95a224e7c721384f758e3f59317fb3588e6543d1917780e9bbde7900',
                                               'producer': 'eoseouldotio',
                                               'trx_id': '139a3feebed6eb9a93be9d5e64eca5ce6265022715584384f20d6d2635c43591',
                                               'global_sequence': 359400842763, 'cpu_usage_us': 4143,
                                               'net_usage_words': 28, 'signatures': [
                    'SIG_K1_KkU2WbYTWd5nMUN2ib8sihkD6tfXLF8jnusRsApTJckZ8q5jwn8kra8WbvJRdnZcwXfj3Y1EhaBYyuRgUU2JuXASWJtxdf'],
                                               'inline_count': 7, 'inline_filtered': False, 'receipts': [
                    {'receiver': 'eosio.token', 'global_sequence': '359400842763', 'recv_sequence': '86030804940',
                     'auth_sequence': [{'account': 'axygsk5vbquz', 'sequence': '1'}]},
                    {'receiver': 'axygsk5vbquz', 'global_sequence': '359400842764', 'recv_sequence': '32',
                     'auth_sequence': [{'account': 'axygsk5vbquz', 'sequence': '2'}]},
                    {'receiver': 'eostexpriwh1', 'global_sequence': '359400842765', 'recv_sequence': '12382',
                     'auth_sequence': [{'account': 'axygsk5vbquz', 'sequence': '3'}]}], 'code_sequence': 4,
                                               'abi_sequence': 4,
                                               'act_digest': '1167A1CD63BA14AA16C4E2081B39E725F03350589622BA3E9E438DD00273680F',
                                               'timestamp': '2023-11-19T21:03:35.000'},
                                              {'action_ordinal': 2, 'creator_action_ordinal': 0,
                                               'act': {'account': 'eosio', 'name': 'powerup', 'authorization': [
                                                   {'actor': 'axygsk5vbquz', 'permission': 'active'}],
                                                       'data': {'payer': 'axygsk5vbquz', 'receiver': 'axygsk5vbquz',
                                                                'days': 1, 'net_frac': '277798',
                                                                'cpu_frac': '287808985', 'max_payment': '0.0060 EOS'}},
                                               'elapsed': '361',
                                               'account_ram_deltas': [{'account': 'axygsk5vbquz', 'delta': '405'}],
                                               '@timestamp': '2023-11-19T21:03:35.000', 'block_num': 342475516,
                                               'block_id': '1469c2fc95a224e7c721384f758e3f59317fb3588e6543d1917780e9bbde7900',
                                               'producer': 'eoseouldotio',
                                               'trx_id': '139a3feebed6eb9a93be9d5e64eca5ce6265022715584384f20d6d2635c43591',
                                               'global_sequence': 359400842766, 'receipts': [
                                                  {'receiver': 'eosio', 'global_sequence': '359400842766',
                                                   'recv_sequence': '430276798',
                                                   'auth_sequence': [{'account': 'axygsk5vbquz', 'sequence': '4'}]}],
                                               'code_sequence': 18, 'abi_sequence': 19,
                                               'act_digest': '03152322C67E0BD8A4909C096A98C28DF4662D2C9CE985FC132C17F39D15AFF1',
                                               'timestamp': '2023-11-19T21:03:35.000'},
                                              {'action_ordinal': 5, 'creator_action_ordinal': 2,
                                               'act': {'account': 'eosio.token', 'name': 'transfer', 'authorization': [
                                                   {'actor': 'axygsk5vbquz', 'permission': 'active'}],
                                                       'data': {'from': 'axygsk5vbquz', 'to': 'eosio.rex',
                                                                'amount': 0.0031, 'symbol': 'EOS',
                                                                'memo': 'transfer from axygsk5vbquz to eosio.rex',
                                                                'quantity': '0.0031 EOS'}}, 'elapsed': '41',
                                               '@timestamp': '2023-11-19T21:03:35.000', 'block_num': 342475516,
                                               'block_id': '1469c2fc95a224e7c721384f758e3f59317fb3588e6543d1917780e9bbde7900',
                                               'producer': 'eoseouldotio',
                                               'trx_id': '139a3feebed6eb9a93be9d5e64eca5ce6265022715584384f20d6d2635c43591',
                                               'global_sequence': 359400842767, 'receipts': [
                                                  {'receiver': 'eosio.token', 'global_sequence': '359400842767',
                                                   'recv_sequence': '86030804941',
                                                   'auth_sequence': [{'account': 'axygsk5vbquz', 'sequence': '5'}]},
                                                  {'receiver': 'axygsk5vbquz', 'global_sequence': '359400842768',
                                                   'recv_sequence': '33',
                                                   'auth_sequence': [{'account': 'axygsk5vbquz', 'sequence': '6'}]},
                                                  {'receiver': 'eosio.rex', 'global_sequence': '359400842769',
                                                   'recv_sequence': '15574726',
                                                   'auth_sequence': [{'account': 'axygsk5vbquz', 'sequence': '7'}]}],
                                               'code_sequence': 4, 'abi_sequence': 4,
                                               'act_digest': 'A8502B5A2447DAC8713A992DC9B47FE3FB50C158C2C1F42B510F0610D6C073B0',
                                               'timestamp': '2023-11-19T21:03:35.000'},
                                              {'action_ordinal': 6, 'creator_action_ordinal': 2,
                                               'act': {'account': 'eosio.reserv', 'name': 'powupresult',
                                                       'authorization': [],
                                                       'data': {'fee': '0.0031 EOS', 'powup_net': '26516',
                                                                'powup_cpu': '109890108'}}, 'elapsed': '3',
                                               '@timestamp': '2023-11-19T21:03:35.000', 'block_num': 342475516,
                                               'block_id': '1469c2fc95a224e7c721384f758e3f59317fb3588e6543d1917780e9bbde7900',
                                               'producer': 'eoseouldotio',
                                               'trx_id': '139a3feebed6eb9a93be9d5e64eca5ce6265022715584384f20d6d2635c43591',
                                               'global_sequence': 359400842770, 'receipts': [
                                                  {'receiver': 'eosio.reserv', 'global_sequence': '359400842770',
                                                   'recv_sequence': '5087238', 'auth_sequence': []}],
                                               'code_sequence': 0, 'abi_sequence': 1,
                                               'act_digest': 'FDAC3C8A822D87178CB5F3DAD63F6D57813164A8428DC41BB7D5D685298970F9',
                                               'timestamp': '2023-11-19T21:03:35.000'}],
             'last_indexed_block': 353618992, 'last_indexed_block_time': '2024-01-23T09:54:28.000'},
            {'cached_lib': False, 'executed': False, 'last_indexed_block': 353619028,
             'last_indexed_block_time': '2024-01-23T09:54:46.000', 'lib': 353618695, 'query_time_ms': 3.237,
             'trx_id': '1b613521679c3c51de24b50a1b5c1b707ff1991d922781dfdfa26d53bd6c26b9'},
            {'cached_lib': False, 'executed': False, 'last_indexed_block': 353619048,
             'last_indexed_block_time': '2024-01-23T09:54:56.000', 'lib': 353618719, 'query_time_ms': 2.897,
             'trx_id': '2062e1b8ca7832cd3f442c56228d430885b9ff6a413906b30638ee90bed90b25'},
            {'cached_lib': False, 'executed': False, 'last_indexed_block': 353619219,
             'last_indexed_block_time': '2024-01-23T09:56:21.500', 'lib': 353618887, 'query_time_ms': 2.63,
             'trx_id': '4f2287a8f7fb63b241100738a030ea9e3a5634b188cce299fa9d0ab9d1534406'}
        ]
        self.api.request = Mock(side_effect=tx_details_mock_responses)
        EosExplorerInterface.tx_details_apis[0] = self.api
        txs_details = BlockchainExplorer.get_transactions_details(self.hash_of_transactions, 'EOS')
        expected_txs_details = [
            {'139a3feebed6eb9a93be9d5e64eca5ce6265022715584384f20d6d2635c43591': {
                'hash': '139a3feebed6eb9a93be9d5e64eca5ce6265022715584384f20d6d2635c43591', 'success': True,
                'block': 342475516, 'date': datetime.datetime(2023, 11, 19, 21, 3, 35,
                                                              tzinfo=UTC), 'fees': None, 'memo': '1390163949',
                'confirmations': 11143476, 'raw': None, 'inputs': [], 'outputs': [], 'transfers': [
                    {'type': 'MainCoin', 'symbol': 'EOS', 'currency': 17, 'from': 'axygsk5vbquz', 'to': 'eostexpriwh1',
                     'value': Decimal('418.3748'), 'is_valid': True, 'memo': '1390163949', 'token': None},
                    {'type': 'MainCoin', 'symbol': 'EOS', 'currency': 17, 'from': 'axygsk5vbquz', 'to': 'eosio.rex',
                     'value': Decimal('0.0031'), 'is_valid': True, 'memo': 'transfer from axygsk5vbquz to eosio.rex',
                     'token': None}]}, '1b613521679c3c51de24b50a1b5c1b707ff1991d922781dfdfa26d53bd6c26b9': {
                'success': False}, '2062e1b8ca7832cd3f442c56228d430885b9ff6a413906b30638ee90bed90b25': {
                'success': False},
                '4f2287a8f7fb63b241100738a030ea9e3a5634b188cce299fa9d0ab9d1534406': {'success': False}}
        ]

        for expected_tx_details, tx_hash in zip(expected_txs_details, self.hash_of_transactions):
            if txs_details[tx_hash].get('success'):
                assert txs_details[tx_hash]['confirmations'] >= expected_tx_details[tx_hash].get('confirmations')
                txs_details[tx_hash]['confirmations'] = expected_tx_details[tx_hash].get('confirmations')
            assert txs_details.get(tx_hash) == expected_tx_details[tx_hash]

    def test_get_address_txs(self):
        APIS_CONF[self.symbol]['get_txs'] = 'eos_explorer_interface'
        address_txs_mock_responses = [
            {'query_time_ms': 3.864, 'cached': False, 'lib': 0, 'last_indexed_block': 353626958,
             'last_indexed_block_time': '2024-01-23T11:00:51.000', 'total': {'value': 13, 'relation': 'eq'},
             'actions': [{'@timestamp': '2023-12-19T03:44:59.500', 'timestamp': '2023-12-19T03:44:59.500',
                          'block_num': 347532522,
                          'block_id': '14b6ecea6255129dffb7baedb69ac132b4b7b8578cc77123c46466b2038dbc36',
                          'trx_id': 'd28cf951d4b45822021c85f62c3e194dc9990c909d313282f2f753e150c444cc',
                          'act': {'account': 'eosio.token', 'name': 'transfer',
                                  'authorization': [{'actor': 'kucoinoteos', 'permission': 'active'}],
                                  'data': {'from': 'kucoinoteos', 'to': 'geytmmrvgene', 'amount': 0.0001,
                                           'symbol': 'EOS', 'memo': '1893588837', 'quantity': '0.0001 EOS'}},
                          'receipts': [
                              {'receiver': 'eosio.token', 'global_sequence': 359603263067,
                               'recv_sequence': 86048721023,
                               'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 240019}]},
                              {'receiver': 'kucoinoteos', 'global_sequence': 359603263068, 'recv_sequence': 80004,
                               'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 240020}]},
                              {'receiver': 'geytmmrvgene', 'global_sequence': 359603263069, 'recv_sequence': 13961,
                               'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 240021}]}],
                          'global_sequence': 359603263067, 'producer': 'bp.defi', 'action_ordinal': 10,
                          'creator_action_ordinal': 0},
                         {'@timestamp': '2023-12-19T03:44:54.000', 'timestamp': '2023-12-19T03:44:54.000',
                          'block_num': 347532511,
                          'block_id': '14b6ecdf4030f046f10792bedc0ee4665128e46e62dba500938714638d8df7f1',
                          'trx_id': '994258b7af4283feba9edc622620d4d7f81a3d6212baeb2c1b62bfcbe551ab70',
                          'act': {'account': 'eosio.token', 'name': 'transfer',
                                  'authorization': [{'actor': 'kucoinoteos', 'permission': 'active'}],
                                  'data': {'from': 'kucoinoteos', 'to': 'geytmmrvgene', 'amount': 0.0001,
                                           'symbol': 'EOS', 'memo': '1893588837', 'quantity': '0.0001 EOS'}},
                          'receipts': [
                              {'receiver': 'eosio.token', 'global_sequence': 359603262773,
                               'recv_sequence': 86048720962,
                               'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 239854}]},
                              {'receiver': 'kucoinoteos', 'global_sequence': 359603262774, 'recv_sequence': 79949,
                               'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 239855}]},
                              {'receiver': 'geytmmrvgene', 'global_sequence': 359603262775, 'recv_sequence': 13960,
                               'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 239856}]}],
                          'global_sequence': 359603262773, 'producer': 'bp.defi', 'action_ordinal': 10,
                          'creator_action_ordinal': 0},
                         {'@timestamp': '2023-11-13T05:52:23.500', 'timestamp': '2023-11-13T05:52:23.500',
                          'block_num': 341329440,
                          'block_id': '14584620920d47b9b15d8e7e683bcb3e62aae90755e0809b2c136dd0050fdbfc',
                          'trx_id': '3f6c5371725ee9868f2994d5c925bb5cf8c25e78876be081d07da4159fa759a2',
                          'act': {'account': 'eosio.token', 'name': 'transfer',
                                  'authorization': [{'actor': 'kucoinoteos', 'permission': 'active'}],
                                  'data': {'from': 'kucoinoteos', 'to': 'geytmmrvgene', 'amount': 0.0001,
                                           'symbol': 'EOS', 'memo': '', 'quantity': '0.0001 EOS'}}, 'receipts': [
                             {'receiver': 'eosio.token', 'global_sequence': 359342833347,
                              'recv_sequence': 86027485962,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 233484}]},
                             {'receiver': 'kucoinoteos', 'global_sequence': 359342833348, 'recv_sequence': 77827,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 233485}]},
                             {'receiver': 'geytmmrvgene', 'global_sequence': 359342833349, 'recv_sequence': 13959,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 233486}]}],
                          'global_sequence': 359342833347, 'producer': 'bitfinexeos1', 'action_ordinal': 10,
                          'creator_action_ordinal': 0},
                         {'@timestamp': '2023-11-07T11:03:36.000', 'timestamp': '2023-11-07T11:03:36.000',
                          'block_num': 340330021,
                          'block_id': '14490625811692c7a29f7654c649b7473532fc7185cec6f087cd9e46628b5c92',
                          'trx_id': 'e368c2f20da511bc5d668b0cf53ae41716c0e451d46e473b1078179d9576042b',
                          'act': {'account': 'eosio.token', 'name': 'transfer',
                                  'authorization': [{'actor': 'kucoinoteos', 'permission': 'active'}],
                                  'data': {'from': 'kucoinoteos', 'to': 'geytmmrvgene', 'amount': 0.0001,
                                           'symbol': 'EOS', 'memo': '', 'quantity': '0.0001 EOS'}}, 'receipts': [
                             {'receiver': 'eosio.token', 'global_sequence': 359305140301,
                              'recv_sequence': 86024533863,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 231362}]},
                             {'receiver': 'kucoinoteos', 'global_sequence': 359305140302, 'recv_sequence': 77120,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 231363}]},
                             {'receiver': 'geytmmrvgene', 'global_sequence': 359305140303, 'recv_sequence': 13958,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 231364}]}],
                          'global_sequence': 359305140301, 'producer': 'binancestake', 'action_ordinal': 10,
                          'creator_action_ordinal': 0},
                         {'@timestamp': '2023-10-23T07:09:13.000', 'timestamp': '2023-10-23T07:09:13.000',
                          'block_num': 337712384,
                          'trx_id': '4b17df59a3ce075401bc8264338fc41e85ecc552866ce9ebfbed9503d8b97d9f',
                          'act': {'account': 'eosio.token', 'name': 'transfer',
                                  'authorization': [{'actor': 'kucoinoteos', 'permission': 'active'}],
                                  'data': {'from': 'kucoinoteos', 'to': 'geytmmrvgene', 'amount': 0.0001,
                                           'symbol': 'EOS', 'memo': '1905793670', 'quantity': '0.0001 EOS'}},
                          'receipts': [
                              {'receiver': 'eosio.token', 'global_sequence': 359215610583,
                               'recv_sequence': 86016124960,
                               'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 228463}]},
                              {'receiver': 'kucoinoteos', 'global_sequence': 359215610584, 'recv_sequence': 76154,
                               'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 228464}]},
                              {'receiver': 'geytmmrvgene', 'global_sequence': 359215610585, 'recv_sequence': 13957,
                               'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 228465}]}],
                          'global_sequence': 359215610583, 'producer': 'ivote4eosusa', 'action_ordinal': 9,
                          'creator_action_ordinal': 0},
                         {'@timestamp': '2023-10-16T09:24:25.000', 'timestamp': '2023-10-16T09:24:25.000',
                          'block_num': 336519024,
                          'trx_id': '3d7607d3c5bb3b42962210379132d1050e9749a22d78ca38fc8ed9a889418ea4',
                          'act': {'account': 'eosio.token', 'name': 'transfer',
                                  'authorization': [{'actor': 'kucoinoteos', 'permission': 'active'}],
                                  'data': {'from': 'kucoinoteos', 'to': 'geytmmrvgene', 'amount': 0.0001,
                                           'symbol': 'EOS', 'memo': '', 'quantity': '0.0001 EOS'}}, 'receipts': [
                             {'receiver': 'eosio.token', 'global_sequence': 359182088143,
                              'recv_sequence': 86012368032,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 226302}]},
                             {'receiver': 'kucoinoteos', 'global_sequence': 359182088144, 'recv_sequence': 75434,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 226303}]},
                             {'receiver': 'geytmmrvgene', 'global_sequence': 359182088145, 'recv_sequence': 13956,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 226304}]}],
                          'global_sequence': 359182088143, 'producer': 'bitfinexeos1', 'action_ordinal': 9,
                          'creator_action_ordinal': 0},
                         {'@timestamp': '2023-10-10T08:59:48.500', 'timestamp': '2023-10-10T08:59:48.500',
                          'block_num': 335479358,
                          'trx_id': '0350e3c3e8f547e0442d515c38e249c3bc8d05500c5899e450935d77fc68008a',
                          'act': {'account': 'eosio.token', 'name': 'transfer',
                                  'authorization': [{'actor': 'kucoinoteos', 'permission': 'active'}],
                                  'data': {'from': 'kucoinoteos', 'to': 'geytmmrvgene', 'amount': 0.0001,
                                           'symbol': 'EOS', 'memo': '', 'quantity': '0.0001 EOS'}}, 'receipts': [
                             {'receiver': 'eosio.token', 'global_sequence': 359150319058,
                              'recv_sequence': 86009124198,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 223904}]},
                             {'receiver': 'kucoinoteos', 'global_sequence': 359150319059, 'recv_sequence': 74635,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 223905}]},
                             {'receiver': 'geytmmrvgene', 'global_sequence': 359150319060, 'recv_sequence': 13955,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 223906}]}],
                          'global_sequence': 359150319058, 'producer': 'bitfinexeos1', 'action_ordinal': 9,
                          'creator_action_ordinal': 0},
                         {'@timestamp': '2023-10-02T07:59:48.000', 'timestamp': '2023-10-02T07:59:48.000',
                          'block_num': 334090184,
                          'trx_id': '987b941c4cf8e07d76f32f9999598c2038593d98d9afde1c575f80ef347f9691',
                          'act': {'account': 'eosio.token', 'name': 'transfer',
                                  'authorization': [{'actor': 'kucoinoteos', 'permission': 'active'}],
                                  'data': {'from': 'kucoinoteos', 'to': 'geytmmrvgene', 'amount': 0.0001,
                                           'symbol': 'EOS', 'memo': '', 'quantity': '0.0001 EOS'}}, 'receipts': [
                             {'receiver': 'eosio.token', 'global_sequence': 359106113785,
                              'recv_sequence': 86004069085,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 221359}]},
                             {'receiver': 'eosio.token', 'global_sequence': 359106113821,
                              'recv_sequence': 86004069097,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 221395}]},
                             {'receiver': 'kucoinoteos', 'global_sequence': 359106113786, 'recv_sequence': 73787,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 221360}]},
                             {'receiver': 'geytmmrvgene', 'global_sequence': 359106113787, 'recv_sequence': 13953,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 221361}]},
                             {'receiver': 'kucoinoteos', 'global_sequence': 359106113822, 'recv_sequence': 73799,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 221396}]},
                             {'receiver': 'geytmmrvgene', 'global_sequence': 359106113823, 'recv_sequence': 13954,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 221397}]}],
                          'global_sequence': 359106113785, 'producer': 'starteosiobp', 'action_ordinal': 9,
                          'creator_action_ordinal': 0},
                         {'@timestamp': '2023-09-25T07:42:00.000', 'timestamp': '2023-09-25T07:42:00.000',
                          'block_num': 332878473,
                          'trx_id': '6ec53b23a2ca73521b7194c94403fc481f185b6c5d0f3af3afebf2323149b103',
                          'act': {'account': 'eosio.token', 'name': 'transfer',
                                  'authorization': [{'actor': 'kucoinoteos', 'permission': 'active'}],
                                  'data': {'from': 'kucoinoteos', 'to': 'geytmmrvgene', 'amount': 0.0001,
                                           'symbol': 'EOS', 'memo': '', 'quantity': '0.0001 EOS'}}, 'receipts': [
                             {'receiver': 'eosio.token', 'global_sequence': 359065753891,
                              'recv_sequence': 85997943934,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 217401}]},
                             {'receiver': 'kucoinoteos', 'global_sequence': 359065753892, 'recv_sequence': 72468,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 217402}]},
                             {'receiver': 'geytmmrvgene', 'global_sequence': 359065753893, 'recv_sequence': 13952,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 217403}]}],
                          'global_sequence': 359065753891, 'producer': 'eoseouldotio', 'action_ordinal': 9,
                          'creator_action_ordinal': 0},
                         {'@timestamp': '2023-09-25T07:41:53.500', 'timestamp': '2023-09-25T07:41:53.500',
                          'block_num': 332878460,
                          'trx_id': 'b7163ddbdf39da7def78d2d8ab107bf260e0a698bb1fe56156be064218dccace',
                          'act': {'account': 'eosio.token', 'name': 'transfer',
                                  'authorization': [{'actor': 'kucoinoteos', 'permission': 'active'}],
                                  'data': {'from': 'kucoinoteos', 'to': 'geytmmrvgene', 'amount': 0.0001,
                                           'symbol': 'EOS', 'memo': '', 'quantity': '0.0001 EOS'}}, 'receipts': [
                             {'receiver': 'eosio.token', 'global_sequence': 359065753514,
                              'recv_sequence': 85997943860,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 217203}]},
                             {'receiver': 'kucoinoteos', 'global_sequence': 359065753515, 'recv_sequence': 72402,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 217204}]},
                             {'receiver': 'geytmmrvgene', 'global_sequence': 359065753516, 'recv_sequence': 13951,
                              'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 217205}]}],
                          'global_sequence': 359065753514, 'producer': 'eosasia11111', 'action_ordinal': 9,
                          'creator_action_ordinal': 0},
                         {'@timestamp': '2023-09-18T07:03:11.500', 'timestamp': '2023-09-18T07:03:11.500',
                          'block_num': 331664253,
                          'trx_id': '8a54a7791c9ef86d4e78077d06f5737fec9ecf43e2ac3e7625cb88109f428487',
                          'act': {'account': 'eosio.token', 'name': 'transfer',
                                  'authorization': [{'actor': 'kucoinoteos', 'permission': 'active'}],
                                  'data': {'from': 'kucoinoteos', 'to': 'geytmmrvgene', 'amount': 0.0001,
                                           'symbol': 'EOS', 'memo': '1872749313', 'quantity': '0.0001 EOS'}},
                          'receipts': [
                              {'receiver': 'eosio.token', 'global_sequence': 359022140752,
                               'recv_sequence': 85990934708,
                               'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 213209}]},
                              {'receiver': 'kucoinoteos', 'global_sequence': 359022140753, 'recv_sequence': 71071,
                               'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 213210}]},
                              {'receiver': 'geytmmrvgene', 'global_sequence': 359022140754, 'recv_sequence': 13950,
                               'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 213211}]}],
                          'global_sequence': 359022140752, 'producer': 'starteosiobp', 'action_ordinal': 9,
                          'creator_action_ordinal': 0},
                         {'@timestamp': '2023-09-18T07:03:05.000', 'timestamp': '2023-09-18T07:03:05.000',
                          'block_num': 331664240,
                          'trx_id': '90ed008563f7e9f0c0ae9319a4886f4cc9b5998e1c943f123c65e785ed42b1bf',
                          'act': {'account': 'eosio.token', 'name': 'transfer',
                                  'authorization': [{'actor': 'kucoinoteos', 'permission': 'active'}],
                                  'data': {'from': 'kucoinoteos', 'to': 'geytmmrvgene', 'amount': 0.0001,
                                           'symbol': 'EOS', 'memo': '1872749313', 'quantity': '0.0001 EOS'}},
                          'receipts': [
                              {'receiver': 'eosio.token', 'global_sequence': 359022140406,
                               'recv_sequence': 85990934639,
                               'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 213011}]},
                              {'receiver': 'kucoinoteos', 'global_sequence': 359022140407, 'recv_sequence': 71005,
                               'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 213012}]},
                              {'receiver': 'geytmmrvgene', 'global_sequence': 359022140408, 'recv_sequence': 13949,
                               'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 213013}]}],
                          'global_sequence': 359022140406, 'producer': 'newdex.bp', 'action_ordinal': 9,
                          'creator_action_ordinal': 0},
                         {'@timestamp': '2023-09-11T04:55:11.000', 'timestamp': '2023-09-11T04:55:11.000',
                          'block_num': 330439395,
                          'trx_id': '50dc20000bd9d83b97355a6a113ef43c8dfbab75f922bedd7608a61fbb4eed4a',
                          'act': {'account': 'eosio.token', 'name': 'transfer',
                                  'authorization': [{'actor': 'kucoinoteos', 'permission': 'active'}],
                                  'data': {'from': 'kucoinoteos', 'to': 'geytmmrvgene', 'amount': 0.0001,
                                           'symbol': 'EOS', 'memo': '1925983329', 'quantity': '0.0001 EOS'}},
                          'receipts': [
                              {'receiver': 'eosio.token', 'global_sequence': 358989913830,
                               'recv_sequence': 85986930255,
                               'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 210127}]},
                              {'receiver': 'kucoinoteos', 'global_sequence': 358989913831, 'recv_sequence': 70043,
                               'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 210128}]},
                              {'receiver': 'geytmmrvgene', 'global_sequence': 358989913832, 'recv_sequence': 13948,
                               'auth_sequence': [{'account': 'kucoinoteos', 'sequence': 210129}]}],
                          'global_sequence': 358989913830, 'producer': 'whaleex.com', 'action_ordinal': 9,
                          'creator_action_ordinal': 0}]},
            {'query_time_ms': 3.236, 'cached': False, 'lib': 0, 'last_indexed_block': 353627030,
             'last_indexed_block_time': '2024-01-23T11:01:27.000', 'total': {'value': 3, 'relation': 'eq'},
             'actions': [
                 {'@timestamp': '2023-11-19T21:03:35.000', 'timestamp': '2023-11-19T21:03:35.000',
                  'block_num': 342475516,
                  'block_id': '1469c2fc95a224e7c721384f758e3f59317fb3588e6543d1917780e9bbde7900',
                  'trx_id': '139a3feebed6eb9a93be9d5e64eca5ce6265022715584384f20d6d2635c43591',
                  'act': {'account': 'eosio.token', 'name': 'transfer',
                          'authorization': [{'actor': 'axygsk5vbquz', 'permission': 'active'}],
                          'data': {'from': 'axygsk5vbquz', 'to': 'eosio.rex', 'amount': 0.0031, 'symbol': 'EOS',
                                   'memo': 'transfer from axygsk5vbquz to eosio.rex', 'quantity': '0.0031 EOS'}},
                  'receipts': [
                      {'receiver': 'eosio.token', 'global_sequence': 359400842767, 'recv_sequence': 86030804941,
                       'auth_sequence': [{'account': 'axygsk5vbquz', 'sequence': 5}]},
                      {'receiver': 'axygsk5vbquz', 'global_sequence': 359400842768, 'recv_sequence': 33,
                       'auth_sequence': [{'account': 'axygsk5vbquz', 'sequence': 6}]},
                      {'receiver': 'eosio.rex', 'global_sequence': 359400842769, 'recv_sequence': 15574726,
                       'auth_sequence': [{'account': 'axygsk5vbquz', 'sequence': 7}]}],
                  'global_sequence': 359400842767, 'producer': 'eoseouldotio', 'action_ordinal': 5,
                  'creator_action_ordinal': 2},
                 {'@timestamp': '2023-11-19T21:03:35.000', 'timestamp': '2023-11-19T21:03:35.000',
                  'block_num': 342475516,
                  'block_id': '1469c2fc95a224e7c721384f758e3f59317fb3588e6543d1917780e9bbde7900',
                  'trx_id': '139a3feebed6eb9a93be9d5e64eca5ce6265022715584384f20d6d2635c43591',
                  'act': {'account': 'eosio', 'name': 'powerup',
                          'authorization': [{'actor': 'axygsk5vbquz', 'permission': 'active'}],
                          'data': {'payer': 'axygsk5vbquz', 'receiver': 'axygsk5vbquz', 'days': 1,
                                   'net_frac': '277798',
                                   'cpu_frac': '287808985', 'max_payment': '0.0060 EOS'}}, 'receipts': [
                     {'receiver': 'eosio', 'global_sequence': 359400842766, 'recv_sequence': 430276798,
                      'auth_sequence': [{'account': 'axygsk5vbquz', 'sequence': 4}]}],
                  'account_ram_deltas': [{'account': 'axygsk5vbquz', 'delta': 405}],
                  'global_sequence': 359400842766,
                  'producer': 'eoseouldotio', 'action_ordinal': 2, 'creator_action_ordinal': 0},
                 {'@timestamp': '2023-11-19T21:03:35.000', 'timestamp': '2023-11-19T21:03:35.000',
                  'block_num': 342475516,
                  'block_id': '1469c2fc95a224e7c721384f758e3f59317fb3588e6543d1917780e9bbde7900',
                  'trx_id': '139a3feebed6eb9a93be9d5e64eca5ce6265022715584384f20d6d2635c43591',
                  'act': {'account': 'eosio.token', 'name': 'transfer',
                          'authorization': [{'actor': 'axygsk5vbquz', 'permission': 'active'}],
                          'data': {'from': 'axygsk5vbquz', 'to': 'eostexpriwh1', 'amount': 418.3748,
                                   'symbol': 'EOS',
                                   'memo': '1390163949', 'quantity': '418.3748 EOS'}}, 'receipts': [
                     {'receiver': 'eosio.token', 'global_sequence': 359400842763, 'recv_sequence': 86030804940,
                      'auth_sequence': [{'account': 'axygsk5vbquz', 'sequence': 1}]},
                     {'receiver': 'axygsk5vbquz', 'global_sequence': 359400842764, 'recv_sequence': 32,
                      'auth_sequence': [{'account': 'axygsk5vbquz', 'sequence': 2}]},
                     {'receiver': 'eostexpriwh1', 'global_sequence': 359400842765, 'recv_sequence': 12382,
                      'auth_sequence': [{'account': 'axygsk5vbquz', 'sequence': 3}]}], 'cpu_usage_us': 4143,
                  'net_usage_words': 28, 'account_ram_deltas': [{'account': 'axygsk5vbquz', 'delta': 128},
                                                                {'account': 'exodussignup', 'delta': -128}],
                  'global_sequence': 359400842763, 'producer': 'eoseouldotio', 'action_ordinal': 1,
                  'creator_action_ordinal': 0, 'signatures': [
                     'SIG_K1_KkU2WbYTWd5nMUN2ib8sihkD6tfXLF8jnusRsApTJckZ8q5jwn8kra8WbvJRdnZcwXfj3Y1EhaBYyuRgUU2JuXASWJtxdf']}]}
        ]
        self.api.request = Mock(side_effect=address_txs_mock_responses)
        EosExplorerInterface.address_txs_apis[0] = self.api
        expected_addresses_txs = [
            [], [{'contract_address': None, 'address': 'axygsk5vbquz', 'from_address': ['axygsk5vbquz'],
                  'hash': '139a3feebed6eb9a93be9d5e64eca5ce6265022715584384f20d6d2635c43591', 'block': 342475516,
                  'timestamp': datetime.datetime(2023, 11, 19, 21, 3, 35, tzinfo=UTC), 'value': Decimal('-0.0031'),
                  'confirmations': -342475516, 'is_double_spend': False, 'details': {},
                  'tag': 'transfer from axygsk5vbquz to eosio.rex', 'huge': False, 'invoice': None},
                 {'contract_address': None, 'address': 'axygsk5vbquz', 'from_address': ['axygsk5vbquz'],
                  'hash': '139a3feebed6eb9a93be9d5e64eca5ce6265022715584384f20d6d2635c43591', 'block': 342475516,
                  'timestamp': datetime.datetime(2023, 11, 19, 21, 3, 35, tzinfo=UTC), 'value': Decimal('-418.3748'),
                  'confirmations': 11151514, 'is_double_spend': False, 'details': {}, 'tag': '1390163949', 'huge': False,
                  'invoice': None}
                 ]
        ]

        for address, expected_address_txs in zip(self.addresses, expected_addresses_txs):
            address_txs = BlockchainExplorer.get_wallet_transactions(address, Currencies.eos, 'EOS')
            assert len(expected_address_txs) == len(address_txs.get(Currencies.eos))
            for expected_address_tx, address_tx in zip(expected_address_txs, address_txs.get(Currencies.eos)):
                assert address_tx.confirmations >= expected_address_tx.get('confirmations')
                address_tx.confirmations = expected_address_tx.get('confirmations')
                assert address_tx.__dict__ == expected_address_tx
