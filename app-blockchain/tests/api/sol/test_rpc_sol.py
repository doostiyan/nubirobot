import math
import pytest
import datetime
from decimal import Decimal
from unittest import TestCase

import pytz
from pytz import UTC

from exchange.base.models import Currencies
from exchange.blockchain.api.general.dtos import TransferTx
from exchange.blockchain.api.sol.sol_explorer_interface import RpcSolExplorerInterface
from exchange.blockchain.api.sol.rpc_sol import QuickNodeRPC, MainRPC, AlchemyRPC, RpcSolParser
from exchange.blockchain.apis_conf import APIS_CONF
from exchange.blockchain.tests.api.general_test.general_test_from_explorer import TestFromExplorer
from exchange.blockchain.tests.fixtures.sol_fixtures import sol_raw_multi_transfer_address_txs, sol_multi_transfer_address


class TestRpcSolApiCalls(TestCase):
    api = MainRPC  # default
    txs_hash = ['57rfrAKFTMyretUzDMy2TLY6UX7VNq2uzFgdpLufztgK75kCxZnhmoUbhqpoyeTeacT76Nak2HJjrVa9o2wZSVhV']
    addresses = ['6h7Ce5MfeuUP4gqMfQkM9GanBrZDvBcuxK6RX8qLSWAP']
    block_heights = [(226975974, 226975980)]

    @pytest.mark.slow
    def test_get_balance_api(self):
        for address in self.addresses:
            get_balance_result = self.api.get_balance(address)
            assert isinstance(get_balance_result, dict)
            assert {'result'}.issubset(set(get_balance_result.keys()))
            assert isinstance(get_balance_result.get('result').get('value'), int)

    @pytest.mark.slow
    def test_get_balances_api(self):
        get_balances_result = self.api.get_balances(self.addresses)
        assert isinstance(get_balances_result, dict)
        assert {'result'}.issubset(set(get_balances_result.keys()))
        assert isinstance(get_balances_result.get('result').get('value'), list)
        for balance in get_balances_result.get('result').get('value'):
            assert isinstance(balance.get('lamports'), int)

    @pytest.mark.slow
    def test_get_block_head_api(self):
        get_block_head_result = self.api.get_block_head()
        assert isinstance(get_block_head_result, dict)
        assert {'result'}.issubset(set(get_block_head_result.keys()))
        assert isinstance(get_block_head_result.get('result').get('absoluteSlot'), int)

    @pytest.mark.slow
    def test_get_tx_details_api(self):
        for tx_hash in self.txs_hash:
            get_tx_details_response = self.api.get_tx_details(tx_hash)
            assert isinstance(get_tx_details_response, dict)
            assert isinstance(get_tx_details_response.get('result'), dict)
            if (get_tx_details_response.get('result').get('meta').get('err')
                    or get_tx_details_response.get('result').get('meta').get('status').get('Err')
                    or 'Ok' not in get_tx_details_response.get('result').get('meta').get('status').keys()
                    or not get_tx_details_response.get('result').get('transaction').get('signatures')):
                continue
            assert isinstance(get_tx_details_response.get('result').get('transaction').get('signatures')[0], str)
            assert isinstance(get_tx_details_response.get('result').get('blockTime'), int)
            assert isinstance(get_tx_details_response.get('result').get('slot'), int)
            for transfer in get_tx_details_response.get('result').get('transaction').get('message').get(
                    'instructions'):
                if (not transfer.get('parsed')
                        or transfer.get('program') != 'system'
                        or transfer.get('programId') != '11111111111111111111111111111111'
                        or transfer.get('parsed').get('type') not in ['transfer', 'transferChecked']):
                    continue
                isinstance(transfer.get('parsed').get('info').get('source'), str)
                isinstance(transfer.get('parsed').get('info').get('destination'), str)
                isinstance(transfer.get('parsed').get('info').get('lamports'), int)

    @pytest.mark.slow
    def test_get_address_txs_api(self):
        for address in self.addresses:
            get_txs_hash_response = self.api.get_txs_hash(address)
            txs_hash = self.api.parser.parse_txs_hash_response(get_txs_hash_response)
            get_address_txs_result = self.api.get_address_txs(txs_hash)
            assert isinstance(get_address_txs_result, list)
            assert {'result'}.issubset(get_address_txs_result[0])
            if (get_address_txs_result[0].get('result').get('meta').get('err')
                    or get_address_txs_result[0].get('result').get('meta').get('status').get('Err')
                    or 'Ok' not in get_address_txs_result[0].get('result').get('meta').get('status').keys()
                    or not get_address_txs_result[0].get('result').get('transaction').get('signatures')):
                continue
            assert isinstance(get_address_txs_result[0].get('result').get('transaction').get('signatures')[0], str)
            assert isinstance(get_address_txs_result[0].get('result').get('blockTime'), int)
            assert isinstance(get_address_txs_result[0].get('result').get('slot'), int)
            for transfer in get_address_txs_result[0].get('result').get('transaction').get('message').get(
                    'instructions'):
                if (not transfer.get('parsed')
                        or transfer.get('program') != 'system'
                        or transfer.get('programId') != '11111111111111111111111111111111'
                        or transfer.get('parsed').get('type') not in ['transfer', 'transferChecked']):
                    continue
                isinstance(transfer.get('parsed').get('info').get('source'), str)
                isinstance(transfer.get('parsed').get('info').get('destination'), str)
                isinstance(transfer.get('parsed').get('info').get('lamports'), int)

    @pytest.mark.slow
    def test_get_txs_hash_api(self):
        for address in self.addresses:
            get_txs_hash_response = self.api.get_txs_hash(address)
            assert isinstance(get_txs_hash_response, dict)
            assert isinstance(get_txs_hash_response.get('result'), list)
            for tx_hash in get_txs_hash_response.get('result'):
                assert not tx_hash.get('err')
                assert isinstance(tx_hash.get('signature'), str)
                assert isinstance(tx_hash.get('blockTime'), int)

    @pytest.mark.slow
    def test_get_blocks_api(self):
        for from_block, to_block in self.block_heights:
            get_blocks_txs_response = self.api.get_batch_block_txs(from_block, to_block)
            assert isinstance(get_blocks_txs_response, dict)
            assert isinstance(get_blocks_txs_response.get('result'), list)
            for block in get_blocks_txs_response.get('result'):
                assert isinstance(block, int)

    @pytest.mark.slow
    def test_get_blocks_txs_api(self):
        for from_block, to_block in self.block_heights:
            batch_response = self.api.get_batch_block_txs(from_block, to_block)
            request_numbers = int(math.ceil(len(batch_response.get('result')) / self.api.max_block_in_single_request))
            for i in range(request_numbers):
                block_txs_api_response = self.api.get_blocks_txs(i, batch_response)
                assert isinstance(block_txs_api_response, list)
                assert isinstance(block_txs_api_response[0], dict)
                assert isinstance(block_txs_api_response[0].get('result'), dict)
                key2check = [('blockHeight', int), ('blockTime', int), ('blockhash', str), ('transactions', list)]
                for key, value in key2check:
                    assert isinstance(block_txs_api_response[0].get('result').get(key), value)
                for tx in block_txs_api_response[0].get('result').get('transactions'):
                    assert isinstance(tx.get('transaction'), dict)


class TestMainRpcApiCall(TestRpcSolApiCalls):
    api = MainRPC


class TestQuickNodeRpcApiCall(TestRpcSolApiCalls):
    api = QuickNodeRPC


class TestAlchemyRpcApiCall(TestRpcSolApiCalls):
    api = AlchemyRPC


