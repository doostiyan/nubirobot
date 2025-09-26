import datetime
from decimal import Decimal
from unittest import TestCase

import pytest
from exchange.base.models import Currencies
from exchange.blockchain.api.sol.sol_explorer_interface import SolExplorerInterface
from exchange.blockchain.api.sol.solanabeach_sol import SolanaBeachSolApi
from exchange.blockchain.apis_conf import APIS_CONF
from exchange.blockchain.tests.api.general_test.general_test_from_explorer import TestFromExplorer


class TestSolanaBeachSolApiCalls(TestCase):
    api = SolanaBeachSolApi
    addresses = ['Fi5Lw5opNWcs4iSMxEUBaXS9wzy9Td9k2VoBfpNwzZoD']
    txs_hash = ['57rfrAKFTMyretUzDMy2TLY6UX7VNq2uzFgdpLufztgK75kCxZnhmoUbhqpoyeTeacT76Nak2HJjrVa9o2wZSVhV']

    @pytest.mark.slow
    def test_get_balance_api(self):
        for address in self.addresses:
            get_balance_result = self.api.get_balance(address)
            assert {'balance'}.issubset(set(get_balance_result.get('value').get('base').keys()))
            assert isinstance(get_balance_result.get('value').get('base').get('balance'), int)

    @pytest.mark.slow
    def test_get_block_head_api(self):
        get_block_head_response = self.api.get_block_head()
        assert {'currentSlot'}.issubset(set(get_block_head_response.keys()))
        assert isinstance(get_block_head_response.get('currentSlot'), int)

    @pytest.mark.slow
    def test_get_tx_details_api(self):
        for tx_hash in self.txs_hash:
            get_details_tx_response = self.api.get_tx_details(tx_hash)
            assert isinstance(get_details_tx_response, dict)
            assert ({'transactionHash', 'blockNumber', 'meta', 'valid', 'instructions', 'blocktime'}
                    .issubset(set(get_details_tx_response.keys())))
            keys2check = [('transactionHash', str), ('blockNumber', int), ('meta', dict), ('valid', bool),
                          ('instructions', list), ('blocktime', dict)]
            for key, value in keys2check:
                assert isinstance(get_details_tx_response.get(key), value)
            assert isinstance(get_details_tx_response.get('blocktime').get('absolute'), int)
            for tx in get_details_tx_response.get('instructions'):
                if not tx.get('parsed'):
                    continue
                assert isinstance(tx.get('parsed'), dict)
                assert isinstance(tx.get('parsed').get('Transfer'), dict)
                assert isinstance(tx.get('parsed').get('Transfer').get('lamports'), int)
                assert isinstance(tx.get('parsed').get('Transfer').get('account').get('address'), str)
                assert isinstance(tx.get('parsed').get('Transfer').get('recipient').get('address'), str)

    @pytest.mark.slow
    def test_get_address_txs_api(self):
        for address in self.addresses:
            get_address_txs_response = self.api.get_address_txs(address)
            assert isinstance(get_address_txs_response, list)
            for tx in get_address_txs_response:
                assert ({'transactionHash', 'blockNumber', 'meta', 'valid', 'instructions', 'blocktime'}
                        .issubset(set(tx.keys())))
                keys2check = [('transactionHash', str), ('blockNumber', int), ('meta', dict), ('valid', bool),
                              ('instructions', list), ('blocktime', dict)]
                for key, value in keys2check:
                    assert isinstance(tx.get(key), value)
                assert isinstance(tx.get('blocktime').get('absolute'), int)
                for transfer in tx.get('instructions'):
                    if not transfer.get('parsed'):
                        continue
                    assert isinstance(transfer.get('parsed'), dict)
                    assert isinstance(transfer.get('parsed').get('Transfer'), dict)
                    assert isinstance(transfer.get('parsed').get('Transfer').get('lamports'), int)
                    assert isinstance(transfer.get('parsed').get('Transfer').get('account').get('address'), str)
                    assert isinstance(transfer.get('parsed').get('Transfer').get('recipient').get('address'), str)


