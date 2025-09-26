import re
import pytest
from decimal import Decimal
from unittest import TestCase
from exchange.base.models import Currencies
from exchange.blockchain.api.sol.getblock_sol import GetBlockSolApi
from exchange.blockchain.api.sol.sol_explorer_interface import SolExplorerInterface
from exchange.blockchain.apis_conf import APIS_CONF
from exchange.blockchain.tests.api.general_test.general_test_from_explorer import TestFromExplorer


class TestGetBlockSolApiCalls(TestCase):
    api = GetBlockSolApi
    addresses = ['ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt']
    txs_hash = ['57rfrAKFTMyretUzDMy2TLY6UX7VNq2uzFgdpLufztgK75kCxZnhmoUbhqpoyeTeacT76Nak2HJjrVa9o2wZSVhV']
    block_height = [232643901]

    @pytest.mark.slow
    def test_get_balance_api(self):
        for address in self.addresses:
            get_balance_result = self.api.get_balance(address)
            assert isinstance(get_balance_result, dict)
            assert {'result'}.issubset(set(get_balance_result.keys()))
            assert isinstance(get_balance_result.get('result'), dict)
            assert isinstance(get_balance_result.get('result').get('value'), int)

    @pytest.mark.slow
    def test_get_balances_api(self):
        get_balances_result = self.api.get_balances(list(set(self.addresses)))
        assert isinstance(get_balances_result, dict)
        assert {'result'}.issubset(set(get_balances_result.keys()))
        assert isinstance(get_balances_result.get('result').get('value'), list)
        for balance in get_balances_result.get('result').get('value'):
            assert isinstance(balance.get('lamports'), int)

    @pytest.mark.slow
    def test_get_block_head_api(self):
        get_block_head_response = self.api.get_block_head()
        assert isinstance(get_block_head_response, dict)
        assert {'result'}.issubset(set(get_block_head_response.keys()))
        assert isinstance(get_block_head_response.get('result'), dict)
        assert isinstance(get_block_head_response.get('result').get('absoluteSlot'), int)

    @pytest.mark.slow
    def test_get_block_txs_api(self):  # you may need to update the block_height
        for block in self.block_height:
            get_block_txs_result = self.api.get_block_txs(block)
            assert isinstance(get_block_txs_result, dict)
            assert {'result'}.issubset(set(get_block_txs_result.keys()))
            assert isinstance(get_block_txs_result.get('result'), dict)
            assert isinstance(get_block_txs_result.get('result').get('transactions'), list)
            for tx in get_block_txs_result.get('result').get('transactions'):
                if tx.get('meta').get('err') \
                        or tx.get('meta').get('status').get('Err') \
                        or 'Ok' not in tx.get('meta').get('status').keys() \
                        or not tx.get('transaction').get('signatures'):
                    continue
                for transfer in tx.get('transaction').get('message').get('instructions'):
                    if transfer.get('program') != 'system' \
                            or transfer.get('programId') != '11111111111111111111111111111111' \
                            or transfer.get('parsed').get('type') not in ['transfer', 'transferChecked']:
                        continue
                    assert isinstance(tx.get('transaction').get('signatures')[0], str)
                    assert isinstance(transfer.get('parsed').get('info').get('source'), str)
                    assert isinstance(transfer.get('parsed').get('info').get('destination'), str)
                    assert isinstance(transfer.get('parsed').get('info').get('lamports'), int)