class TestRpcSolApiFromExplorer(TestFromExplorer):
    api = MainRPC
    addresses = ['ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt', '6h7Ce5MfeuUP4gqMfQkM9GanBrZDvBcuxK6RX8qLSWAP']
    txs_addresses = ['ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt']
    txs_hash = ['57rfrAKFTMyretUzDMy2TLY6UX7VNq2uzFgdpLufztgK75kCxZnhmoUbhqpoyeTeacT76Nak2HJjrVa9o2wZSVhV']
    symbol = 'SOL'
    currencies = Currencies.sol
    explorerInterface = RpcSolExplorerInterface

    @classmethod
    def test_get_balance(cls):
        balance_mock_responses = [
            {
                "jsonrpc": "2.0",
                "result": {
                    "context": {
                        "apiVersion": "1.13.5",
                        "slot": 171949127
                    },
                    "value": 47122816272
                },
                "id": 1
            },
            {
                "jsonrpc": "2.0",
                "result": {
                    "context": {
                        "apiVersion": "1.13.5",
                        "slot": 171949127
                    },
                    "value": 37487493837
                },
                "id": 1
            }
        ]
        expected_balances = [
            {
                'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                'balance': Decimal('47.122816272'),
                'received': Decimal('47.122816272'),
                'sent': Decimal('0'),
                'rewarded': Decimal('0')
            },
            {
                'address': '6h7Ce5MfeuUP4gqMfQkM9GanBrZDvBcuxK6RX8qLSWAP',
                'balance': Decimal('37.487493837'),
                'received': Decimal('37.487493837'),
                'sent': Decimal('0'),
                'rewarded': Decimal('0')
            }
        ]
        APIS_CONF['SOL']['get_balances'] = 'rpc_sol_explorer_interface'
        cls.api.SUPPORT_GET_BALANCE_BATCH = False
        cls.get_balance(balance_mock_responses, expected_balances)

    @classmethod
    def test_get_balances(cls):
        balances_mock_responses = [
            {'jsonrpc': '2.0', 'result': {'context': {'apiVersion': '1.14.22', 'slot': 209576986}, 'value': [
                {'data': ['', 'base64'], 'executable': False, 'lamports': 47122816272,
                 'owner': '11111111111111111111111111111111', 'rentEpoch': 0},
                {'data': ['', 'base64'], 'executable': False, 'lamports': 37487493837,
                 'owner': '11111111111111111111111111111111', 'rentEpoch': 361}]}, 'id': 1}
        ]
        expected_balances = [
            {
                'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                'balance': Decimal('47.122816272'),
                'received': Decimal('47.122816272'),
                'sent': Decimal('0'),
                'rewarded': Decimal('0')
            },
            {
                'address': '6h7Ce5MfeuUP4gqMfQkM9GanBrZDvBcuxK6RX8qLSWAP',
                'balance': Decimal('37.487493837'),
                'received': Decimal('37.487493837'),
                'sent': Decimal('0'),
                'rewarded': Decimal('0')
            }
        ]
        APIS_CONF['SOL']['get_balances'] = 'rpc_sol_explorer_interface'
        cls.api.SUPPORT_GET_BALANCE_BATCH = True
        cls.get_balance(balances_mock_responses, expected_balances)

    @classmethod
    @pytest.mark.django_db
    def test_get_tx_details(cls):
        tx_details_mock_response = [
            {
                'id': 1,
                'jsonrpc': '2.0',
                'result': {'absoluteSlot': 209611660, 'blockHeight': 192071334, 'epoch': 485, 'slotIndex': 91660,
                           'slotsInEpoch': 432000, 'transactionCount': 205860574342}
            },
            {
                'jsonrpc': '2.0',
                'result': {
                    'blockTime': 1688144949,
                    'meta': {
                        'computeUnitsConsumed': 0, 'err': None, 'fee': 5000,
                        'innerInstructions': [],
                        'logMessages': [
                            'Program 11111111111111111111111111111111 invoke [1]',
                            'Program 11111111111111111111111111111111 success'],
                        'postBalances': [1982180308, 22240000000, 1],
                        'postTokenBalances': [], 'preBalances': [24222185308, 0, 1],
                        'preTokenBalances': [], 'rewards': [], 'status': {'Ok': None}},
                    'slot': 202617447, 'transaction': {'message': {'accountKeys': [
                        {'pubkey': '7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj', 'signer': True,
                         'source': 'transaction',
                         'writable': True},
                        {'pubkey': 'Fi5Lw5opNWcs4iSMxEUBaXS9wzy9Td9k2VoBfpNwzZoD', 'signer': False,
                         'source': 'transaction',
                         'writable': True},
                        {'pubkey': '11111111111111111111111111111111', 'signer': False, 'source': 'transaction',
                         'writable': False}],
                        'instructions': [{'parsed': {
                            'info': {'destination': 'Fi5Lw5opNWcs4iSMxEUBaXS9wzy9Td9k2VoBfpNwzZoD',
                                     'lamports': 22240000000,
                                     'source': '7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj'}, 'type': 'transfer'},
                            'program': 'system',
                            'programId': '11111111111111111111111111111111',
                            'stackHeight': None}],
                        'recentBlockhash': '3zg4nvFFSWJCMVUpF4iE5ExS4f95PD32XF9KRvKDLr3N'},
                        'signatures': [
                            '57rfrAKFTMyretUzDMy2TLY6UX7VNq2uzFgdpLufztgK75kCxZ'
                            'nhmoUbhqpoyeTeacT76Nak2HJjrVa9o2wZSVhV']},
                    'version': 'legacy'}, 'id': 0}
        ]
        expected_tx_details = [
            {
                'hash': '57rfrAKFTMyretUzDMy2TLY6UX7VNq2uzFgdpLufztgK75kCxZnhmoUbhqpoyeTeacT76Nak2HJjrVa9o2wZSVhV',
                'success': True, 'block': 202617447,
                'date': datetime.datetime(2023, 6, 30, 17, 9, 9, tzinfo=datetime.timezone.utc),
                'fees': Decimal('0.000005000'),
                'memo': None,
                'confirmations': 6994213,
                'raw': None,
                'inputs': [],
                'outputs': [],
                'transfers': [
                    {'type': 'MainCoin', 'symbol': 'SOL', 'currency': 37,
                     'from': '7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj',
                     'to': 'Fi5Lw5opNWcs4iSMxEUBaXS9wzy9Td9k2VoBfpNwzZoD', 'value': Decimal('22.240000000'),
                     'is_valid': True,
                     'memo': None,
                     'token': None}
                ]
            }
        ]
        APIS_CONF['SOL']['txs_details'] = 'rpc_sol_explorer_interface'
        cls.get_tx_details(tx_details_mock_response, expected_tx_details)

        tx_details_mock_response2 = [
            {
                'id': 1,
                'jsonrpc': '2.0',
                'result': {'absoluteSlot': 226975974, 'blockHeight': 192071334, 'epoch': 485, 'slotIndex': 91660,
                           'slotsInEpoch': 432000, 'transactionCount': 205860574342}
            },
            {'jsonrpc': '2.0',
             'result': {
                 'blockTime': 1698648046,
                 'meta': {'computeUnitsConsumed': 0, 'err': None, 'fee': 5000,
                          'innerInstructions': [],
                          'logMessages': [
                              'Program 11111111111111111111111111111111 invoke [1]',
                              'Program 11111111111111111111111111111111 success',
                              'Program 11111111111111111111111111111111 invoke [1]',
                              'Program 11111111111111111111111111111111 success'],
                          'postBalances': [3020842247260951, 20000000, 1107945797, 42706560,
                                           1], 'postTokenBalances': [],
                          'preBalances': [3020843339265951, 20000000, 15945797, 42706560, 1],
                          'preTokenBalances': [], 'rewards': [], 'status': {'Ok': None}},
                 'slot': 226876286, 'transaction': {'message': {'accountKeys': [
                     {'pubkey': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9', 'signer': True, 'source': 'transaction',
                      'writable': True},
                     {'pubkey': '8xSH84dD2uNTipwVbqA37Z7vzinuxLDWd4VBpVbnXtAq', 'signer': False,
                      'source': 'transaction',
                      'writable': True},
                     {'pubkey': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN', 'signer': False,
                      'source': 'transaction',
                      'writable': True},
                     {'pubkey': 'SysvarRecentB1ockHashes11111111111111111111', 'signer': False, 'source': 'transaction',
                      'writable': False},
                     {'pubkey': '11111111111111111111111111111111', 'signer': False, 'source': 'transaction',
                      'writable': False}],
                     'instructions': [
                         {'parsed': {
                             'info': {'nonceAccount': '8xSH84dD2uNTipwVbqA37Z7vzinuxLDWd4VBpVbnXtAq',
                                      'nonceAuthority': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9',
                                      'recentBlockhashesSysvar': 'SysvarRecentB1ockHashes11111111111111111111'},
                             'type': 'advanceNonce'}, 'program': 'system',
                             'programId': '11111111111111111111111111111111',
                             'stackHeight': None},
                         {'parsed': {
                             'info': {'destination': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN',
                                      'lamports': 1092000000,
                                      'source': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'}, 'type': 'transfer'},
                             'program': 'system',
                             'programId': '11111111111111111111111111111111',
                             'stackHeight': None}],
                     'recentBlockhash': 'C6JMpqxtT8hyPbD4bcgmiGhY64ay2gzGQyr634e5BvFT'},
                     'signatures': [
                         '4hyCo6poqsgDhyRbdsDAGeB4U7ioP2x1exsmjtZW2og4eSKrwttUzXxpvsjJfxVf9bqptFyQkvDH6wis9VxMsrb8']},
                 'version': 'legacy'}, 'id': 0}
        ]
        expected_txs_details2 = [
            {'hash': '4hyCo6poqsgDhyRbdsDAGeB4U7ioP2x1exsmjtZW2og4eSKrwttUzXxpvsjJfxVf9bqptFyQkvDH6wis9VxMsrb8',
             'success': True, 'block': 226876286,
             'date': datetime.datetime(2023, 10, 30, 6, 40, 46, tzinfo=datetime.timezone.utc),
             'fees': Decimal('0.000005000'),
             'memo': None,
             'confirmations': 99688,
             'raw': None,
             'inputs': [],
             'outputs': [],
             'transfers': [
                 {'type': 'MainCoin', 'symbol': 'SOL', 'currency': 37,
                  'from': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9',
                  'to': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN', 'value': Decimal('1.092000000'),
                  'is_valid': True,
                  'memo': None,
                  'token': None}]}
        ]
        cls.get_tx_details(tx_details_mock_response2, expected_txs_details2)

        tx_details_mock_response3 = [
            {
                'id': 1,
                'jsonrpc': '2.0',
                'result': {'absoluteSlot': 226975974, 'blockHeight': 192071334, 'epoch': 485, 'slotIndex': 91660,
                           'slotsInEpoch': 432000, 'transactionCount': 205860574342}
            },
            {
                'jsonrpc': '2.0',
                'result': {
                    'blockTime': 1698613905,
                    'meta': {'computeUnitsConsumed': 0, 'err': None, 'fee': 5000,
                             'innerInstructions': [],
                             'logMessages': [
                                 'Program 11111111111111111111111111111111 invoke [1]',
                                 'Program 11111111111111111111111111111111 success',
                                 'Program 11111111111111111111111111111111 invoke [1]',
                                 'Program 11111111111111111111111111111111 success'],
                             'postBalances': [4324728495947892, 21000000, 377185797, 42706560, 1],
                             'postTokenBalances': [],
                             'preBalances': [4324728872242892, 21000000, 895797, 42706560, 1],
                             'preTokenBalances': [], 'rewards': [], 'status': {'Ok': None}},
                    'slot': 226793177,
                    'transaction': {'message': {'accountKeys': [
                        {'pubkey': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9', 'signer': True,
                         'source': 'transaction',
                         'writable': True},
                        {'pubkey': 'uRz4VqbrLzQCN767YNKjTNqGyTfmRyDTe1GyCiyfrtW', 'signer': False,
                         'source': 'transaction',
                         'writable': True},
                        {'pubkey': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN', 'signer': False,
                         'source': 'transaction',
                         'writable': True},
                        {'pubkey': 'SysvarRecentB1ockHashes11111111111111111111', 'signer': False,
                         'source': 'transaction',
                         'writable': False},
                        {'pubkey': '11111111111111111111111111111111', 'signer': False, 'source': 'transaction',
                         'writable': False}],
                        'instructions': [{'parsed': {
                            'info': {'nonceAccount': 'uRz4VqbrLzQCN767YNKjTNqGyTfmRyDTe1GyCiyfrtW',
                                     'nonceAuthority': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9',
                                     'recentBlockhashesSysvar': 'SysvarRecentB1ockHashes11111111111111111111'},
                            'type': 'advanceNonce'}, 'program': 'system',
                            'programId': '11111111111111111111111111111111',
                            'stackHeight': None},
                            {'parsed': {
                                'info': {'destination': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN',
                                         'lamports': 376290000,
                                         'source': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'}, 'type': ''},
                                'program': 'system',
                                'programId': '11111111111111111111111111111111',
                                'stackHeight': None}],
                        'recentBlockhash': 'AgSjFuAtrUsXJqLs2zaM5RMPDGBKCSfAYoXxgsRymeW3'},
                        'signatures': [
                            '3ZLtdKtcrKmL8DaBd8p7xb2hxfjpXnATmDXgEScR19dA6v1QK8cDyY4sBP9q86NDgrmp9vkMRsvRk4wUGcfTuKL']
                    },
                    'version': 'legacy'}, 'id': 0}
        ]
        expected_txs_details3 = [{'success': False}]
        cls.get_tx_details(tx_details_mock_response3, expected_txs_details3)

        tx_details_mock_response4 = [
            {
                'id': 1,
                'jsonrpc': '2.0',
                'result': {'absoluteSlot': 226975974, 'blockHeight': 192071334, 'epoch': 485, 'slotIndex': 91660,
                           'slotsInEpoch': 432000, 'transactionCount': 205860574342}
            },
            {'jsonrpc': '2.0',
             'result': {
                 'blockTime': 1698526705,
                 'meta': {'computeUnitsConsumed': 0, 'err': None, 'fee': 5000,
                          'innerInstructions': [],
                          'logMessages': [
                              'Program 11111111111111111111111111111111 invoke [1]',
                              'Program 11111111111111111111111111111111 success',
                              'Program 11111111111111111111111111111111 invoke [1]',
                              'Program 11111111111111111111111111111111 success'],
                          'postBalances': [4691376316364879, 20000000, 892895788, 42706560, 1],
                          'postTokenBalances': [],
                          'preBalances': [4691377208369879, 20000000, 895788, 42706560, 1],
                          'preTokenBalances': [], 'rewards': [], 'status': {'Ok': None}},
                 'slot': 226579590, 'transaction': {'message': {'accountKeys': [
                     {'pubkey': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9', 'signer': True, 'source': 'transaction',
                      'writable': True},
                     {'pubkey': 'E8gPR9iQyS67j2hFmAzjywbY7rBRmT5FVMoQd8KRn4dH', 'signer': False,
                      'source': 'transaction',
                      'writable': True},
                     {'pubkey': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN', 'signer': False,
                      'source': 'transaction',
                      'writable': True},
                     {'pubkey': 'SysvarRecentB1ockHashes11111111111111111111', 'signer': False, 'source': 'transaction',
                      'writable': False},
                     {'pubkey': '11111111111111111111111111111111', 'signer': False, 'source': 'transaction',
                      'writable': False}],
                     'instructions': [
                         {'parsed': {
                             'info': {'nonceAccount': 'E8gPR9iQyS67j2hFmAzjywbY7rBRmT5FVMoQd8KRn4dH',
                                      'nonceAuthority': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9',
                                      'recentBlockhashesSysvar': 'SysvarRecentB1ockHashes11111111111111111111'},
                             'type': 'advanceNonce'}, 'program': 'system',
                             'programId': '11111111111111111111111111111111',
                             'stackHeight': None},
                         {'parsed': {
                             'info': {'destination': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN',
                                      'lamports': 89200,
                                      'source': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'}, 'type': 'transfer'},
                             'program': 'system',
                             'programId': '11111111111111111111111111111111',
                             'stackHeight': None}],
                     'recentBlockhash': 'GKuZPX1EvVK4j4pmCovMJGBfLDWER86Pi8Bk7ZcvVK66'},
                     'signatures': [
                         'RfUKdN2A6M12VEfekEfTTcNoDbj8tamSi2Ukxpqr5kPxwuECeUoGRcgFUPDmUuLqAA7enhqF1hMKjypAoM6qG']},
                 'version': 'legacy'}, 'id': 0}
        ]
        expected_txs_details4 = [{'success': False}]
        cls.get_tx_details(tx_details_mock_response4, expected_txs_details4)

        tx_details_mock_response5 = [
            {
                'id': 1,
                'jsonrpc': '2.0',
                'result': {'absoluteSlot': 226975974, 'blockHeight': 192071334, 'epoch': 485, 'slotIndex': 91660,
                           'slotsInEpoch': 432000, 'transactionCount': 205860574342}
            },
            {
                'jsonrpc': '2.0',
                'result': {
                    'blockTime': 1697745326,
                    'meta': {'computeUnitsConsumed': 0, 'err': None, 'fee': 5000,
                             'innerInstructions': [],
                             'logMessages': [
                                 'Program 11111111111111111111111111111111 invoke [1]',
                                 'Program 11111111111111111111111111111111 success',
                                 'Program 11111111111111111111111111111111 invoke [1]',
                                 'Program 11111111111111111111111111111111 success'],
                             'postBalances': [1658813680109510, 20000100, 1057109017, 42706560,
                                              1], 'postTokenBalances': [],
                             'preBalances': [1658814672114510, 20000100, 65109017, 42706560, 1],
                             'preTokenBalances': [], 'rewards': [], 'status': {'Ok': None}},
                    'slot': 224723044,
                    'transaction': {'message': {'accountKeys': [
                        {'pubkey': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9', 'signer': True,
                         'source': 'transaction',
                         'writable': True},
                        {'pubkey': 'Dmf5N6kLdkYUNESTqn1EEwScQCr8XebUFkV6fnS3uqGB', 'signer': False,
                         'source': 'transaction',
                         'writable': True},
                        {'pubkey': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN', 'signer': False,
                         'source': 'transaction',
                         'writable': True},
                        {'pubkey': 'SysvarRecentB1ockHashes11111111111111111111', 'signer': False,
                         'source': 'transaction',
                         'writable': False},
                        {'pubkey': '11111111111111111111111111111111', 'signer': False, 'source': 'transaction',
                         'writable': False}],
                        'instructions': [
                            {'parsed': {
                                'info': {'nonceAccount': 'Dmf5N6kLdkYUNESTqn1EEwScQCr8XebUFkV6fnS3uqGB',
                                         'nonceAuthority': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9',
                                         'recentBlockhashesSysvar': 'SysvarRecentB1ockHashes11111111111111111111'},
                                'type': 'advanceNonce'}, 'program': 'system',
                                'programId': '11111111111111111111111111111111',
                                'stackHeight': None},
                            {'parsed': {
                                'info': {'destination': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN',
                                         'lamports': 992000000,
                                         'source': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'}, 'type': 'transfer'},
                                'program': '',
                                'programId': '',
                                'stackHeight': None}],
                        'recentBlockhash': '7Vpj5nhKJprTYCrJ6qCvSKfgMjfGnzY2gmZQJLfEBje7'},
                        'signatures': [
                            '4uqoqYgYubahc7zKb2fWcwqpxkBL77DemXtgd23oVz4GTDMk4bHLt7uJLUJsF63Dv3yU3ZzXc1TbcNj9oejeS']
                    },
                    'version': 'legacy'}, 'id': 0}
        ]
        expected_txs_details5 = [{'success': False}]
        cls.get_tx_details(tx_details_mock_response5, expected_txs_details5)

    @classmethod
    def test_get_address_txs(cls):
        APIS_CONF['SOL']['get_txs'] = 'rpc_sol_explorer_interface'
        address_txs_mock_responses = [
            {
                'id': 1,
                'jsonrpc': '2.0',
                'result': {'absoluteSlot': 209611660, 'blockHeight': 192071334, 'epoch': 485, 'slotIndex': 91660,
                           'slotsInEpoch': 432000, 'transactionCount': 205860574342}
            },
            {
                'id': 0,
                'jsonrpc': '2.0',
                'result': [{
                    'blockTime': 1688145039, 'confirmationStatus': 'finalized', 'err': None, 'memo': None,
                    'signature':
                        '52cRTeHPjmaw68qrg5gQNwkv1B4NVcxzPreqXDMy8W9ES1Q2taZCb7hi9CgQ9k6Kw6M54gh3KTT6iGWyDzxsTfXE',
                    'slot': 202617637}]
            },
            [{
                'jsonrpc': '2.0',
                'result': {'blockTime': 1688145039,
                           'meta': {'computeUnitsConsumed': 0,
                                    'err': None,
                                    'fee': 19000,
                                    'innerInstructions': [],
                                    'logMessages': [
                                        'Program 11111111111111111111111111111111 invoke [1]',
                                        'Program 11111111111111111111111111111111 success',
                                        'Program ComputeBudget111111111111111111111111111111 invoke [1]',
                                        'Program ComputeBudget111111111111111111111111111111 success'],
                                    'postBalances': [0, 59781921431691, 1, 1], 'postTokenBalances': [],
                                    'preBalances': [22240000000, 59759681450691, 1, 1],
                                    'preTokenBalances': [],
                                    'rewards': [],
                                    'status': {'Ok': None}},
                           'slot': 202617637,
                           'transaction':
                               {'message': {
                                   'accountKeys': [
                                       {'pubkey': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt', 'signer': True,
                                        'source': 'transaction',
                                        'writable': True},
                                       {'pubkey': 'GJRs4FwHtemZ5ZE9x3FNvJ8TMwitKTh21yxdRPqn7npE', 'signer': False,
                                        'source': 'transaction',
                                        'writable': True},
                                       {'pubkey': '11111111111111111111111111111111', 'signer': False,
                                        'source': 'transaction',
                                        'writable': False},
                                       {'pubkey': 'ComputeBudget111111111111111111111111111111', 'signer': False,
                                        'source': 'transaction',
                                        'writable': False}],
                                   'addressTableLookups': None,
                                   'instructions': [{'parsed': {
                                       'info': {
                                           'destination': 'GJRs4FwHtemZ5ZE9x3FNvJ8TMwitKTh21yxdRPqn7npE',
                                           'lamports': 22239981000,
                                           'source': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt'},
                                       'type': 'transfer'},
                                       'program': 'system',
                                       'programId': '11111111111111111111111111111111'},
                                       {'accounts': [],
                                        'data': '3GAG5eogvTjV',
                                        'programId': 'ComputeBudget111111111111111111111111111111'}],
                                   'recentBlockhash': '2oRmhh11TKAub7yeYt3TYnk6HzPKwcb3CEpwK9SYBZEz'},
                                   'signatures':
                                       [
                                           '52cRTeHPjmaw68qrg5gQNwkv1B4NVcxzPreqXDMy8W9ES1Q2taZCb7hi9CgQ9k'
                                           '6Kw6M54gh3KTT6iGWyDzxsTfXE']},
                           'version': 'legacy'}, 'id': 1}]
        ]
        expected_addresses_txs = [
            [
                {
                    'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                    'block': 202617637,
                    'confirmations': 6994023,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt'],
                    'hash': '52cRTeHPjmaw68qrg5gQNwkv1B4NVcxzPreqXDMy8W9ES1Q2taZCb7hi9CgQ9k6Kw6M54gh3KTT6iGWyDzxsTfXE',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 6, 30, 17, 10, 39,
                                                   tzinfo=datetime.timezone.utc),
                    'value': Decimal('-22.239981000')
                },
            ]
        ]
        cls.get_address_txs(address_txs_mock_responses, expected_addresses_txs)

    @classmethod
    def test_get_block_txs(cls):
        APIS_CONF['SOL']['get_blocks_addresses'] = 'rpc_sol_explorer_interface'
        block_txs_mock_responses = [
            {
                'id': 1,
                'jsonrpc': '2.0',
                'result': {'absoluteSlot': 209611660, 'blockHeight': 192071334, 'epoch': 485, 'slotIndex': 91660,
                           'slotsInEpoch': 432000, 'transactionCount': 205860574342}
            },
            {
                'jsonrpc': '2.0',
                'result': [215481266],
                'id': 2
            },
            [
                {
                    'jsonrpc': '2.0',
                    'id': 3,
                    'result':
                        {
                            'blockHeight': 197824826,
                            'blockTime': 1693809860,
                            'blockhash': '98YCjkwB1ahzXpvpnY3HKhYSxYyufnMzysiFu4VJKczL',
                            'parentSlot': 215481265,
                            'previousBlockhash': 'Exr9GHLcKn9J3SxMoCbDjVLGRBt6uCr9pjLNbauXqNSV',
                            'transactions': [
                                {
                                    'meta': {
                                        'err': None, 'fee': 5000,
                                        'postBalances':
                                            [252668872968, 3118080, 10501000000, 1, 1141440, 145549900,
                                             934087680, 100129363687, 1461600, 13654000, 5616720],
                                        'postTokenBalances': [],
                                        'preBalances': [252671996048, 0, 10501000000, 1, 1141440, 145549900,
                                                        934087680, 100129363687, 1461600, 13654000, 5616720],
                                        'preTokenBalances': [], 'status': {'Ok': None}},
                                    'transaction': {
                                        'accountKeys': [
                                            {'pubkey': 'hadeaC5JQvAJugvsa97BPPSdeGQzhWxqK6DAqq5TsW8', 'signer': True,
                                             'source': 'transaction', 'writable': True},
                                            {'pubkey': 'BVxK4C8B2w7aAsgTdpJFDUnz46ei5VZjVmsSjEAQa3s1', 'signer': False,
                                             'source': 'transaction', 'writable': True},
                                            {'pubkey': 'ERqNAeo6LHUfgsExY9kJRuf9cR829pb1YcgehJMmEssb', 'signer': False,
                                             'source': 'transaction', 'writable': True},
                                            {'pubkey': '11111111111111111111111111111111', 'signer': False,
                                             'source': 'transaction', 'writable': False},
                                            {'pubkey': 'M2mx93ekt1fmXSVkTrUL9xVFHkmME8HTUi5Cyc5aF7K', 'signer': False,
                                             'source': 'transaction', 'writable': False},
                                            {'pubkey': 'NTYeYJ1wr4bpM5xo6zx5En44SvJFAd35zTxxNoERYqd', 'signer': False,
                                             'source': 'transaction', 'writable': False},
                                            {'pubkey': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA', 'signer': False,
                                             'source': 'transaction', 'writable': False},
                                            {'pubkey': 'autMW8SgBkVYeBgqYiTuJZnkvDZMVU2MHJh9Jh7CSQ2', 'signer': False,
                                             'source': 'transaction', 'writable': False},
                                            {'pubkey': 'va8V2GMHsC3ZfwpcGqRyR73FK6jspuPJQQVfRUjpaQs', 'signer': False,
                                             'source': 'transaction', 'writable': False},
                                            {'pubkey': 'E8cU1WiRWjanGxmn96ewBgk9vPTcL6AEZ1t6F6fkgUWe', 'signer': False,
                                             'source': 'transaction', 'writable': False},
                                            {'pubkey': 'Ezswps7RahsThaAVhJ8VH3BCwqzwPdMN4M1fT4scMsVK', 'signer': False,
                                             'source': 'transaction', 'writable': False}],
                                        'signatures': [
                                            '4qgt8khqoAb7kxJZNBSUAtPjeXYid885vsmfPTftrLRLp'
                                            'VVuBNnJwEXsDboD6VSvw2Bs8vyR6o9cbs9q1ZPDeFHj']},
                                    'version': 'legacy'},
                                {
                                    'meta': {
                                        'err': None, 'fee': 5040,
                                        'postBalances': [11012844775, 23942400, 1, 1169280, 1141440],
                                        'postTokenBalances': [],
                                        'preBalances': [11012849815, 23942400, 1, 1169280, 1141440],
                                        'preTokenBalances': [], 'status': {'Ok': None}},
                                    'transaction': {
                                        'accountKeys': [
                                            {'pubkey': 'DgAK7fPveidN72LCwCF4QjFcYHchBZbtZnjEAtgU1bMX', 'signer': True,
                                             'source': 'transaction', 'writable': True},
                                            {'pubkey': '8ihFLu5FimgTQ1Unh4dVyEHUGodJ5gJQCrQf4KUVB9bN', 'signer': False,
                                             'source': 'transaction', 'writable': True},
                                            {'pubkey': 'ComputeBudget111111111111111111111111111111', 'signer': False,
                                             'source': 'transaction', 'writable': False},
                                            {'pubkey': 'SysvarC1ock11111111111111111111111111111111', 'signer': False,
                                             'source': 'transaction', 'writable': False},
                                            {'pubkey': 'FsJ3A3u2vn5cTVofAjvy6y5kwABJAqYWpe4975bi2epH', 'signer': False,
                                             'source': 'transaction', 'writable': False}],
                                        'signatures': [
                                            '3XZDBKAXfxVgqJtFC9QtQ6AKvk3A3WZTtjP2rkj5Zi8zN'
                                            'Tm5qwBfekgKRtB2P6TjpWS6TYY8RjhytB9tRiHfV6Fc']},
                                    'version': 'legacy'},
                                {'meta': {
                                    'err': None, 'fee': 5001,
                                    'postBalances': [9171877808, 23942400, 23942400, 23942400, 23942400,
                                                     683442400, 23942400, 23942400, 23942400, 23942400, 23942400,
                                                     23942400, 23942400, 1, 1169280, 1141440],
                                    'postTokenBalances': [],
                                    'preBalances': [9171882809, 23942400, 23942400, 23942400, 23942400, 683442400,
                                                    23942400, 23942400, 23942400, 23942400, 23942400, 23942400,
                                                    23942400, 1, 1169280, 1141440], 'preTokenBalances': [],
                                    'status': {'Ok': None}},
                                    'transaction': {'accountKeys': [
                                        {'pubkey': '4dxDjABzLZQauxReFWpBdXZdgCi9P4W47w1xfLHrSzM5', 'signer': True,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'FNNvb1AFDnDVPkocEri8mWbJ1952HQZtFLuwPiUjSJQ', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': '3Qub3HaAJaa2xNY7SUqPKd3vVwTqDfDDkEUMPjXD2c1q', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': '3bNH7uDsap5nzwhCvv98i7VshjMagtx1NXTDBLbPYD66', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': '3pyn4svBbxJ9Wnn3RVeafyLWfzie6yC5eTig2S62v9SC', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': '4ivThkX8uRxBpHsdWSqyXYihzKF3zpRGAUCqyuagnLoV', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': '5ALDzwcRJfSyGdGyhP3kP628aqBNHZzLuVww7o9kdspe', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': '5bmWuR1dgP4avtGYMNKLuxumZTVKGgoN2BCMXWDNL9nY', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': '8JPJJkmDScpcNmBRKGZuPuG2GYAveQgP3t5gFuMymwvF', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'CtJ8EkqLmeYyGB8s4jevpeNsvmD4dxVR2krfsDLcvV8Y', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'ECSFWQ1bnnpqPVvoy9237t2wddZAaHisW88mYxuEHKWf', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'EcV1X1gY2yb4KXxjVQtTHTbioum2gvmPnFk4zYAt7zne', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'H6ARHf6YXhGYeQfUzQNGk6rDNnLBQKrenN712K4AQJEG', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'ComputeBudget111111111111111111111111111111', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': 'SysvarC1ock11111111111111111111111111111111', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': 'FsJ3A3u2vn5cTVofAjvy6y5kwABJAqYWpe4975bi2epH', 'signer': False,
                                         'source': 'transaction', 'writable': False}],
                                        'signatures': [
                                            '2Bmf14Nx17WyZh7w57a1qBGwPdSqe1vVTRX3RQ4LyM'
                                            'LzhVgSEyp4rTPJaYhCbStj61aNGQuTRdAcxzQ6pmHmruu8']},
                                    'version': 'legacy'},
                                {'meta': {
                                    'err': {'InstructionError': [1, {'Custom': 6003}]}, 'fee': 5000,
                                    'postBalances': [4795742531, 49054080, 2616960, 1141440, 0, 0, 1141440, 1],
                                    'postTokenBalances': [],
                                    'preBalances': [4795747531, 49054080, 2616960, 1141440, 0, 0, 1141440, 1],
                                    'preTokenBalances': [],
                                    'status': {'Err': {'InstructionError': [1, {'Custom': 6003}]}}},
                                    'transaction': {'accountKeys': [
                                        {'pubkey': '8c8inJVLSSvF9Kgxm4YJ88v5bNUS3wDRX23GFgbVjXxU', 'signer': True,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'F86tf6LbPqrUDWEoHt7vhNafaVKTVWqXefvH7BMaUBKA', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'GzGuoKXE8Unn7Vcg1DtomwD27tL4bVUpSK2M1yk6Xfz5', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'HEvSKofvBgfaexv23kMabbYqxasxU3mQ4ibBMEmJWHny', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': 'DxJ3uy4nHka6CGbz14969FoW3qckzHkHxsrfZkZyiimJ', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': 'Sysvar1nstructions1111111111111111111111111', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': 'cjg3oHmg9uuPsP8D6g29NWvhySJkdYdAo9D25PRbKXJ', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': 'ComputeBudget111111111111111111111111111111', 'signer': False,
                                         'source': 'transaction', 'writable': False}],
                                        'signatures': [
                                            '3kHyZPMg7brcvbERy5UdCG8E7ajwbxZEx6pAAEeZRcERuEegNTNEBt'
                                            'WS87HCPrgKrQhkauJi1yyNZRJbb5TGkFKP']},
                                    'version': 'legacy'},
                                {'meta': {
                                    'err': {'InstructionError': [1, {'Custom': 6001}]}, 'fee': 5000,
                                    'postBalances': [2235284999, 2039280, 686758878123, 514278270, 2039280, 1,
                                                     1141440, 173763014507, 3811756703, 0, 182981359454, 2039280,
                                                     11996367360, 4077852039280, 1141440, 934087680, 0],
                                    'postTokenBalances': [
                                        {'accountIndex': 1,
                                         'mint': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
                                         'owner': 'Hb3vcrr6kJgXAm8xmhAPdTMaigYgDH7zXBsNm8vff9fS',
                                         'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                         'uiTokenAmount': {'amount': '7384269677',
                                                           'decimals': 6,
                                                           'uiAmount': 7384.269677,
                                                           'uiAmountString': '7384.269677'}},
                                        {'accountIndex': 2,
                                         'mint': 'So11111111111111111111111111111111111111112',
                                         'owner': 'Hb3vcrr6kJgXAm8xmhAPdTMaigYgDH7zXBsNm8vff9fS',
                                         'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                         'uiTokenAmount': {'amount': '686756838843',
                                                           'decimals': 9,
                                                           'uiAmount': 686.756838843,
                                                           'uiAmountString': '686.756838843'}},
                                        {'accountIndex': 3,
                                         'mint': 'So11111111111111111111111111111111111111112',
                                         'owner': '9nnLbotNTcUhvbrsA6Mdkx45Sm82G35zo28AqUvjExn8',
                                         'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                         'uiTokenAmount': {'amount': '512238990', 'decimals': 9,
                                                           'uiAmount': 0.51223899,
                                                           'uiAmountString': '0.51223899'}},
                                        {'accountIndex': 4,
                                         'mint': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
                                         'owner': '9nnLbotNTcUhvbrsA6Mdkx45Sm82G35zo28AqUvjExn8',
                                         'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                         'uiTokenAmount': {'amount': '54063211', 'decimals': 6,
                                                           'uiAmount': 54.063211,
                                                           'uiAmountString': '54.063211'}},
                                        {'accountIndex': 11,
                                         'mint': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
                                         'owner': '3HSYXeGc3LjEPCuzoNDjQN37F1ebsSiR4CqXVqQCdekZ',
                                         'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                         'uiTokenAmount': {'amount': '131627076141',
                                                           'decimals': 6,
                                                           'uiAmount': 131627.076141,
                                                           'uiAmountString': '131627.076141'}},
                                        {'accountIndex': 13,
                                         'mint': 'So11111111111111111111111111111111111111112',
                                         'owner': '8g4Z9d6PqGkgH31tMW6FwxGhwYJrXpxZHQrkikpLJKrG',
                                         'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                         'uiTokenAmount': {'amount': '4077850000000',
                                                           'decimals': 9, 'uiAmount': 4077.85,
                                                           'uiAmountString': '4077.85'}}],
                                    'preBalances': [2235289999, 2039280, 686758878123, 514278270, 2039280, 1,
                                                    1141440, 173763014507, 3811756703, 0, 182981359454, 2039280,
                                                    11996367360, 4077852039280, 1141440, 934087680, 0],
                                    'preTokenBalances': [{'accountIndex': 1,
                                                          'mint': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
                                                          'owner': 'Hb3vcrr6kJgXAm8xmhAPdTMaigYgDH7zXBsNm8vff9fS',
                                                          'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                                          'uiTokenAmount': {'amount': '7384269677', 'decimals': 6,
                                                                            'uiAmount': 7384.269677,
                                                                            'uiAmountString': '7384.269677'}},
                                                         {'accountIndex': 2,
                                                          'mint': 'So11111111111111111111111111111111111111112',
                                                          'owner': 'Hb3vcrr6kJgXAm8xmhAPdTMaigYgDH7zXBsNm8vff9fS',
                                                          'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                                          'uiTokenAmount': {'amount': '686756838843',
                                                                            'decimals': 9,
                                                                            'uiAmount': 686.756838843,
                                                                            'uiAmountString': '686.756838843'}},
                                                         {'accountIndex': 3,
                                                          'mint': 'So11111111111111111111111111111111111111112',
                                                          'owner': '9nnLbotNTcUhvbrsA6Mdkx45Sm82G35zo28AqUvjExn8',
                                                          'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                                          'uiTokenAmount': {'amount': '512238990', 'decimals': 9,
                                                                            'uiAmount': 0.51223899,
                                                                            'uiAmountString': '0.51223899'}},
                                                         {'accountIndex': 4,
                                                          'mint': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
                                                          'owner': '9nnLbotNTcUhvbrsA6Mdkx45Sm82G35zo28AqUvjExn8',
                                                          'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                                          'uiTokenAmount': {'amount': '54063211', 'decimals': 6,
                                                                            'uiAmount': 54.063211,
                                                                            'uiAmountString': '54.063211'}},
                                                         {'accountIndex': 11,
                                                          'mint': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
                                                          'owner': '3HSYXeGc3LjEPCuzoNDjQN37F1ebsSiR4CqXVqQCdekZ',
                                                          'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                                          'uiTokenAmount': {'amount': '131627076141',
                                                                            'decimals': 6,
                                                                            'uiAmount': 131627.076141,
                                                                            'uiAmountString': '131627.076141'}},
                                                         {'accountIndex': 13,
                                                          'mint': 'So11111111111111111111111111111111111111112',
                                                          'owner': '8g4Z9d6PqGkgH31tMW6FwxGhwYJrXpxZHQrkikpLJKrG',
                                                          'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                                          'uiTokenAmount': {'amount': '4077850000000',
                                                                            'decimals': 9, 'uiAmount': 4077.85,
                                                                            'uiAmountString': '4077.85'}}],
                                    'status': {'Err': {'InstructionError': [1, {'Custom': 6001}]}}},
                                    'transaction': {'accountKeys': [
                                        {'pubkey': 'Hb3vcrr6kJgXAm8xmhAPdTMaigYgDH7zXBsNm8vff9fS', 'signer': True,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': '7YPCHEucjceuLyA5FjNB2MVZL2bxSZidnfxGjgafHpCp', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': '9CQdhWRxLwVpQuMzxQ7vLoZQUzyDd6jLEQgYUkbJhDry', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'A8kEy5wWgdW4FG593fQJ5QPVbqx1wkfXw9c4L9bPo2CN', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'EXrqY7jLTLp83H38L8Zw3GvGkk1KoQbYTckPGBghwD8X', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'ComputeBudget111111111111111111111111111111', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': 'JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': 'So11111111111111111111111111111111111111112', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': '9nnLbotNTcUhvbrsA6Mdkx45Sm82G35zo28AqUvjExn8', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': 'D8cy77BBepLMngZx6ZukaTff5hCt1HrWyKk3Hnd9oitf', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': '3HSYXeGc3LjEPCuzoNDjQN37F1ebsSiR4CqXVqQCdekZ', 'signer': False,
                                         'source': 'lookupTable', 'writable': True},
                                        {'pubkey': '4DoNfFBfF7UokCC2FQzriy7yHK6DY6NVdYpuekQ5pRgg', 'signer': False,
                                         'source': 'lookupTable', 'writable': True},
                                        {'pubkey': '8g4Z9d6PqGkgH31tMW6FwxGhwYJrXpxZHQrkikpLJKrG', 'signer': False,
                                         'source': 'lookupTable', 'writable': True},
                                        {'pubkey': 'PhoeNiXZ8ByJGLkxNfZRnkUfjvmuYqLR89jjFHGqdXY', 'signer': False,
                                         'source': 'lookupTable', 'writable': False},
                                        {'pubkey': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA', 'signer': False,
                                         'source': 'lookupTable', 'writable': False},
                                        {'pubkey': '7aDTsspkQNGKmrexAN7FLx9oxU3iPczSSvHNggyuqYkR', 'signer': False,
                                         'source': 'lookupTable', 'writable': False}],
                                        'signatures': [
                                            '3RussHg2vmxZF4F6HPhMMYumGw3AaCCeKhAm7Q8srade1P34e'
                                            'pmu9sftQCTGhgwXi4pTzKsLUvTyAmua9anV3Tbz']},
                                    'version': 0},
                                {'meta': {
                                    'err': {'InstructionError': [1, {'Custom': 6003}]}, 'fee': 5000,
                                    'postBalances': [41213408118, 49054080, 2616960, 1141440, 0, 0, 1141440, 1],
                                    'postTokenBalances': [],
                                    'preBalances': [41213413118, 49054080, 2616960, 1141440, 0, 0, 1141440, 1],
                                    'preTokenBalances': [],
                                    'status': {'Err': {'InstructionError': [1, {'Custom': 6003}]}}},
                                    'transaction': {'accountKeys': [
                                        {'pubkey': 'BEMZ2yGTwLfxb1tmWHJzURaDSwobp5L6Z6JKMATMyYK3', 'signer': True,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'F86tf6LbPqrUDWEoHt7vhNafaVKTVWqXefvH7BMaUBKA', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'GzGuoKXE8Unn7Vcg1DtomwD27tL4bVUpSK2M1yk6Xfz5', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'HEvSKofvBgfaexv23kMabbYqxasxU3mQ4ibBMEmJWHny', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': 'DxJ3uy4nHka6CGbz14969FoW3qckzHkHxsrfZkZyiimJ', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': 'Sysvar1nstructions1111111111111111111111111', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': 'cjg3oHmg9uuPsP8D6g29NWvhySJkdYdAo9D25PRbKXJ', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': 'ComputeBudget111111111111111111111111111111', 'signer': False,
                                         'source': 'transaction', 'writable': False}],
                                        'signatures': [
                                            '5Yyd7JyiJg7zvZcENyp3gg6428YmQC7ExeMxawgJtbHQSS4puV'
                                            'r4J989owZwKS5DWUezd1x9oV7DXgpidLuoe67D']},
                                    'version': 'legacy'},
                                {'meta': {
                                    'err': {'InstructionError': [1, {'Custom': 6003}]}, 'fee': 5000,
                                    'postBalances': [82043723869, 49054080, 2616960, 1141440, 0, 0, 1141440, 1],
                                    'postTokenBalances': [],
                                    'preBalances': [82043728869, 49054080, 2616960, 1141440, 0, 0, 1141440, 1],
                                    'preTokenBalances': [],
                                    'status': {'Err': {'InstructionError': [1, {'Custom': 6003}]}}},
                                    'transaction': {'accountKeys': [
                                        {'pubkey': 'Fhfv8uB5Sux1nWiw4ssDrbDdt26BPB4tfoW4Bm2on3rj', 'signer': True,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': '8tM61kiFYqDoH9Lt5KRAvDhjKCjRoc79ZsFMcZvyjf8D', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': '8vAuuqC5wVZ9Z9oQUGGDSjYgudTfjmyqGU5VucQxTk5U', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'HEvSKofvBgfaexv23kMabbYqxasxU3mQ4ibBMEmJWHny', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': 'B8ptja2KHCmJsjn2iWb84S7t2ReXDA2fPKKjV1d7sJwx', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': 'Sysvar1nstructions1111111111111111111111111', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': 'cjg3oHmg9uuPsP8D6g29NWvhySJkdYdAo9D25PRbKXJ', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': 'ComputeBudget111111111111111111111111111111', 'signer': False,
                                         'source': 'transaction', 'writable': False}],
                                        'signatures': [
                                            '46ZoKRedTt5nmSSn32fHmSLnxbknCzB9KLQEzxf5tp'
                                            'wZEZX6GY8QJUnqKqfUTZAd8kARJf6KnaRVzjceG4tt6JRU']},
                                    'version': 'legacy'},
                                {'meta': {
                                    'err': {'InstructionError': [1, {'Custom': 6001}]}, 'fee': 5000,
                                    'postBalances': [2235279999, 2039280, 2039280, 686758878123, 634891101, 1,
                                                     1141440, 173763014507, 0, 0, 182981359454, 2039280,
                                                     11996367360, 4077852039280, 1141440, 934087680, 0],
                                    'postTokenBalances': [
                                        {'accountIndex': 1,
                                         'mint': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
                                         'owner': '2MFoS3MPtvyQ4Wh4M9pdfPjz6UhVoNbFbGJAskCPCj3h',
                                         'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                         'uiTokenAmount': {'amount': '52936526', 'decimals': 6,
                                                           'uiAmount': 52.936526,
                                                           'uiAmountString': '52.936526'}},
                                        {'accountIndex': 2,
                                         'mint': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
                                         'owner': 'Hb3vcrr6kJgXAm8xmhAPdTMaigYgDH7zXBsNm8vff9fS',
                                         'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                         'uiTokenAmount': {'amount': '7384269677',
                                                           'decimals': 6,
                                                           'uiAmount': 7384.269677,
                                                           'uiAmountString': '7384.269677'}},
                                        {'accountIndex': 3,
                                         'mint': 'So11111111111111111111111111111111111111112',
                                         'owner': 'Hb3vcrr6kJgXAm8xmhAPdTMaigYgDH7zXBsNm8vff9fS',
                                         'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                         'uiTokenAmount': {'amount': '686756838843',
                                                           'decimals': 9,
                                                           'uiAmount': 686.756838843,
                                                           'uiAmountString': '686.756838843'}},
                                        {'accountIndex': 4,
                                         'mint': 'So11111111111111111111111111111111111111112',
                                         'owner': '2MFoS3MPtvyQ4Wh4M9pdfPjz6UhVoNbFbGJAskCPCj3h',
                                         'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                         'uiTokenAmount': {'amount': '632851821', 'decimals': 9,
                                                           'uiAmount': 0.632851821,
                                                           'uiAmountString': '0.632851821'}},
                                        {'accountIndex': 11,
                                         'mint': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
                                         'owner': '3HSYXeGc3LjEPCuzoNDjQN37F1ebsSiR4CqXVqQCdekZ',
                                         'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                         'uiTokenAmount':
                                             {'amount': '131627076141',
                                              'decimals': 6,
                                              'uiAmount': 131627.076141,
                                              'uiAmountString': '131627.076141'}},
                                        {'accountIndex': 13,
                                         'mint': 'So11111111111111111111111111111111111111112',
                                         'owner': '8g4Z9d6PqGkgH31tMW6FwxGhwYJrXpxZHQrkikpLJKrG',
                                         'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                         'uiTokenAmount':
                                             {'amount': '4077850000000',
                                              'decimals': 9, 'uiAmount': 4077.85,
                                              'uiAmountString': '4077.85'}}],
                                    'preBalances': [2235284999, 2039280, 2039280, 686758878123, 634891101, 1,
                                                    1141440, 173763014507, 0, 0, 182981359454, 2039280,
                                                    11996367360, 4077852039280, 1141440, 934087680, 0],
                                    'preTokenBalances': [
                                        {'accountIndex': 1,
                                         'mint': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
                                         'owner': '2MFoS3MPtvyQ4Wh4M9pdfPjz6UhVoNbFbGJAskCPCj3h',
                                         'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                         'uiTokenAmount': {'amount': '52936526', 'decimals': 6,
                                                           'uiAmount': 52.936526,
                                                           'uiAmountString': '52.936526'}},
                                        {'accountIndex': 2,
                                         'mint': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
                                         'owner': 'Hb3vcrr6kJgXAm8xmhAPdTMaigYgDH7zXBsNm8vff9fS',
                                         'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                         'uiTokenAmount': {'amount': '7384269677', 'decimals': 6,
                                                           'uiAmount': 7384.269677,
                                                           'uiAmountString': '7384.269677'}},
                                        {'accountIndex': 3,
                                         'mint': 'So11111111111111111111111111111111111111112',
                                         'owner': 'Hb3vcrr6kJgXAm8xmhAPdTMaigYgDH7zXBsNm8vff9fS',
                                         'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                         'uiTokenAmount': {'amount': '686756838843',
                                                           'decimals': 9,
                                                           'uiAmount': 686.756838843,
                                                           'uiAmountString': '686.756838843'}},
                                        {'accountIndex': 4,
                                         'mint': 'So11111111111111111111111111111111111111112',
                                         'owner': '2MFoS3MPtvyQ4Wh4M9pdfPjz6UhVoNbFbGJAskCPCj3h',
                                         'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                         'uiTokenAmount': {'amount': '632851821', 'decimals': 9,
                                                           'uiAmount': 0.632851821,
                                                           'uiAmountString': '0.632851821'}},
                                        {'accountIndex': 11,
                                         'mint': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
                                         'owner': '3HSYXeGc3LjEPCuzoNDjQN37F1ebsSiR4CqXVqQCdekZ',
                                         'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                         'uiTokenAmount': {'amount': '131627076141',
                                                           'decimals': 6,
                                                           'uiAmount': 131627.076141,
                                                           'uiAmountString': '131627.076141'}},
                                        {'accountIndex': 13,
                                         'mint': 'So11111111111111111111111111111111111111112',
                                         'owner': '8g4Z9d6PqGkgH31tMW6FwxGhwYJrXpxZHQrkikpLJKrG',
                                         'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                         'uiTokenAmount': {'amount': '4077850000000',
                                                           'decimals': 9, 'uiAmount': 4077.85,
                                                           'uiAmountString': '4077.85'}}],
                                    'status': {'Err': {'InstructionError': [1, {'Custom': 6001}]}}},
                                    'transaction': {'accountKeys': [
                                        {'pubkey': 'Hb3vcrr6kJgXAm8xmhAPdTMaigYgDH7zXBsNm8vff9fS', 'signer': True,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'JSvtokJbtGsYhneKomFBjnJh4djEQLdHV2kAeS43bBZ', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': '7YPCHEucjceuLyA5FjNB2MVZL2bxSZidnfxGjgafHpCp', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': '9CQdhWRxLwVpQuMzxQ7vLoZQUzyDd6jLEQgYUkbJhDry', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'H1qQ6Hent1C5wa4Hc3GK2V1sgg4grvDBbmKd5H8dsTmo', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'ComputeBudget111111111111111111111111111111', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': 'JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': 'So11111111111111111111111111111111111111112', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': '2MFoS3MPtvyQ4Wh4M9pdfPjz6UhVoNbFbGJAskCPCj3h', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': 'D8cy77BBepLMngZx6ZukaTff5hCt1HrWyKk3Hnd9oitf', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v', 'signer': False,
                                         'source': 'transaction', 'writable': False},
                                        {'pubkey': '3HSYXeGc3LjEPCuzoNDjQN37F1ebsSiR4CqXVqQCdekZ', 'signer': False,
                                         'source': 'lookupTable', 'writable': True},
                                        {'pubkey': '4DoNfFBfF7UokCC2FQzriy7yHK6DY6NVdYpuekQ5pRgg', 'signer': False,
                                         'source': 'lookupTable', 'writable': True},
                                        {'pubkey': '8g4Z9d6PqGkgH31tMW6FwxGhwYJrXpxZHQrkikpLJKrG', 'signer': False,
                                         'source': 'lookupTable', 'writable': True},
                                        {'pubkey': 'PhoeNiXZ8ByJGLkxNfZRnkUfjvmuYqLR89jjFHGqdXY', 'signer': False,
                                         'source': 'lookupTable', 'writable': False},
                                        {'pubkey': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA', 'signer': False,
                                         'source': 'lookupTable', 'writable': False},
                                        {'pubkey': '7aDTsspkQNGKmrexAN7FLx9oxU3iPczSSvHNggyuqYkR', 'signer': False,
                                         'source': 'lookupTable', 'writable': False}],
                                        'signatures': [
                                            '3SnTwKqzHTGAvs7xz2L9CQjUufWPmoNtJ4UjS3HmypaYPT'
                                            'dZeEyaUgPJhGmsCAxusY3aRFn3WJA6UgRM4qR6mXPW']},
                                    'version': 0},
                                {'meta': {'err': None, 'fee': 5000, 'postBalances': [12927639176, 100000000, 1],
                                          'postTokenBalances': [], 'preBalances': [12927644176, 100000000, 1],
                                          'preTokenBalances': [], 'status': {'Ok': None}}, 'transaction': {
                                    'accountKeys': [
                                        {'pubkey': '9z7sdEnttp9T9bzoRZumMcKWCU76RdmrFPi42km7Twb8', 'signer': True,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'CGj63fS6gJXm8KvaUkkL5yAZvH9cjeRgHCgJwcZZEsRd', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'Vote111111111111111111111111111111111111111', 'signer': False,
                                         'source': 'transaction', 'writable': False}],
                                    'signatures': [
                                        '2q88q4UAQnK2cxcrDv8PF3pMBtwseCyZ9R4XkrteYvK7A'
                                        'zdK1iVuFYGHaSKkHmiJMWmRTCUz62S2Cwm6cgEakUgy']},
                                 'version': 'legacy'},
                                {'meta': {'err': None, 'fee': 5000, 'postBalances': [33107962205, 9318466763, 1],
                                          'postTokenBalances': [], 'preBalances': [33107967205, 9318466763, 1],
                                          'preTokenBalances': [], 'status': {'Ok': None}}, 'transaction': {
                                    'accountKeys': [
                                        {'pubkey': 'EK26xTH6QLS5uubx12av6XrmKH2eotCwAG9r7SBhbhGb', 'signer': True,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': '2UuXvFqNmyxsNygvFUfjmDGMGn7pGQ61t5CUzvgczazW', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'Vote111111111111111111111111111111111111111', 'signer': False,
                                         'source': 'transaction', 'writable': False}],
                                    'signatures': [
                                        '23CZkLW9gT2Usv7gHBr4vxub3SfrPHRu6NnP7vm6UPjG'
                                        '5f98Lmk94xkGbaENxrvZugGuReDETVMdx2K2USUo6J2b']},
                                 'version': 'legacy'},
                                {'meta': {
                                    'err': None, 'fee': 5000, 'postBalances': [12469937568, 74627325965, 1],
                                    'postTokenBalances': [], 'preBalances': [12469942568, 74627325965, 1],
                                    'preTokenBalances': [], 'status': {'Ok': None}}, 'transaction': {
                                    'accountKeys': [
                                        {'pubkey': '6YRhtz3UHwsD61YTPZL3hWSro8dYJELUiH2STsi9P9Qi', 'signer': True,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': '7DrGM5rSgw8iCnXNxgjfmy4GFy6PuKu3gsujT5TjcDaA', 'signer': False,
                                         'source': 'transaction', 'writable': True},
                                        {'pubkey': 'Vote111111111111111111111111111111111111111', 'signer': False,
                                         'source': 'transaction', 'writable': False}],
                                    'signatures': [
                                        '3o8N97rBVDqr7sEMb4PnC4KLXDfBktYazgZWsar4ijb3a'
                                        'UY37aKrgUVme6JC7GwM1C1yrNU2C2d8j3iFedFC1tbw']},
                                    'version': 'legacy'},
                                {
                                    'meta': {
                                        'err': None, 'fee': 5000, 'postBalances': [659722560, 2000000, 1],
                                        'postTokenBalances': [], 'preBalances': [660727560, 0, 1],
                                        'preTokenBalances': [], 'status': {'Ok': None}},
                                    'transaction': {
                                        'accountKeys': [
                                            {'pubkey': '91dBvTQ2LbbuGcPxZuEARxCiJjW3UtGUumEzhx7HYR87', 'signer': True,
                                             'source': 'transaction', 'writable': True},
                                            {'pubkey': 'HTT5c1EHEEP2YbVjB98Xjcif6PRVjqfUaWPd6ZnrAm2v', 'signer': False,
                                             'source': 'transaction', 'writable': True},
                                            {'pubkey': '11111111111111111111111111111111', 'signer': False,
                                             'source': 'transaction', 'writable': False}],
                                        'signatures': [
                                            '24yXaPDEeHSii5kqDKcxsgm8S17GB7BibM9GgUC2ZfpXi'
                                            '2RQx6AWUBHHmUgHSSHySRAnLbHKrxieuUzSBrXUz2dW']},
                                    'version': 'legacy'}
                            ]
                        }
                }
            ]
        ]
        expected_txs_addresses = {
            'input_addresses': {'91dBvTQ2LbbuGcPxZuEARxCiJjW3UtGUumEzhx7HYR87'},
            'output_addresses': {'HTT5c1EHEEP2YbVjB98Xjcif6PRVjqfUaWPd6ZnrAm2v'},
        }
        expected_txs_info = {
            'outgoing_txs': {
                '91dBvTQ2LbbuGcPxZuEARxCiJjW3UtGUumEzhx7HYR87': {
                    Currencies.sol: [
                        {
                            'contract_address': None,
                            'tx_hash': '24yXaPDEeHSii5kqDKcxsgm8S17GB7BibM'
                                       '9GgUC2ZfpXi2RQx6AWUBHHmUgHSSHySRAnLbHKrxieuUzSBrXUz2dW',
                            'value': Decimal('0.002000000'), 'symbol': 'SOL', 'block_height': 215481266,
                        },
                    ]
                },
            },
            'incoming_txs': {
                'HTT5c1EHEEP2YbVjB98Xjcif6PRVjqfUaWPd6ZnrAm2v': {
                    Currencies.sol: [
                        {
                            'contract_address': None,
                            'tx_hash': '24yXaPDEeHSii5kqDKcxsgm8S17GB7BibM9GgUC2Zf'
                                       'pXi2RQx6AWUBHHmUgHSSHySRAnLbHKrxieuUzSBrXUz2dW',
                            'value': Decimal('0.002000000'), 'symbol': 'SOL', 'block_height': 215481266,
                        }
                    ]
                },
            }
        }
        cls.get_block_txs(block_txs_mock_responses, expected_txs_addresses, expected_txs_info)