class TestSolanaBeachFromExplorer(TestFromExplorer):
    api = SolanaBeachSolApi
    addresses = ['ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt']
    txs_addresses = ['ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt']
    txs_hash = ['57rfrAKFTMyretUzDMy2TLY6UX7VNq2uzFgdpLufztgK75kCxZnhmoUbhqpoyeTeacT76Nak2HJjrVa9o2wZSVhV']
    symbol = 'SOL'
    currencies = Currencies.sol
    explorerInterface = SolExplorerInterface

    @classmethod
    def test_get_balance(cls):
        balance_mock_responses = [
            {
                "type": "system",
                "value": {
                    "base": {
                        "address": {
                            "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                        },
                        "balance": 49446075176,
                        "executable": False,
                        "owner": {
                            "name": "System Program",
                            "address": "11111111111111111111111111111111"
                        },
                        "rentEpoch": 0,
                        "dataSize": 0,
                        "rentExemptReserve": 890880
                    },
                    "extended": {}
                }
            }
        ]
        expected_balances = [
            {
                'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                'balance': Decimal('49.446075176'),
                'received': Decimal('49.446075176'),
                'sent': Decimal('0'),
                'rewarded': Decimal('0')
            }
        ]
        APIS_CONF['SOL']['get_balances'] = 'sol_explorer_interface'
        cls.get_balance(balance_mock_responses, expected_balances)

    @classmethod
    @pytest.mark.django_db
    def test_get_tx_details(cls):
        tx_details_mock_responses1 = [
            {
                "boundaries": {
                    "start": 208498472,
                    "end": 208598472
                },
                "window": 100000,
                "networkLag": 6,
                "currentSlot": 208598478
            },
            {
                "transactionHash":
                    "57rfrAKFTMyretUzDMy2TLY6UX7VNq2uzFgdpLufztgK75kCxZnhmoUbhqpoyeTeacT76Nak2HJjrVa9o2wZSVhV",
                "blockNumber": 202617447,
                "accounts": [
                    {
                        "account": {
                            "address": "7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj"
                        },
                        "writable": True,
                        "signer": True
                    },
                    {
                        "account": {
                            "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                        },
                        "writable": True,
                        "signer": False
                    },
                    {
                        "account": {
                            "name": "System Program",
                            "address": "11111111111111111111111111111111"
                        },
                        "writable": False,
                        "signer": False,
                        "program": True
                    }
                ],
                "header": {
                    "numReadonlySignedAccounts": 0,
                    "numReadonlyUnsignedAccounts": 1,
                    "numRequiredSignatures": 1
                },
                "instructions": [
                    {
                        "parsed": {
                            "TransferSol": {
                                "amount": 22240000000,
                                "source": {
                                    "address": "7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj"
                                },
                                "destination": {
                                    "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                                },
                                "signers": [
                                    {
                                        "address": "7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj"
                                    }
                                ],
                                "writable": [
                                    {
                                        "address": "7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj"
                                    },
                                    {
                                        "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                                    }
                                ]
                            }
                        },
                        "programId": {
                            "name": "System Program",
                            "address": "11111111111111111111111111111111"
                        }
                    }
                ],
                "recentBlockhash": "3zg4nvFFSWJCMVUpF4iE5ExS4f95PD32XF9KRvKDLr3N",
                "signatures": [
                    "57rfrAKFTMyretUzDMy2TLY6UX7VNq2uzFgdpLufztgK75kCxZnhmoUbhqpoyeTeacT76Nak2HJjrVa9o2wZSVhV"
                ],
                "meta": {
                    "computeUnitsConsumed": 0,
                    "err": None,
                    "fee": 5000,
                    "loadedAddresses": {
                        "readonly": [],
                        "writable": []
                    },
                    "logMessages": [
                        "Program 11111111111111111111111111111111 invoke [1]",
                        "Program 11111111111111111111111111111111 success"
                    ],
                    "postBalances": [
                        1982180308,
                        22240000000,
                        1
                    ],
                    "postTokenBalances": [],
                    "preBalances": [
                        24222185308,
                        0,
                        1
                    ],
                    "preTokenBalances": [],
                    "rewards": [],
                    "status": {
                        "Ok": None
                    }
                },
                "valid": True,
                "blocktime": {
                    "absolute": 1688144949,
                    "relative": 1688144950
                },
                "mostImportantInstruction": {
                    "name": "Transfer",
                    "weight": 0.5,
                    "index": 0
                },
                "smart": [
                    {
                        "type": "address",
                        "value": {
                            "address": "7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj"
                        }
                    },
                    {
                        "type": "text",
                        "value": "transferred"
                    },
                    {
                        "type": "amount",
                        "value": 22240000000
                    },
                    {
                        "type": "text",
                        "value": "to"
                    },
                    {
                        "type": "address",
                        "value": {
                            "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                        }
                    }
                ]
            }
        ]
        expected_txs_details1 = [
            {
                'success': True,
                'block': 202617447,
                'date': datetime.datetime(2023, 6, 30, 17, 9, 9,
                                          tzinfo=datetime.timezone.utc),
                'raw': None,
                'inputs': [],
                'outputs': [],
                'transfers': [
                    {
                        'type': 'MainCoin',
                        'symbol': 'SOL',
                        'currency': 37,
                        'to': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                        'value': Decimal('22.240000000'),
                        'is_valid': True,
                        'token': None,
                        'memo': None,
                        'from': '7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj'
                    }
                ],
                'fees': None,
                'memo': None,
                'confirmations': 5981031,
                'hash': '57rfrAKFTMyretUzDMy2TLY6UX7VNq2uzFgdpLufztgK75kCxZnhmoUbhqpoyeTeacT76Nak2HJjrVa9o2wZSVhV'
            }
        ]
        APIS_CONF['SOL']['txs_details'] = 'sol_explorer_interface'
        cls.get_tx_details(tx_details_mock_responses1, expected_txs_details1)

        tx_details_mock_responses2 = [
            {
                "boundaries": {
                    "start": 208498472,
                    "end": 208598472
                },
                "window": 100000,
                "networkLag": 6,
                "currentSlot": 208598478
            },
            {
                'transactionHash':
                    '4hyCo6poqsgDhyRbdsDAGeB4U7ioP2x1etZW2og4eSKrwttUzXxpvsjJfxVf9bqptFyQkvDH6wis9VxMsrb8',
                'blockNumber': 226876286,
                'accounts': [
                    {'account': {'address': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'}, 'writable': True,
                     'signer': True},
                    {'account': {'address': '8xSH84dD2uNTipwVbqA37Z7vzinuxLDWd4VBpVbnXtAq'}, 'writable': True,
                     'signer': False},
                    {'account': {'address': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN'}, 'writable': True,
                     'signer': False},
                    {'account': {'name': 'Sysvar: Recent Blockhashes',
                                 'address': 'SysvarRecentB1ockHashes11111111111111111111'},
                     'writable': False, 'signer': False},
                    {'account': {'name': 'System Program', 'address': '11111111111111111111111111111111'},
                     'writable': False, 'signer': False, 'program': True}],
                'header': {'numReadonlySignedAccounts': 0, 'numReadonlyUnsignedAccounts': 2,
                           'numRequiredSignatures': 1},
                'instructions': [{'parsed': {
                    'AdvanceNonceAccount':
                        {'nonceAccount': {'address': '8xSH84dD2uNTipwVbqA37Z7vzinuxLDWd4VBpVbnXtAq'},
                         'recentBlockhashesSysVar': {'name': 'Sysvar: Recent Blockhashes',
                                                     'address': 'SysvarRecentB1ockHashes11111111111111111111'},
                         'nonceAuthority': {
                             'address': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'},
                         'signers': [{'address': '8xSH84dD2uNTipwVbqA37Z7vzinuxLDWd4VBpVbnXtAq'},
                                     {'address': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'}],
                         'writable': [{'address': '8xSH84dD2uNTipwVbqA37Z7vzinuxLDWd4VBpVbnXtAq'}]}},
                    'programId': {'name': 'System Program',
                                  'address': '11111111111111111111111111111111'}},
                    {'parsed': {
                        'Transfer':
                            {'lamports': 109200,
                             'account': {
                                 'address': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'},
                             'recipient': {
                                 'address': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN'},
                             'signers': [{
                                 'address': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'}],
                             'writable': [{
                                 'address': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'},
                                 {
                                     'address': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN'}]}},
                        'programId': {'name': '',
                                      'address': '11111111111111111111111111111111'}}],
                'recentBlockhash': 'C6JMpqxtT8hyPbD4bcgmiGhY64ay2gzGQyr634e5BvFT',
                'signatures': [
                    '4hyCo6poqsgDhyRbdsDAGeB4U7ioP2x1etZW2og4eSKrwttUzXxpvsjJfxVf9bqptFyQkvDH6wis9VxMsrb8'],
                'meta': {'computeUnitsConsumed': 0, 'err': None, 'fee': 5000,
                         'loadedAddresses': {'readonly': [], 'writable': []},
                         'logMessages': ['Program 11111111111111111111111111111111 invoke [1]',
                                         'Program 11111111111111111111111111111111 success',
                                         'Program 11111111111111111111111111111111 invoke [1]',
                                         'Program 11111111111111111111111111111111 success'],
                         'postBalances': [3020842247260951, 20000000, 1107945797, 42706560, 1], 'postTokenBalances': [],
                         'preBalances': [3020843339265951, 20000000, 15945797, 42706560, 1], 'preTokenBalances': [],
                         'rewards': [], 'status': {'Ok': None}}, 'valid': True,
                'blocktime': {'absolute': 1698648046, 'relative': 1698648048},
                'mostImportantInstruction': {'name': 'AdvanceNonceAccount', 'weight': 0.5, 'index': 0},
                'smart': [{'type': 'address', 'value': {'address': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'}},
                          {'type': 'text', 'value': 'transferred'}, {'type': 'amount', 'value': 109200},
                          {'type': 'text', 'value': 'to'},
                          {'type': 'address', 'value': {'address': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN'}}]}
        ]
        expected_txs_details2 = [{'success': False}]
        cls.get_tx_details(tx_details_mock_responses2, expected_txs_details2)

        tx_details_mock_responses3 = [
            {
                "boundaries": {
                    "start": 208498472,
                    "end": 208598472
                },
                "window": 100000,
                "networkLag": 6,
                "currentSlot": 208598478
            },
            {
                'transactionHash':
                    'RfUKdN2A6M12VEfekEfTTcNoDbj8tamSi2Uk8sxpqr5kPxwuECeUoGgFUPDmUuLqAA7enhqF1hMKjypAoM6qG ',
                'blockNumber': 226579590, 'index': 46,
                'accounts': [
                    {'account': {'address': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'}, 'writable': True,
                     'signer': True},
                    {'account': {'address': 'E8gPR9iQyS67j2hFmAzjywbY7rBRmT5FVMoQd8KRn4dH'}, 'writable': True,
                     'signer': False},
                    {'account': {'address': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN'}, 'writable': True,
                     'signer': False},
                    {'account': {
                        'name': 'Sysvar: Recent Blockhashes',
                        'address': 'SysvarRecentB1ockHashes11111111111111111111'},
                        'writable': False, 'signer': False},
                    {'account': {'name': 'System Program', 'address': '11111111111111111111111111111111'},
                     'writable': False, 'signer': False, 'program': True}],
                'header': {'numRequiredSignatures': 1, 'numReadonlySignedAccounts': 0,
                           'numReadonlyUnsignedAccounts': 2},
                'instructions': [
                    {'parsed': {
                        'AdvanceNonceAccount':
                            {'nonceAccount': {'address': 'E8gPR9iQyS67j2hFmAzjywbY7rBRmT5FVMoQd8KRn4dH'},
                             'recentBlockhashesSysVar': {'name': 'Sysvar: Recent Blockhashes',
                                                         'address': 'SysvarRecentB1ockHashes11111111111111111111'},
                             'nonceAuthority': {
                                 'address': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'},
                             'signers': [{'address': 'E8gPR9iQyS67j2hFmAzjywbY7rBRmT5FVMoQd8KRn4dH'},
                                         {'address': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'}],
                             'writable': [{'address': 'E8gPR9iQyS67j2hFmAzjywbY7rBRmT5FVMoQd8KRn4dH'}]}},
                        'programId': {'name': 'System Program',
                                      'address': '11111111111111111111111111111111'}},
                    {'parsed': {
                        'Transfer': {'lamports': 89200,
                                     'account': {
                                         'address': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'},
                                     'recipient': {
                                         'address': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN'},
                                     'signers': [{
                                         'address': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'}],
                                     'writable': [{
                                         'address': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'},
                                         {
                                             'address': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN'}]}},
                        'programId': {'name': 'System Program',
                                      'address': '11111111111111111111111111111111'}}],
                'recentBlockhash': 'GKuZPX1EvVK4j4pmCovMJGBfLDWER86Pi8Bk7ZcvVK66',
                'signatures': [
                    'RfUKdN2A6M12VEfekEfTTcNoDbj8tamSi2Uk8sxpqr5kPxwuECeUoGgFUPDmUuLqAA7enhqF1hMKjypAoM6qG'],
                'meta': {'err': None, 'fee': 5000, 'status': {'Ok': None}, 'rewards': [],
                         'logMessages': ['Program 11111111111111111111111111111111 invoke [1]',
                                         'Program 11111111111111111111111111111111 success',
                                         'Program 11111111111111111111111111111111 invoke [1]',
                                         'Program 11111111111111111111111111111111 success'],
                         'preBalances': [4691377208369879, 20000000, 895788, 42706560, 1],
                         'postBalances': [4691376316364879, 20000000, 892895788, 42706560, 1],
                         'loadedAddresses': {'readonly': [], 'writable': []}, 'preTokenBalances': [],
                         'postTokenBalances': [], 'computeUnitsConsumed': 0}, 'valid': True,
                'blocktime': {'absolute': 1698526705, 'relative': 1698526707},
                'mostImportantInstruction': {'name': 'AdvanceNonceAccount', 'weight': 0.5, 'index': 0},
                'smart': [{'type': 'address', 'value': {'address': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'}},
                          {'type': 'text', 'value': 'transferred'}, {'type': 'amount', 'value': 89200},
                          {'type': 'text', 'value': 'to'},
                          {'type': 'address', 'value': {'address': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN'}}]}
        ]
        expected_txs_details3 = [{'success': False}]
        cls.get_tx_details(tx_details_mock_responses3, expected_txs_details3)

        tx_details_mock_responses4 = [
            {
                "boundaries": {
                    "start": 208498472,
                    "end": 208598472
                },
                "window": 100000,
                "networkLag": 6,
                "currentSlot": 208598478
            },
            {
                'transactionHash':
                    '3ZLtdKtcrKmL8DaBd8p7xb2fjpXnATmDXgEScR19dA6v1QKL8cDyY4sBP9q86NDgrmp9vkMRsvRk4wUGcfTuKL',
                'blockNumber': 226793177,
                'accounts': [
                    {'account': {'address': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'}, 'writable': True,
                     'signer': True},
                    {'account': {'address': 'uRz4VqbrLzQCN767YNKjTNqGyTfmRyDTe1GyCiyfrtW'}, 'writable': True,
                     'signer': False},
                    {'account': {'address': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN'}, 'writable': True,
                     'signer': False},
                    {'account': {'name': 'Sysvar: Recent Blockhashes',
                                 'address': 'SysvarRecentB1ockHashes11111111111111111111'},
                     'writable': False, 'signer': False},
                    {'account': {'name': 'System Program', 'address': '11111111111111111111111111111111'},
                     'writable': False, 'signer': False, 'program': True}],
                'header': {'numReadonlySignedAccounts': 0, 'numReadonlyUnsignedAccounts': 2,
                           'numRequiredSignatures': 1},
                'instructions': [{'parsed': {
                    'AdvanceNonceAccount':
                        {'nonceAccount': {'address': 'uRz4VqbrLzQCN767YNKjTNqGyTfmRyDTe1GyCiyfrtW'},
                         'recentBlockhashesSysVar': {'name': 'Sysvar: Recent Blockhashes',
                                                     'address': 'SysvarRecentB1ockHashes11111111111111111111'},
                         'nonceAuthority': {
                             'address': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'},
                         'signers': [{'address': 'uRz4VqbrLzQCN767YNKjTNqGyTfmRyDTe1GyCiyfrtW'},
                                     {'address': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'}],
                         'writable': [{'address': 'uRz4VqbrLzQCN767YNKjTNqGyTfmRyDTe1GyCiyfrtW'}]}},
                    'programId': {'name': 'System Program',
                                  'address': '11111111111111111111111111111111'}},
                    {'parsed': {
                        'Transfer':
                            {'lamports': 3762900,
                             'account': {
                                 'address': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN'},
                             'recipient': {
                                 'address': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN'},
                             'signers': [{
                                 'address': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN'}],
                             'writable': [{
                                 'address': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN'},
                                 {
                                     'address': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN'}]}},
                        'programId': {'name': 'System Program',
                                      'address': '11111111111111111111111111111111'}}],
                'recentBlockhash': 'AgSjFuAtrUsXJqLs2zaM5RMPDGBKCSfAYoXxgsRymeW3',
                'signatures': [
                    '3ZLtdKtcrKmL8DaBd8p7xb2fjpXnATmDXgEScR19dA6v1QKL8cDyY4sBP9q86NDgrmp9vkMRsvRk4wUGcfTuKL'],
                'meta': {'computeUnitsConsumed': 0, 'err': None, 'fee': 5000,
                         'loadedAddresses': {'readonly': [], 'writable': []},
                         'logMessages': ['Program 11111111111111111111111111111111 invoke [1]',
                                         'Program 11111111111111111111111111111111 success',
                                         'Program 11111111111111111111111111111111 invoke [1]',
                                         'Program 11111111111111111111111111111111 success'],
                         'postBalances': [4324728495947892, 21000000, 377185797, 42706560, 1], 'postTokenBalances': [],
                         'preBalances': [4324728872242892, 21000000, 895797, 42706560, 1], 'preTokenBalances': [],
                         'rewards': [], 'status': {'Ok': None}}, 'valid': True,
                'blocktime': {'absolute': 1698613905, 'relative': 1698613908},
                'mostImportantInstruction': {'name': 'AdvanceNonceAccount', 'weight': 0.5, 'index': 0},
                'smart': [{'type': 'address', 'value': {'address': '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'}},
                          {'type': 'text', 'value': 'transferred'}, {'type': 'amount', 'value': 376290000},
                          {'type': 'text', 'value': 'to'},
                          {'type': 'address', 'value': {'address': '7Lp6sJYnJL2p33oPshdfAx5FSvYDFYRpng2gHJDTEQeN'}}]}
        ]
        expected_txs_details4 = [{'success': False}]
        cls.get_tx_details(tx_details_mock_responses4, expected_txs_details4)

    @classmethod
    def test_get_address_txs(cls):
        APIS_CONF['SOL']['get_txs'] = 'sol_explorer_interface'
        address_txs_mock_responses = [
            {
                "boundaries": {
                    "start": 208498472,
                    "end": 208598472
                },
                "window": 100000,
                "networkLag": 6,
                "currentSlot": 208598478
            },
            [
                {
                    "transactionHash":
                        "52cRTeHPjmaw68qrg5gQNwkv1B4NVcxzPreqXDMy8W9ES1Q2taZCb7hi9CgQ9k6Kw6M54gh3KTT6iGWyDzxsTfXE",
                    "blockNumber": 202617637,
                    "accounts": [
                        {
                            "account": {
                                "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                            },
                            "writable": True,
                            "signer": True
                        },
                        {
                            "account": {
                                "address": "GJRs4FwHtemZ5ZE9x3FNvJ8TMwitKTh21yxdRPqn7npE"
                            },
                            "writable": True,
                            "signer": False
                        },
                        {
                            "account": {
                                "name": "System Program",
                                "address": "11111111111111111111111111111111"
                            },
                            "writable": False,
                            "signer": False,
                            "program": True
                        },
                        {
                            "account": {
                                "address": "ComputeBudget111111111111111111111111111111"
                            },
                            "writable": False,
                            "signer": False,
                            "program": True
                        }
                    ],
                    "header": {
                        "numReadonlySignedAccounts": 0,
                        "numReadonlyUnsignedAccounts": 2,
                        "numRequiredSignatures": 1
                    },
                    "instructions": [
                        {
                            "parsed": {
                                "TransferSol": {
                                    "amount": 22239981000,
                                    "source": {
                                        "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                                    },
                                    "destination": {
                                        "address": "GJRs4FwHtemZ5ZE9x3FNvJ8TMwitKTh21yxdRPqn7npE"
                                    },
                                    "signers": [
                                        {
                                            "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                                        }
                                    ],
                                    "writable": [
                                        {
                                            "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                                        },
                                        {
                                            "address": "GJRs4FwHtemZ5ZE9x3FNvJ8TMwitKTh21yxdRPqn7npE"
                                        }
                                    ]
                                }
                            },
                            "programId": {
                                "name": "System Program",
                                "address": "11111111111111111111111111111111"
                            }
                        },
                        {
                            "raw": {
                                "accounts": [],
                                "data": "031027000000000000",
                                "programIdIndex": 3
                            },
                            "programId": {
                                "address": "ComputeBudget111111111111111111111111111111"
                            }
                        }
                    ],
                    "recentBlockhash": "2oRmhh11TKAub7yeYt3TYnk6HzPKwcb3CEpwK9SYBZEz",
                    "signatures": [
                        "52cRTeHPjmaw68qrg5gQNwkv1B4NVcxzPreqXDMy8W9ES1Q2taZCb7hi9CgQ9k6Kw6M54gh3KTT6iGWyDzxsTfXE"
                    ],
                    "meta": {
                        "computeUnitsConsumed": 0,
                        "err": None,
                        "fee": 19000,
                        "loadedAddresses": {
                            "readonly": [],
                            "writable": []
                        },
                        "logMessages": [
                            "Program 11111111111111111111111111111111 invoke [1]",
                            "Program 11111111111111111111111111111111 success",
                            "Program ComputeBudget111111111111111111111111111111 invoke [1]",
                            "Program ComputeBudget111111111111111111111111111111 success"
                        ],
                        "postBalances": [
                            0,
                            59781921431691,
                            1,
                            1
                        ],
                        "postTokenBalances": [],
                        "preBalances": [
                            22240000000,
                            59759681450691,
                            1,
                            1
                        ],
                        "preTokenBalances": [],
                        "rewards": [],
                        "status": {
                            "Ok": None
                        }
                    },
                    "valid": True,
                    "blocktime": {
                        "absolute": 1688145039,
                        "relative": 1688145044
                    },
                    "mostImportantInstruction": {
                        "name": "Transfer",
                        "weight": 0.5,
                        "index": 0
                    }
                },
                {
                    "transactionHash":
                        "57rfrAKFTMyretUzDMy2TLY6UX7VNq2uzFgdpLufztgK75kCxZnhmoUbhqpoyeTeacT76Nak2HJjrVa9o2wZSVhV",
                    "blockNumber": 202617447,
                    "accounts": [
                        {
                            "account": {
                                "address": "7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj"
                            },
                            "writable": True,
                            "signer": True
                        },
                        {
                            "account": {
                                "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                            },
                            "writable": True,
                            "signer": False
                        },
                        {
                            "account": {
                                "name": "System Program",
                                "address": "11111111111111111111111111111111"
                            },
                            "writable": False,
                            "signer": False,
                            "program": True
                        }
                    ],
                    "header": {
                        "numReadonlySignedAccounts": 0,
                        "numReadonlyUnsignedAccounts": 1,
                        "numRequiredSignatures": 1
                    },
                    "instructions": [
                        {
                            "parsed": {
                                "TransferSol": {
                                    "amount": 22240000000,
                                    "source": {
                                        "address": "7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj"
                                    },
                                    "destination": {
                                        "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                                    },
                                    "signers": [
                                        {
                                            "address": "7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj"
                                        }
                                    ],
                                    "writable": [
                                        {
                                            "address": "7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj"
                                        },
                                        {
                                            "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                                        }
                                    ]
                                }
                            },
                            "programId": {
                                "name": "System Program",
                                "address": "11111111111111111111111111111111"
                            }
                        }
                    ],
                    "recentBlockhash": "3zg4nvFFSWJCMVUpF4iE5ExS4f95PD32XF9KRvKDLr3N",
                    "signatures": [
                        "57rfrAKFTMyretUzDMy2TLY6UX7VNq2uzFgdpLufztgK75kCxZnhmoUbhqpoyeTeacT76Nak2HJjrVa9o2wZSVhV"
                    ],
                    "meta": {
                        "computeUnitsConsumed": 0,
                        "err": None,
                        "fee": 5000,
                        "loadedAddresses": {
                            "readonly": [],
                            "writable": []
                        },
                        "logMessages": [
                            "Program 11111111111111111111111111111111 invoke [1]",
                            "Program 11111111111111111111111111111111 success"
                        ],
                        "postBalances": [
                            1982180308,
                            22240000000,
                            1
                        ],
                        "postTokenBalances": [],
                        "preBalances": [
                            24222185308,
                            0,
                            1
                        ],
                        "preTokenBalances": [],
                        "rewards": [],
                        "status": {
                            "Ok": None
                        }
                    },
                    "valid": True,
                    "blocktime": {
                        "absolute": 1688144949,
                        "relative": 1688144954
                    },
                    "mostImportantInstruction": {
                        "name": "Transfer",
                        "weight": 0.5,
                        "index": 0
                    }
                },
                {
                    "transactionHash":
                        "4esXjEgQqXyUAzjBK1AQF4joGwZn4k8hz2VKgdiXojeRd9yrpG2bzomeuULBHBaMQb23Xsx5jxYd14WhPmgWdXJX",
                    "blockNumber": 197329118,
                    "accounts": [
                        {
                            "account": {
                                "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                            },
                            "writable": True,
                            "signer": True
                        },
                        {
                            "account": {
                                "address": "GJRs4FwHtemZ5ZE9x3FNvJ8TMwitKTh21yxdRPqn7npE"
                            },
                            "writable": True,
                            "signer": False
                        },
                        {
                            "account": {
                                "name": "System Program",
                                "address": "11111111111111111111111111111111"
                            },
                            "writable": False,
                            "signer": False,
                            "program": True
                        },
                        {
                            "account": {
                                "address": "ComputeBudget111111111111111111111111111111"
                            },
                            "writable": False,
                            "signer": False,
                            "program": True
                        }
                    ],
                    "header": {
                        "numReadonlySignedAccounts": 0,
                        "numReadonlyUnsignedAccounts": 2,
                        "numRequiredSignatures": 1
                    },
                    "instructions": [
                        {
                            "parsed": {
                                "TransferSol": {
                                    "amount": 24459981000,
                                    "source": {
                                        "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                                    },
                                    "destination": {
                                        "address": "GJRs4FwHtemZ5ZE9x3FNvJ8TMwitKTh21yxdRPqn7npE"
                                    },
                                    "signers": [
                                        {
                                            "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                                        }
                                    ],
                                    "writable": [
                                        {
                                            "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                                        },
                                        {
                                            "address": "GJRs4FwHtemZ5ZE9x3FNvJ8TMwitKTh21yxdRPqn7npE"
                                        }
                                    ]
                                }
                            },
                            "programId": {
                                "name": "System Program",
                                "address": "11111111111111111111111111111111"
                            }
                        },
                        {
                            "raw": {
                                "accounts": [],
                                "data": "031027000000000000",
                                "programIdIndex": 3
                            },
                            "programId": {
                                "address": "ComputeBudget111111111111111111111111111111"
                            }
                        }
                    ],
                    "recentBlockhash": "9m57YhvBB9xsrXBXfVNvsoGUxRZenZ6kn2aCMme9Mggj",
                    "signatures": [
                        "4esXjEgQqXyUAzjBK1AQF4joGwZn4k8hz2VKgdiXojeRd9yrpG2bzomeuULBHBaMQb23Xsx5jxYd14WhPmgWdXJX"
                    ],
                    "meta": {
                        "err": None,
                        "fee": 19000,
                        "loadedAddresses": {
                            "readonly": [],
                            "writable": []
                        },
                        "logMessages": [
                            "Program 11111111111111111111111111111111 invoke [1]",
                            "Program 11111111111111111111111111111111 success",
                            "Program ComputeBudget111111111111111111111111111111 invoke [1]",
                            "Program ComputeBudget111111111111111111111111111111 success"
                        ],
                        "postBalances": [
                            0,
                            62544323134969,
                            1,
                            1
                        ],
                        "postTokenBalances": [],
                        "preBalances": [
                            24460000000,
                            62519863153969,
                            1,
                            1
                        ],
                        "preTokenBalances": [],
                        "rewards": [],
                        "status": {
                            "Ok": None
                        }
                    },
                    "valid": True,
                    "blocktime": {
                        "absolute": 1685696908,
                        "relative": 1685696913
                    },
                    "mostImportantInstruction": {
                        "name": "Transfer",
                        "weight": 0.5,
                        "index": 0
                    }
                },
                {
                    "transactionHash":
                        "38zTReQMhqZ2AweDbyma7gSii6UTskARBipLGbRTzt7A7KmGvwCTpNLNep7f1Mtjr2Mm6kLmd6kyZgQ2qqpioHtU",
                    "blockNumber": 197328826,
                    "accounts": [
                        {
                            "account": {
                                "address": "7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj"
                            },
                            "writable": True,
                            "signer": True
                        },
                        {
                            "account": {
                                "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                            },
                            "writable": True,
                            "signer": False
                        },
                        {
                            "account": {
                                "name": "System Program",
                                "address": "11111111111111111111111111111111"
                            },
                            "writable": False,
                            "signer": False,
                            "program": True
                        }
                    ],
                    "header": {
                        "numReadonlySignedAccounts": 0,
                        "numReadonlyUnsignedAccounts": 1,
                        "numRequiredSignatures": 1
                    },
                    "instructions": [
                        {
                            "parsed": {
                                "TransferSol": {
                                    "amount": 24460000000,
                                    "source": {
                                        "address": "7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj"
                                    },
                                    "destination": {
                                        "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                                    },
                                    "signers": [
                                        {
                                            "address": "7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj"
                                        }
                                    ],
                                    "writable": [
                                        {
                                            "address": "7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj"
                                        },
                                        {
                                            "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                                        }
                                    ]
                                }
                            },
                            "programId": {
                                "name": "System Program",
                                "address": "11111111111111111111111111111111"
                            }
                        }
                    ],
                    "recentBlockhash": "AnThLwmzGWryxVWv85fj1A4ZVVaF2mihisV3D1dwiYvs",
                    "signatures": [
                        "38zTReQMhqZ2AweDbyma7gSii6UTskARBipLGbRTzt7A7KmGvwCTpNLNep7f1Mtjr2Mm6kLmd6kyZgQ2qqpioHtU"
                    ],
                    "meta": {
                        "err": None,
                        "fee": 5000,
                        "loadedAddresses": {
                            "readonly": [],
                            "writable": []
                        },
                        "logMessages": [
                            "Program 11111111111111111111111111111111 invoke [1]",
                            "Program 11111111111111111111111111111111 success"
                        ],
                        "postBalances": [
                            771188399,
                            24460000000,
                            1
                        ],
                        "postTokenBalances": [],
                        "preBalances": [
                            25231193399,
                            0,
                            1
                        ],
                        "preTokenBalances": [],
                        "rewards": [],
                        "status": {
                            "Ok": None
                        }
                    },
                    "valid": True,
                    "blocktime": {
                        "absolute": 1685696771,
                        "relative": 1685696776
                    },
                    "mostImportantInstruction": {
                        "name": "Transfer",
                        "weight": 0.5,
                        "index": 0
                    }
                },
                {
                    "transactionHash":
                        "2pGPCZzauHVkC1uNgACGBorr4D293FPsJh7YisdynX39UthoNxSGwm5ywuSe3dKBf3uFjqEGRRsBbk3yjaFHmKjX",
                    "blockNumber": 191381138,
                    "accounts": [
                        {
                            "account": {
                                "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                            },
                            "writable": True,
                            "signer": True
                        },
                        {
                            "account": {
                                "address": "H8sMJSCQxfKiFTCfDR3DUMLPwcRbM61LGFJ8N4dK3WjS"
                            },
                            "writable": True,
                            "signer": False
                        },
                        {
                            "account": {
                                "name": "System Program",
                                "address": "11111111111111111111111111111111"
                            },
                            "writable": False,
                            "signer": False,
                            "program": True
                        },
                        {
                            "account": {
                                "address": "ComputeBudget111111111111111111111111111111"
                            },
                            "writable": False,
                            "signer": False,
                            "program": True
                        }
                    ],
                    "header": {
                        "numReadonlySignedAccounts": 0,
                        "numReadonlyUnsignedAccounts": 2,
                        "numRequiredSignatures": 1
                    },
                    "instructions": [
                        {
                            "parsed": {
                                "TransferSol": {
                                    "amount": 30019981000,
                                    "source": {
                                        "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                                    },
                                    "destination": {
                                        "address": "H8sMJSCQxfKiFTCfDR3DUMLPwcRbM61LGFJ8N4dK3WjS"
                                    },
                                    "signers": [
                                        {
                                            "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                                        }
                                    ],
                                    "writable": [
                                        {
                                            "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                                        },
                                        {
                                            "address": "H8sMJSCQxfKiFTCfDR3DUMLPwcRbM61LGFJ8N4dK3WjS"
                                        }
                                    ]
                                }
                            },
                            "programId": {
                                "name": "System Program",
                                "address": "11111111111111111111111111111111"
                            }
                        },
                        {
                            "raw": {
                                "accounts": [],
                                "data": "031027000000000000",
                                "programIdIndex": 3
                            },
                            "programId": {
                                "address": "ComputeBudget111111111111111111111111111111"
                            }
                        }
                    ],
                    "recentBlockhash": "BnEqYgvzm3oHWx4tWzr1XFRPNvoetJwFUbMdLSr32dMd",
                    "signatures": [
                        "2pGPCZzauHVkC1uNgACGBorr4D293FPsJh7YisdynX39UthoNxSGwm5ywuSe3dKBf3uFjqEGRRsBbk3yjaFHmKjX"
                    ],
                    "meta": {
                        "err": None,
                        "fee": 19000,
                        "loadedAddresses": {
                            "readonly": [],
                            "writable": []
                        },
                        "logMessages": [
                            "Program 11111111111111111111111111111111 invoke [1]",
                            "Program 11111111111111111111111111111111 success",
                            "Program ComputeBudget111111111111111111111111111111 invoke [1]",
                            "Program ComputeBudget111111111111111111111111111111 success"
                        ],
                        "postBalances": [
                            0,
                            58897225044638,
                            1,
                            1
                        ],
                        "postTokenBalances": [],
                        "preBalances": [
                            30020000000,
                            58867205063638,
                            1,
                            1
                        ],
                        "preTokenBalances": [],
                        "rewards": [],
                        "status": {
                            "Ok": None
                        }
                    },
                    "valid": True,
                    "blocktime": {
                        "absolute": 1682879612,
                        "relative": 1682879617
                    },
                    "mostImportantInstruction": {
                        "name": "Transfer",
                        "weight": 0.5,
                        "index": 0
                    }
                },
                {
                    "transactionHash":
                        "5vq4g1AEaNhDSrx7KYgMjH8ZDcxtfq8pS4J1x5oUc8rwvA2CwjW5eC97pGdBFXGqZSKB9R19t8XJku8SMR1ap935",
                    "blockNumber": 191380789,
                    "accounts": [
                        {
                            "account": {
                                "address": "7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj"
                            },
                            "writable": True,
                            "signer": True
                        },
                        {
                            "account": {
                                "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                            },
                            "writable": True,
                            "signer": False
                        },
                        {
                            "account": {
                                "name": "System Program",
                                "address": "11111111111111111111111111111111"
                            },
                            "writable": False,
                            "signer": False,
                            "program": True
                        }
                    ],
                    "header": {
                        "numReadonlySignedAccounts": 0,
                        "numReadonlyUnsignedAccounts": 1,
                        "numRequiredSignatures": 1
                    },
                    "instructions": [
                        {
                            "parsed": {
                                "TransferSol": {
                                    "amount": 30020000000,
                                    "source": {
                                        "address": "7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj"
                                    },
                                    "destination": {
                                        "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                                    },
                                    "signers": [
                                        {
                                            "address": "7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj"
                                        }
                                    ],
                                    "writable": [
                                        {
                                            "address": "7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj"
                                        },
                                        {
                                            "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                                        }
                                    ]
                                }
                            },
                            "programId": {
                                "name": "System Program",
                                "address": "11111111111111111111111111111111"
                            }
                        }
                    ],
                    "recentBlockhash": "A9nZY9tW84tAbySyaNfWrZUicWWLYjjf6GHBVWQXyubw",
                    "signatures": [
                        "5vq4g1AEaNhDSrx7KYgMjH8ZDcxtfq8pS4J1x5oUc8rwvA2CwjW5eC97pGdBFXGqZSKB9R19t8XJku8SMR1ap935"
                    ],
                    "meta": {
                        "err": None,
                        "fee": 5000,
                        "loadedAddresses": {
                            "readonly": [],
                            "writable": []
                        },
                        "logMessages": [
                            "Program 11111111111111111111111111111111 invoke [1]",
                            "Program 11111111111111111111111111111111 success"
                        ],
                        "postBalances": [
                            1997387777,
                            30020000000,
                            1
                        ],
                        "postTokenBalances": [],
                        "preBalances": [
                            32017392777,
                            0,
                            1
                        ],
                        "preTokenBalances": [],
                        "rewards": [],
                        "status": {
                            "Ok": None
                        }
                    },
                    "valid": True,
                    "blocktime": {
                        "absolute": 1682879449,
                        "relative": 1682879454
                    },
                    "mostImportantInstruction": {
                        "name": "Transfer",
                        "weight": 0.5,
                        "index": 0
                    }
                },
                {
                    "transactionHash":
                        "5mJiwcADUfKW5LJMZxqAMQsS6ETRx6tr9BnPPqZe1cyRdPrLsRaaFmUHVuj6okcbxVwhvbE5gnxuaLiLrx2m3p34",
                    "blockNumber": 185371136,
                    "accounts": [
                        {
                            "account": {
                                "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                            },
                            "writable": True,
                            "signer": True
                        },
                        {
                            "account": {
                                "address": "2AQdpHJ2JpcEgPiATUXjQxA8QmafFegfQwSLWSprPicm"
                            },
                            "writable": True,
                            "signer": False
                        },
                        {
                            "account": {
                                "name": "System Program",
                                "address": "11111111111111111111111111111111"
                            },
                            "writable": False,
                            "signer": False,
                            "program": True
                        },
                        {
                            "account": {
                                "address": "ComputeBudget111111111111111111111111111111"
                            },
                            "writable": False,
                            "signer": False,
                            "program": True
                        }
                    ],
                    "header": {
                        "numReadonlySignedAccounts": 0,
                        "numReadonlyUnsignedAccounts": 2,
                        "numRequiredSignatures": 1
                    },
                    "instructions": [
                        {
                            "parsed": {
                                "TransferSol": {
                                    "amount": 51539981000,
                                    "source": {
                                        "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                                    },
                                    "destination": {
                                        "address": "2AQdpHJ2JpcEgPiATUXjQxA8QmafFegfQwSLWSprPicm"
                                    },
                                    "signers": [
                                        {
                                            "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                                        }
                                    ],
                                    "writable": [
                                        {
                                            "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                                        },
                                        {
                                            "address": "2AQdpHJ2JpcEgPiATUXjQxA8QmafFegfQwSLWSprPicm"
                                        }
                                    ]
                                }
                            },
                            "programId": {
                                "name": "System Program",
                                "address": "11111111111111111111111111111111"
                            }
                        },
                        {
                            "raw": {
                                "accounts": [],
                                "data": "031027000000000000",
                                "programIdIndex": 3
                            },
                            "programId": {
                                "address": "ComputeBudget111111111111111111111111111111"
                            }
                        }
                    ],
                    "recentBlockhash": "3WYvELZWDgaZHpgHe3hY48MhvzzCqjoXq1KMtJbXSX1h",
                    "signatures": [
                        "5mJiwcADUfKW5LJMZxqAMQsS6ETRx6tr9BnPPqZe1cyRdPrLsRaaFmUHVuj6okcbxVwhvbE5gnxuaLiLrx2m3p34"
                    ],
                    "meta": {
                        "err": None,
                        "fee": 19000,
                        "loadedAddresses": {
                            "readonly": [],
                            "writable": []
                        },
                        "logMessages": [
                            "Program 11111111111111111111111111111111 invoke [1]",
                            "Program 11111111111111111111111111111111 success",
                            "Program ComputeBudget111111111111111111111111111111 invoke [1]",
                            "Program ComputeBudget111111111111111111111111111111 success"
                        ],
                        "postBalances": [
                            0,
                            635464938580121,
                            1,
                            1
                        ],
                        "postTokenBalances": [],
                        "preBalances": [
                            51540000000,
                            635413398599121,
                            1,
                            1
                        ],
                        "preTokenBalances": [],
                        "rewards": [],
                        "status": {
                            "Ok": None
                        }
                    },
                    "valid": True,
                    "blocktime": {
                        "absolute": 1680100296,
                        "relative": 1680100301
                    },
                    "mostImportantInstruction": {
                        "name": "Transfer",
                        "weight": 0.5,
                        "index": 0
                    }
                },
                {
                    "transactionHash":
                        "52nEjPd9uKEHuBh6uWiUkNLSYeikKZH37zSYpbwc6s8QE4mwXUwVewV8H9j1iKNugPoBePnjehhJ8j195ZXWcuCs",
                    "blockNumber": 185370791,
                    "accounts": [
                        {
                            "account": {
                                "address": "7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj"
                            },
                            "writable": True,
                            "signer": True
                        },
                        {
                            "account": {
                                "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                            },
                            "writable": True,
                            "signer": False
                        },
                        {
                            "account": {
                                "name": "System Program",
                                "address": "11111111111111111111111111111111"
                            },
                            "writable": False,
                            "signer": False,
                            "program": True
                        }
                    ],
                    "header": {
                        "numReadonlySignedAccounts": 0,
                        "numReadonlyUnsignedAccounts": 1,
                        "numRequiredSignatures": 1
                    },
                    "instructions": [
                        {
                            "parsed": {
                                "TransferSol": {
                                    "amount": 51540000000,
                                    "source": {
                                        "address": "7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj"
                                    },
                                    "destination": {
                                        "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                                    },
                                    "signers": [
                                        {
                                            "address": "7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj"
                                        }
                                    ],
                                    "writable": [
                                        {
                                            "address": "7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj"
                                        },
                                        {
                                            "address": "ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt"
                                        }
                                    ]
                                }
                            },
                            "programId": {
                                "name": "System Program",
                                "address": "11111111111111111111111111111111"
                            }
                        }
                    ],
                    "recentBlockhash": "FQfdRnQrBhu4qPhWXMaG9bP5iDF15fJEnFu9UXUGuzZv",
                    "signatures": [
                        "52nEjPd9uKEHuBh6uWiUkNLSYeikKZH37zSYpbwc6s8QE4mwXUwVewV8H9j1iKNugPoBePnjehhJ8j195ZXWcuCs"
                    ],
                    "meta": {
                        "err": None,
                        "fee": 5000,
                        "loadedAddresses": {
                            "readonly": [],
                            "writable": []
                        },
                        "logMessages": [
                            "Program 11111111111111111111111111111111 invoke [1]",
                            "Program 11111111111111111111111111111111 success"
                        ],
                        "postBalances": [
                            1950753003,
                            51540000000,
                            1
                        ],
                        "postTokenBalances": [],
                        "preBalances": [
                            53490758003,
                            0,
                            1
                        ],
                        "preTokenBalances": [],
                        "rewards": [],
                        "status": {
                            "Ok": None
                        }
                    },
                    "valid": True,
                    "blocktime": {
                        "absolute": 1680100135,
                        "relative": 1680100140
                    },
                    "mostImportantInstruction": {
                        "name": "Transfer",
                        "weight": 0.5,
                        "index": 0
                    }
                }
            ]
        ]
        expected_addresses_txs = [
            [
                {
                    'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                    'block': 202617637,
                    'confirmations': 5980841,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt'],
                    'hash': '52cRTeHPjmaw68qrg5gQNwkv1B4NVcxzPreqXDMy8W9ES1Q2taZCb7hi9CgQ9k6Kw6M54gh3KTT6iGWyDzxsTfXE',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 6, 30, 17, 10, 39, tzinfo=datetime.timezone.utc),
                    'value': Decimal('-22.239981000')
                },
                {
                    'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                    'block': 202617447,
                    'confirmations': 5981031,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj'],
                    'hash': '57rfrAKFTMyretUzDMy2TLY6UX7VNq2uzFgdpLufztgK75kCxZnhmoUbhqpoyeTeacT76Nak2HJjrVa9o2wZSVhV',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 6, 30, 17, 9, 9, tzinfo=datetime.timezone.utc),
                    'value': Decimal('22.240000000')
                },
                {
                    'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                    'block': 197329118,
                    'confirmations': 11269360,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt'],
                    'hash': '4esXjEgQqXyUAzjBK1AQF4joGwZn4k8hz2VKgdiXojeRd9yrpG2bzomeuULBHBaMQb23Xsx5jxYd14WhPmgWdXJX',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 6, 2, 9, 8, 28, tzinfo=datetime.timezone.utc),
                    'value': Decimal('-24.459981000')
                },
                {
                    'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                    'block': 197328826,
                    'confirmations': 11269652,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj'],
                    'hash': '38zTReQMhqZ2AweDbyma7gSii6UTskARBipLGbRTzt7A7KmGvwCTpNLNep7f1Mtjr2Mm6kLmd6kyZgQ2qqpioHtU',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 6, 2, 9, 6, 11, tzinfo=datetime.timezone.utc),
                    'value': Decimal('24.460000000')
                },
                {
                    'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                    'block': 191381138,
                    'confirmations': 17217340,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt'],
                    'hash': '2pGPCZzauHVkC1uNgACGBorr4D293FPsJh7YisdynX39UthoNxSGwm5ywuSe3dKBf3uFjqEGRRsBbk3yjaFHmKjX',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 4, 30, 18, 33, 32, tzinfo=datetime.timezone.utc),
                    'value': Decimal('-30.019981000')
                },
                {
                    'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                    'block': 191380789,
                    'confirmations': 17217689,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj'],
                    'hash': '5vq4g1AEaNhDSrx7KYgMjH8ZDcxtfq8pS4J1x5oUc8rwvA2CwjW5eC97pGdBFXGqZSKB9R19t8XJku8SMR1ap935',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 4, 30, 18, 30, 49, tzinfo=datetime.timezone.utc),
                    'value': Decimal('30.020000000')
                },
                {
                    'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                    'block': 185371136,
                    'confirmations': 23227342,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt'],
                    'hash': '5mJiwcADUfKW5LJMZxqAMQsS6ETRx6tr9BnPPqZe1cyRdPrLsRaaFmUHVuj6okcbxVwhvbE5gnxuaLiLrx2m3p34',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 3, 29, 14, 31, 36, tzinfo=datetime.timezone.utc),
                    'value': Decimal('-51.539981000')
                },
                {
                    'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                    'block': 185370791,
                    'confirmations': 23227687,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj'],
                    'hash': '52nEjPd9uKEHuBh6uWiUkNLSYeikKZH37zSYpbwc6s8QE4mwXUwVewV8H9j1iKNugPoBePnjehhJ8j195ZXWcuCs',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 3, 29, 14, 28, 55, tzinfo=datetime.timezone.utc),
                    'value': Decimal('51.540000000')
                },
            ]
        ]
        cls.get_address_txs(address_txs_mock_responses, expected_addresses_txs)