class TestGetBlockSolApiFromExplorer(TestFromExplorer):
    api = GetBlockSolApi
    addresses = ['6h7Ce5MfeuUP4gqMfQkM9GanBrZDvBcuxK6RX8qLSWAP', 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt']
    txs_addresses = ['ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt']
    txs_hash = ['57rfrAKFTMyretUzDMy2TLY6UX7VNq2uzFgdpLufztgK75kCxZnhmoUbhqpoyeTeacT76Nak2HJjrVa9o2wZSVhV']
    symbol = 'SOL'
    currencies = Currencies.sol
    explorerInterface = SolExplorerInterface

    @classmethod
    def test_get_balance(cls):
        balance_mock_responses = [
            {
                'id': 1, 'jsonrpc': '2.0',
                'result':
                    {
                        'context': {'apiVersion': '1.14.19', 'slot': 208620002},
                        'value': 43566144773
                    }
            },
            {
                'id': 1, 'jsonrpc': '2.0',
                'result':
                    {
                        'context': {'apiVersion': '1.14.19', 'slot': 208620002},
                        'value': 49446075176
                    }
            }
        ]
        expected_balances = [
            {
                'address': '6h7Ce5MfeuUP4gqMfQkM9GanBrZDvBcuxK6RX8qLSWAP',
                'balance': Decimal('43.566144773'),
                'received': Decimal('43.566144773'),
                'sent': Decimal('0'),
                'rewarded': Decimal('0')
            },
            {
                'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                'balance': Decimal('49.446075176'),
                'received': Decimal('49.446075176'),
                'sent': Decimal('0'),
                'rewarded': Decimal('0')
            }
        ]
        cls.api.SUPPORT_GET_BALANCE_BATCH = False
        cls.get_balance(balance_mock_responses, expected_balances)

    @classmethod
    def test_get_balances(cls):
        balances_mock_responses = [
            {
                'jsonrpc': '2.0', 'id': 1,
                'result': {
                    'context': {'apiVersion': '1.14.22', 'slot': 209549643},
                    'value': [
                        {'data': ['', 'base64'], 'executable': False, 'lamports': 38484562093,
                         'owner': '11111111111111111111111111111111', 'rentEpoch': 361},
                        {'data': ['', 'base64'], 'executable': False, 'lamports': 46110908375,
                         'owner': '11111111111111111111111111111111', 'rentEpoch': 0}
                    ]
                }
            }
        ]
        expected_balances = [
            {
                'address': '6h7Ce5MfeuUP4gqMfQkM9GanBrZDvBcuxK6RX8qLSWAP',
                'balance': Decimal('38.484562093'),
                'received': Decimal('38.484562093'),
                'sent': Decimal('0'),
                'rewarded': Decimal('0')
            },
            {
                'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                'balance': Decimal('46.110908375'),
                'received': Decimal('46.110908375'),
                'sent': Decimal('0'),
                'rewarded': Decimal('0')
            }
        ]
        cls.api.SUPPORT_GET_BALANCE_BATCH = True
        cls.get_balance(balances_mock_responses, expected_balances)

    @classmethod
    def test_get_block_txs(cls):
        APIS_CONF['SOL']['get_blocks_addresses'] = 'sol_explorer_interface'
        block_txs_mock_responses = [
            {
                'jsonrpc': '2.0',
                'result': {
                    'absoluteSlot': 334470571,
                    'blockTime': 1700965675,
                },
                'id': 1
            },
            {
                'jsonrpc': '2.0',
                'result': {
                    'blockHeight': 191470571,
                    'blockTime': 1690978375,
                    'blockhash': '2Vz2PeMXjnQzC6SVbSDyEUtCHWbxTfKAgh4qDJMZXvZV',
                    'parentSlot': 209000000,
                    'previousBlockhash': '4dFpdgW6adpv1gYUKHpXc1zTM8UiFyfuJCZv75tkMARB',
                    'transactions': [
                        {'meta':
                            {
                                'computeUnitsConsumed': 39099,
                                'err': None,
                                'fee': 105000,
                                'innerInstructions':
                                    [{
                                        'index': 4,
                                        'instructions': [
                                            {'parsed': {
                                                'info': {
                                                    'lamports': 1113600,
                                                    'newAccount': 'AzF6aqTwNdzKxb2R59545gXfdeJfBX6EALRxsmR1Hdi7',
                                                    'owner': '9ehXDD5bnhSpFVRf99veikjgq8VajtRH7e3D9aVPLqYd',
                                                    'source': 'D9C8BXwJDzrph3RAqdFFrd2ctWyTRM51k1Ydgx77cPui',
                                                    'space': 32},
                                                'type': 'createAccount'},
                                                'program': 'system',
                                                'programId': '11111111111111111111111111111111'},
                                            {'parsed': {
                                                'info': {
                                                    'amount': '379000000',
                                                    'authority': 'D9C8BXwJDzrph3RAqdFFrd2ctWyTRM51k1Ydgx77cPui',
                                                    'destination': 'CeorfAKXwmKcPkaLd4Aoh8XBz27kTv9yP4kzsqhpBQVh',
                                                    'source': '5TjNEMCvBpDrByKST6BeSpi2Dsty3VqtU14HKNwV8qJY'},
                                                'type': 'transfer'},
                                                'program': 'spl-token',
                                                'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'}]
                                    }],
                                'logMessages': ['Program ComputeBudget111111111111111111111111111111 invoke [1]',
                                                'Program ComputeBudget111111111111111111111111111111 success',
                                                'Program ComputeBudget111111111111111111111111111111 invoke [1]',
                                                'Program ComputeBudget111111111111111111111111111111 success',
                                                'Program 11111111111111111111111111111111 invoke [1]',
                                                'Program 11111111111111111111111111111111 success',
                                                'Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA invoke [1]',
                                                'Program log: Instruction: SyncNative',
                                                'Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA consumed 3045 of 1000000 compute units',
                                                'Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA success',
                                                'Program 9ehXDD5bnhSpFVRf99veikjgq8VajtRH7e3D9aVPLqYd invoke [1]',
                                                'Program log: Instruction: BuyTickets',
                                                'Program 11111111111111111111111111111111 invoke [2]',
                                                'Program 11111111111111111111111111111111 success',
                                                'Program log: 379000000 379000000',
                                                'Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA invoke [2]',
                                                'Program log: Instruction: Transfer',
                                                'Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA consumed 4736 of 969196 compute units',
                                                'Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA success',
                                                'Program log: Total entrants: 4, 4, 10',
                                                'Program 9ehXDD5bnhSpFVRf99veikjgq8VajtRH7e3D9aVPLqYd consumed 36054 of 996955 compute units',
                                                'Program 9ehXDD5bnhSpFVRf99veikjgq8VajtRH7e3D9aVPLqYd success'],
                                'postBalances':
                                    [1345334298, 12138240, 2039280, 4231680, 1113600, 1518039280, 1, 1141440, 1,
                                     934087680],
                                'postTokenBalances': [
                                    {'accountIndex': 2, 'mint': 'So11111111111111111111111111111111111111112',
                                     'owner': 'D9C8BXwJDzrph3RAqdFFrd2ctWyTRM51k1Ydgx77cPui',
                                     'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                     'uiTokenAmount': {'amount': '0', 'decimals': 9, 'uiAmount': None,
                                                       'uiAmountString': '0'}},
                                    {'accountIndex': 5, 'mint': 'So11111111111111111111111111111111111111112',
                                     'owner': 'AeCTksRNJm7mJPJAdxL8cCBPjj6vou3RCSQhP9Qe9N5f',
                                     'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                     'uiTokenAmount': {'amount': '1516000000', 'decimals': 9, 'uiAmount': 1.516,
                                                       'uiAmountString': '1.516'}}],
                                'preBalances': [1725552898, 12138240, 2039280, 4231680, 0, 1139039280, 1, 1141440, 1,
                                                934087680],
                                'preTokenBalances': [
                                    {'accountIndex': 2, 'mint': 'So11111111111111111111111111111111111111112',
                                     'owner': 'D9C8BXwJDzrph3RAqdFFrd2ctWyTRM51k1Ydgx77cPui',
                                     'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                     'uiTokenAmount': {'amount': '0', 'decimals': 9, 'uiAmount': None,
                                                       'uiAmountString': '0'}},
                                    {'accountIndex': 5, 'mint': 'So11111111111111111111111111111111111111112',
                                     'owner': 'AeCTksRNJm7mJPJAdxL8cCBPjj6vou3RCSQhP9Qe9N5f',
                                     'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                     'uiTokenAmount': {'amount': '1137000000', 'decimals': 9, 'uiAmount': 1.137,
                                                       'uiAmountString': '1.137'}}], 'rewards': None,
                                'status': {'Ok': None}}, 'transaction': {'message': {'accountKeys': [
                            {'pubkey': 'D9C8BXwJDzrph3RAqdFFrd2ctWyTRM51k1Ydgx77cPui', 'signer': True,
                             'source': 'transaction',
                             'writable': True},
                            {'pubkey': '5JubhL2EgC5CF1URqmt6WV9CcCqhESyA4U3pUdFKmnrY', 'signer': False,
                             'source': 'transaction',
                             'writable': True},
                            {'pubkey': '5TjNEMCvBpDrByKST6BeSpi2Dsty3VqtU14HKNwV8qJY', 'signer': False,
                             'source': 'transaction',
                             'writable': True},
                            {'pubkey': 'AeCTksRNJm7mJPJAdxL8cCBPjj6vou3RCSQhP9Qe9N5f', 'signer': False,
                             'source': 'transaction',
                             'writable': True},
                            {'pubkey': 'AzF6aqTwNdzKxb2R59545gXfdeJfBX6EALRxsmR1Hdi7', 'signer': False,
                             'source': 'transaction',
                             'writable': True},
                            {'pubkey': 'CeorfAKXwmKcPkaLd4Aoh8XBz27kTv9yP4kzsqhpBQVh', 'signer': False,
                             'source': 'transaction',
                             'writable': True},
                            {'pubkey': '11111111111111111111111111111111', 'signer': False, 'source': 'transaction',
                             'writable': False},
                            {'pubkey': '9ehXDD5bnhSpFVRf99veikjgq8VajtRH7e3D9aVPLqYd', 'signer': False,
                             'source': 'transaction',
                             'writable': False},
                            {'pubkey': 'ComputeBudget111111111111111111111111111111', 'signer': False,
                             'source': 'transaction',
                             'writable': False},
                            {'pubkey': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA', 'signer': False,
                             'source': 'transaction',
                             'writable': False}], 'addressTableLookups': None, 'instructions': [
                            {'accounts': [], 'data': '3gJqkocMWaMm',
                             'programId': 'ComputeBudget111111111111111111111111111111'},
                            {'accounts': [], 'data': 'FjL4FH',
                             'programId': 'ComputeBudget111111111111111111111111111111'}, {
                                'parsed': {
                                    'info': {'destination': '5TjNEMCvBpDrByKST6BeSpi2Dsty3VqtU14HKNwV8qJY',
                                             'lamports': 379000000,
                                             'source': 'D9C8BXwJDzrph3RAqdFFrd2ctWyTRM51k1Ydgx77cPui'},
                                    'type': 'transfer'},
                                'program': 'system', 'programId': '11111111111111111111111111111111'},
                            {'parsed': {'info': {'account': '5TjNEMCvBpDrByKST6BeSpi2Dsty3VqtU14HKNwV8qJY'},
                                        'type': 'syncNative'},
                             'program': 'spl-token', 'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'}, {
                                'accounts': ['AeCTksRNJm7mJPJAdxL8cCBPjj6vou3RCSQhP9Qe9N5f',
                                             '5JubhL2EgC5CF1URqmt6WV9CcCqhESyA4U3pUdFKmnrY',
                                             'AzF6aqTwNdzKxb2R59545gXfdeJfBX6EALRxsmR1Hdi7',
                                             'CeorfAKXwmKcPkaLd4Aoh8XBz27kTv9yP4kzsqhpBQVh',
                                             '5TjNEMCvBpDrByKST6BeSpi2Dsty3VqtU14HKNwV8qJY',
                                             'D9C8BXwJDzrph3RAqdFFrd2ctWyTRM51k1Ydgx77cPui',
                                             'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',
                                             '11111111111111111111111111111111'],
                                'data': 'fqbQGFA49afYQmdGgUyigdfjjVH',
                                'programId': '9ehXDD5bnhSpFVRf99veikjgq8VajtRH7e3D9aVPLqYd'}],
                            'recentBlockhash': 'HXqaqmKrfPmvvoeFECufBbAkDDz6MJ9cRzona31JFQQz'},
                            'signatures': [
                                'AWrj8gSEycZY9PkjsxGHziYQuz5n8FC4AmxbSvxet7sMsen5KCpm6babXNpFQgeayytsPqmY5iV9FvoYeuyg1n3']},
                            'version': 'legacy'}
                    ]
                },
                'id': 1
            },
            {'id': 1, 'jsonrpc': '2.0',
             'result': {'blockHeight': 214315389, 'blockTime': 1701125392,
                        'blockhash': 'FCYsS6JQytNp1at77Ay8ZHCGjuVxaSTtJvUDvwkJZeX3',
                        'parentSlot': 232642699,
                        'previousBlockhash': 'BoYUbK9nK3Ya4U47rJK11fG9ZEzECSaoh68PFURdYM2b',
                        },
             },
            {'blockHeight': 214316341, 'blockTime': 1701125823,
             'blockhash': '6ohS6AGrVuk54gELoANvCS4rYB4zZaED7QghAdXUdbW7', 'parentSlot': 232643700,
             'previousBlockhash': 'GYd49BxYJVhjsqxmKMRQAgSNUyVHGj9RggPEAHyg84gd'
             },
            {'blockHeight': 214316441, 'blockTime': 1701125865,
             'blockhash': '2T376Y5zcHT8WWMBPCBbE77VpmNwJYvcKzTZa4cMMvAC', 'parentSlot': 232643800,
             'previousBlockhash': 'HArrVR8YSswxtoedgrNec1u8uvG3K3iiFggJrGPyxvuT'},
            {'blockHeight': 214316541, 'blockTime': 1701125910,
             'blockhash': 'DbqVyqYawRWhEAyyPPmkNS4BfNNNNa8xoFZ4SaWeDUBQ', 'parentSlot': 232643900,
             'previousBlockhash': 'E1DcMzvSPrRK2yoEhtF9Cm59EsJEKogk9f851M7KZTpv'}
        ]
        expected_txs_addresses = {
            'input_addresses': {'D9C8BXwJDzrph3RAqdFFrd2ctWyTRM51k1Ydgx77cPui'},
            'output_addresses': {'5TjNEMCvBpDrByKST6BeSpi2Dsty3VqtU14HKNwV8qJY'},
        }
        expected_txs_info = {
            'outgoing_txs': {
                'D9C8BXwJDzrph3RAqdFFrd2ctWyTRM51k1Ydgx77cPui': {
                    Currencies.sol: [{
                        'contract_address': None,
                        'tx_hash':
                            'AWrj8gSEycZY9PkjsxGHziYQuz5n8FC4AmxbSvxet7sMsen5KCpm6babXNpFQgeayytsPqmY5iV9FvoYeuyg1n3',
                        'value': Decimal('0.379000000'), 'symbol': 'SOL', 'block_height': None}]},
            },
            'incoming_txs': {
                '5TjNEMCvBpDrByKST6BeSpi2Dsty3VqtU14HKNwV8qJY': {
                    Currencies.sol: [{
                        'contract_address': None,
                        'tx_hash':
                            'AWrj8gSEycZY9PkjsxGHziYQuz5n8FC4AmxbSvxet7sMsen5KCpm6babXNpFQgeayytsPqmY5iV9FvoYeuyg1n3',
                        'value': Decimal('0.379000000'), 'symbol': 'SOL', 'block_height': None}]},
            }
        }
        cls.get_block_txs(block_txs_mock_responses, expected_txs_addresses, expected_txs_info)