def test__parse_address_txs_response__for_multi_transfer__should_filter_other_addresses_transfers(
        sol_raw_multi_transfer_address_txs,
        sol_multi_transfer_address):
    result = RpcSolParser.parse_address_txs_response(address=sol_multi_transfer_address,
                                                     address_txs_response=sol_raw_multi_transfer_address_txs,
                                                     block_head=316698441)
    expected_results = [
        TransferTx(
            block_hash=None,
            block_height=316514709,
            confirmations=183732,
            date=datetime.datetime(2025, 1, 26, 15, 27, tzinfo=pytz.UTC),
            from_address='GagXj5rERPBfiaEEdJ87trQrdmo2i7tLWq17vMJ7q8xv',
            index=None,
            memo=None,
            success=True,
            symbol='SOL',
            to_address='H6CnHUQ3ZBi3AmeQhrQtfx2mo2YEghStkbX4KdLnVvrQ',
            token=None,
            tx_fee=Decimal('0.000005000'),
            tx_hash='4gS19hrer6Cx6H2f6wEM594vS5qsFTHZ3Ci36rgDL9Z4HZcnYsqPLupoHcW6xQXmrkh7ZEqB9dAxZ1huUcs7uBCc',
            value=Decimal('0.001000000'),

        )
    ]
    assert result == expected_results
