import pytest
import datetime
from decimal import Decimal
from unittest import TestCase
from exchange.base.models import Currencies
from exchange.blockchain.api.sol.sol_explorer_interface import SolExplorerInterface
from exchange.blockchain.api.sol.solscan_sol import SolScanSolApi
from exchange.blockchain.apis_conf import APIS_CONF
from exchange.blockchain.tests.api.general_test.general_test_from_explorer import TestFromExplorer


class TestSolScanSolApiCalls(TestCase):
    api = SolScanSolApi
    addresses = ['6h7Ce5MfeuUP4gqMfQkM9GanBrZDvBcuxK6RX8qLSWAP']
    txs_hash = ['57rfrAKFTMyretUzDMy2TLY6UX7VNq2uzFgdpLufztgK75kCxZnhmoUbhqpoyeTeacT76Nak2HJjrVa9o2wZSVhV']

    @pytest.mark.slow
    def test_get_balance_api(self):
        for address in self.addresses:
            get_balance_result = self.api.get_balance(address)
            assert isinstance(get_balance_result, dict)
            assert {'lamports', 'account'}.issubset(set(get_balance_result.keys()))
            assert isinstance(get_balance_result.get('lamports'), int)
            assert isinstance(get_balance_result.get('account'), str)

    @pytest.mark.slow
    def test_get_block_head_api(self):
        get_block_head_response = self.api.get_block_head()
        assert isinstance(get_block_head_response, dict)
        assert {'absoluteSlot'}.issubset(set(get_block_head_response.keys()))
        assert isinstance(get_block_head_response.get('absoluteSlot'), int)

    @pytest.mark.slow
    def test_get_tx_details_api(self):
        for tx_hash in self.txs_hash:
            get_details_tx_response = self.api.get_tx_details(tx_hash)
            assert isinstance(get_details_tx_response, dict)
            assert ({'blockTime', 'slot', 'txHash', 'solTransfers', 'status'}
                    .issubset(set(get_details_tx_response.keys())))
            keys2check = [('txHash', str), ('blockTime', int), ('solTransfers', list), ('slot', int), ('status', str)]
            for key, value in keys2check:
                assert isinstance(get_details_tx_response.get(key), value)
            for transfer in get_details_tx_response.get('solTransfers'):
                assert isinstance(transfer.get('source'), str)
                assert isinstance(transfer.get('destination'), str)
                assert isinstance(transfer.get('amount'), int)

    @pytest.mark.slow
    def test_get_address_txs_api(self):
        for address in self.addresses:
            get_address_txs_response = self.api.get_address_txs(address)
            assert isinstance(get_address_txs_response, dict)
            assert {'data'}.issubset(set(get_address_txs_response))
            for transfer in get_address_txs_response.get('data'):
                assert ({'blockTime', 'slot', 'txHash', 'status', 'lamport', 'src', 'dst'}
                        .issubset(set(transfer.keys())))
                keys2check = [('txHash', str), ('blockTime', int), ('slot', int), ('status', str), ('lamport', int),
                              ('src', str), ('dst', str)]
                for key, value in keys2check:
                    assert isinstance(transfer.get(key), value)


class TestSolscanSolApiFromExplorer(TestFromExplorer):
    api = SolScanSolApi
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
                'account': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                'executable': False,
                'lamports': 48964194273,
                'ownerProgram': '11111111111111111111111111111111',
                'rentEpoch': 0,
                'type': 'system_account'
            }
        ]
        expected_balances = [
            {
                'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                'balance': Decimal('48.964194273'),
                'received': Decimal('48.964194273'),
                'sent': Decimal('0'),
                'rewarded': Decimal('0')
            }
        ]
        APIS_CONF['SOL']['get_balances'] = 'sol_explorer_interface'
        cls.get_balance(balance_mock_responses, expected_balances)

    @classmethod
    @pytest.mark.django_db
    def test_get_tx_details(cls):
        tx_details_mock_responses = [
            {
                'absoluteSlot': 208615916,
                'blockHeight': 191093680,
                'currentEpoch': 482,
                'transactionCount': 203914191552
            },
            {
                'blockTime': 1688144949,
                'slot': 202617447,
                'txHash': '57rfrAKFTMyretUzDMy2TLY6UX7VNq2uzFgdpLufztgK75kCxZnhmoUbhqpoyeTeacT76Nak2HJjrVa9o2wZSVhV',
                'fee': 5000,
                'status': 'Success',
                'lamport': 0,
                'signer': ['7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj'],
                'logMessage': [
                    'Program 11111111111111111111111111111111 invoke [1]',
                    'Program 11111111111111111111111111111111 success'],
                'inputAccount': [
                    {'account': '7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj',
                     'signer': True,
                     'writable': True,
                     'preBalance': 24222185308,
                     'postBalance': 1982180308},
                    {'account': 'Fi5Lw5opNWcs4iSMxEUBaXS9wzy9Td9k2VoBfpNwzZoD',
                     'signer': False,
                     'writable': True,
                     'preBalance': 0,
                     'postBalance': 22240000000},
                    {'account': '11111111111111111111111111111111',
                     'signer': False,
                     'writable': False,
                     'preBalance': 1,
                     'postBalance': 1}],
                'recentBlockhash': '3zg4nvFFSWJCMVUpF4iE5ExS4f95PD32XF9KRvKDLr3N',
                'innerInstructions': [],
                'tokenBalanes': [],
                'parsedInstruction': [
                    {'programId': '11111111111111111111111111111111',
                     'program': 'system',
                     'type': 'sol-transfer',
                     'data': '0200000000789b2d05000000',
                     'dataEncode': '3Bxs3zwELQqghtuV',
                     'name': 'SOL Transfer',
                     'params': {'source': '7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj',
                                'destination': 'Fi5Lw5opNWcs4iSMxEUBaXS9wzy9Td9k2VoBfpNwzZoD',
                                'amount': 22240000000}}
                ],
                'confirmations': None,
                'version': 'legacy',
                'tokenTransfers': [],
                'solTransfers': [
                    {'source': '7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj',
                     'destination': 'Fi5Lw5opNWcs4iSMxEUBaXS9wzy9Td9k2VoBfpNwzZoD',
                     'amount': 22240000000}],
                'serumTransactions': [],
                'raydiumTransactions': [],
                'unknownTransfers': []
            }
        ]
        expected_txs_details = [
            {
                'success': True,
                'block': 202617447,
                'date': datetime.datetime(2023, 6, 30, 20, 39, 9,
                                          tzinfo=datetime.timezone.utc),
                'raw': None,
                'inputs': [],
                'outputs': [],
                'transfers': [
                    {
                        'type': 'MainCoin',
                        'symbol': 'SOL',
                        'currency': 37,
                        'to': 'Fi5Lw5opNWcs4iSMxEUBaXS9wzy9Td9k2VoBfpNwzZoD',
                        'value': Decimal('22.240000000'),
                        'is_valid': True,
                        'token': None,
                        'memo': None,
                        'from': '7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj'
                    }
                ],
                'fees': None,
                'memo': None,
                'confirmations': 5998469,
                'hash': '57rfrAKFTMyretUzDMy2TLY6UX7VNq2uzFgdpLufztgK75kCxZnhmoUbhqpoyeTeacT76Nak2HJjrVa9o2wZSVhV'
            }
        ]
        APIS_CONF['SOL']['txs_details'] = 'sol_explorer_interface'
        cls.get_tx_details(tx_details_mock_responses, expected_txs_details)

        tx_details_mock_responses = [
            {
                'absoluteSlot': 208615916,
                'blockHeight': 191093680,
                'currentEpoch': 482,
                'transactionCount': 203914191552
            },
            {
                'blockTime': 1688144949,
                'slot': 202617447,
                'txHash': '57rfrAKFTMyretUzDMy2TLY6UX7VNq2uzFgdpLufztgK75kCxZnhmoUbhqpoyeTeacT76Nak2HJjrVa9o2wZSVhV',
                'fee': 5000,
                'status': 'backtracked',
                'lamport': 0,
                'signer': ['7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj'],
                'logMessage': [
                    'Program 11111111111111111111111111111111 invoke [1]',
                    'Program 11111111111111111111111111111111 success'],
                'inputAccount': [
                    {'account': '7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj',
                     'signer': True,
                     'writable': True,
                     'preBalance': 24222185308,
                     'postBalance': 1982180308},
                    {'account': 'Fi5Lw5opNWcs4iSMxEUBaXS9wzy9Td9k2VoBfpNwzZoD',
                     'signer': False,
                     'writable': True,
                     'preBalance': 0,
                     'postBalance': 22240000000},
                    {'account': '11111111111111111111111111111111',
                     'signer': False,
                     'writable': False,
                     'preBalance': 1,
                     'postBalance': 1}],
                'recentBlockhash': '3zg4nvFFSWJCMVUpF4iE5ExS4f95PD32XF9KRvKDLr3N',
                'innerInstructions': [],
                'tokenBalanes': [],
                'parsedInstruction': [
                    {'programId': '11111111111111111111111111111111',
                     'program': 'system',
                     'type': 'sol-transfer',
                     'data': '0200000000789b2d05000000',
                     'dataEncode': '3Bxs3zwELQqghtuV',
                     'name': 'SOL Transfer',
                     'params': {'source': '7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj',
                                'destination': 'Fi5Lw5opNWcs4iSMxEUBaXS9wzy9Td9k2VoBfpNwzZoD',
                                'amount': 22240000000}}
                ],
                'confirmations': None,
                'version': 'legacy',
                'tokenTransfers': [],
                'solTransfers': [
                    {'source': '7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj',
                     'destination': 'Fi5Lw5opNWcs4iSMxEUBaXS9wzy9Td9k2VoBfpNwzZoD',
                     'amount': 22240000000}],
                'serumTransactions': [],
                'raydiumTransactions': [],
                'unknownTransfers': []
            }
        ]
        expected_txs_details = [{'success': False}]
        cls.get_tx_details(tx_details_mock_responses, expected_txs_details)

    @classmethod
    def test_get_address_txs(cls):
        APIS_CONF['SOL']['get_txs'] = 'sol_explorer_interface'
        address_txs_mock_responses = [
            {
                'absoluteSlot': 208615916,
                'blockHeight': 191093680,
                'currentEpoch': 482,
                'transactionCount': 203914191552
            },
            {
                'data': [
                    {'_id': '649f0cacf95fd6653f6d6b12',
                     'src': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                     'dst': 'GJRs4FwHtemZ5ZE9x3FNvJ8TMwitKTh21yxdRPqn7npE',
                     'lamport': 22239981000,
                     'blockTime': 1688145039,
                     'slot': 202617637,
                     'txHash':
                         '52cRTeHPjmaw68qrg5gQNwkv1B4NVcxzPreqXDMy8W9ES1Q2taZCb7hi9CgQ9k6Kw6M54gh3KTT6iGWyDzxsTfXE',
                     'fee': 19000,
                     'status': 'Success',
                     'decimals': 9,
                     'isInner': False,
                     'txNumberSolTransfer': 1},
                    {'_id': '649f0c46f95fd6653f6d5005',
                     'src': '7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj',
                     'dst': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                     'lamport': 22240000000,
                     'blockTime': 1688144949,
                     'slot': 202617447,
                     'txHash':
                         '57rfrAKFTMyretUzDMy2TLY6UX7VNq2uzFgdpLufztgK75kCxZnhmoUbhqpoyeTeacT76Nak2HJjrVa9o2wZSVhV',
                     'fee': 5000,
                     'status': 'Success',
                     'decimals': 9,
                     'isInner': False,
                     'txNumberSolTransfer': 1},
                    {'_id': '6479b19ec3fb8c15cb661114',
                     'src': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                     'dst': 'GJRs4FwHtemZ5ZE9x3FNvJ8TMwitKTh21yxdRPqn7npE',
                     'lamport': 24459981000,
                     'blockTime': 1685696908,
                     'slot': 197329118,
                     'txHash':
                         '4esXjEgQqXyUAzjBK1AQF4joGwZn4k8hz2VKgdiXojeRd9yrpG2bzomeuULBHBaMQb23Xsx5jxYd14WhPmgWdXJX',
                     'fee': 19000,
                     'status': 'Success',
                     'decimals': 9, 'isInner': False,
                     'txNumberSolTransfer': 1},
                    {'_id': '6479b119c3fb8c15cb65fa09',
                     'src': '7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj',
                     'dst': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                     'lamport': 24460000000,
                     'blockTime': 1685696771,
                     'slot': 197328826,
                     'txHash':
                         '38zTReQMhqZ2AweDbyma7gSii6UTskARBipLGbRTzt7A7KmGvwCTpNLNep7f1Mtjr2Mm6kLmd6kyZgQ2qqpioHtU',
                     'fee': 5000,
                     'status': 'Success',
                     'decimals': 9,
                     'isInner': False,
                     'txNumberSolTransfer': 1},
                    {'_id': '644eb49eb287b20c740da5fb',
                     'src': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                     'dst': 'H8sMJSCQxfKiFTCfDR3DUMLPwcRbM61LGFJ8N4dK3WjS',
                     'lamport': 30019981000,
                     'blockTime': 1682879612,
                     'slot': 191381138,
                     'txHash':
                         '2pGPCZzauHVkC1uNgACGBorr4D293FPsJh7YisdynX39UthoNxSGwm5ywuSe3dKBf3uFjqEGRRsBbk3yjaFHmKjX',
                     'fee': 19000,
                     'status': 'Success',
                     'decimals': 9,
                     'isInner': False,
                     'txNumberSolTransfer': 1},
                    {'_id': '644eb3f3b287b20c740d8ff4',
                     'src': '7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj',
                     'dst': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                     'lamport': 30020000000,
                     'blockTime': 1682879449,
                     'slot': 191380789,
                     'txHash':
                         '5vq4g1AEaNhDSrx7KYgMjH8ZDcxtfq8pS4J1x5oUc8rwvA2CwjW5eC97pGdBFXGqZSKB9R19t8XJku8SMR1ap935',
                     'fee': 5000,
                     'status': 'Success',
                     'decimals': 9,
                     'isInner': False,
                     'txNumberSolTransfer': 1},
                    {'_id': '64244bdc90495502bc3ef766',
                     'src': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                     'dst': '2AQdpHJ2JpcEgPiATUXjQxA8QmafFegfQwSLWSprPicm',
                     'lamport': 51539981000,
                     'blockTime': 1680100296,
                     'slot': 185371136,
                     'txHash':
                         '5mJiwcADUfKW5LJMZxqAMQsS6ETRx6tr9BnPPqZe1cyRdPrLsRaaFmUHVuj6okcbxVwhvbE5gnxuaLiLrx2m3p34',
                     'fee': 19000,
                     'status': 'Success',
                     'decimals': 9,
                     'isInner': False,
                     'txNumberSolTransfer': 1},
                    {'_id': '64244b3b90495502bc3ee414',
                     'src': '7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj',
                     'dst': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                     'lamport': 51540000000,
                     'blockTime': 1680100135,
                     'slot': 185370791,
                     'txHash': '52nEjPd9uKEHuBh6uWiUkNLSYeikKZH37zSYpbwc6s8QE4mwXUwVewV8H9j1iKNugPoBePnjehhJ8j195ZXWcuCs',
                     'fee': 5000,
                     'status': 'Success',
                     'decimals': 9,
                     'isInner': False,
                     'txNumberSolTransfer': 1},
                ]
            },
        ]
        expected_addresses_txs = [
            [
                {
                    'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                    'block': 202617637,
                    'confirmations': 5998279,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt'],
                    'hash': '52cRTeHPjmaw68qrg5gQNwkv1B4NVcxzPreqXDMy8W9ES1Q2taZCb7hi9CgQ9k6Kw6M54gh3KTT6iGWyDzxsTfXE',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 6, 30, 20, 40, 39, tzinfo=datetime.timezone.utc),
                    'value': Decimal('-22.239981000')
                },
                {
                    'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                    'block': 202617447,
                    'confirmations': 5998469,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj'],
                    'hash': '57rfrAKFTMyretUzDMy2TLY6UX7VNq2uzFgdpLufztgK75kCxZnhmoUbhqpoyeTeacT76Nak2HJjrVa9o2wZSVhV',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 6, 30, 20, 39, 9, tzinfo=datetime.timezone.utc),
                    'value': Decimal('22.240000000')
                },
                {
                    'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                    'block': 197329118,
                    'confirmations': 11286798,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt'],
                    'hash': '4esXjEgQqXyUAzjBK1AQF4joGwZn4k8hz2VKgdiXojeRd9yrpG2bzomeuULBHBaMQb23Xsx5jxYd14WhPmgWdXJX',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 6, 2, 12, 38, 28, tzinfo=datetime.timezone.utc),
                    'value': Decimal('-24.459981000')
                },
                {
                    'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                    'block': 197328826,
                    'confirmations': 11287090,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj'],
                    'hash': '38zTReQMhqZ2AweDbyma7gSii6UTskARBipLGbRTzt7A7KmGvwCTpNLNep7f1Mtjr2Mm6kLmd6kyZgQ2qqpioHtU',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 6, 2, 12, 36, 11, tzinfo=datetime.timezone.utc),
                    'value': Decimal('24.460000000')
                },
                {
                    'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                    'block': 191381138,
                    'confirmations': 17234778,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt'],
                    'hash': '2pGPCZzauHVkC1uNgACGBorr4D293FPsJh7YisdynX39UthoNxSGwm5ywuSe3dKBf3uFjqEGRRsBbk3yjaFHmKjX',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 4, 30, 22, 3, 32, tzinfo=datetime.timezone.utc),
                    'value': Decimal('-30.019981000')
                },
                {
                    'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                    'block': 191380789,
                    'confirmations': 17235127,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj'],
                    'hash': '5vq4g1AEaNhDSrx7KYgMjH8ZDcxtfq8pS4J1x5oUc8rwvA2CwjW5eC97pGdBFXGqZSKB9R19t8XJku8SMR1ap935',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 4, 30, 22, 0, 49, tzinfo=datetime.timezone.utc),
                    'value': Decimal('30.020000000')
                },
                {
                    'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                    'block': 185371136,
                    'confirmations': 23244780,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt'],
                    'hash': '5mJiwcADUfKW5LJMZxqAMQsS6ETRx6tr9BnPPqZe1cyRdPrLsRaaFmUHVuj6okcbxVwhvbE5gnxuaLiLrx2m3p34',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 3, 29, 18, 1, 36, tzinfo=datetime.timezone.utc),
                    'value': Decimal('-51.539981000')
                },
                {
                    'address': 'ADtaKHTsYSmsty3MgLVfTQoMpM7hvFNTd2AxwN3hWRtt',
                    'block': 185370791,
                    'confirmations': 23245125,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['7yUBtfjFbxF669rf5p5fFFpNv6TbX9Z7UJkaUs2UxiPj'],
                    'hash': '52nEjPd9uKEHuBh6uWiUkNLSYeikKZH37zSYpbwc6s8QE4mwXUwVewV8H9j1iKNugPoBePnjehhJ8j195ZXWcuCs',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 3, 29, 17, 58, 55, tzinfo=datetime.timezone.utc),
                    'value': Decimal('51.540000000')
                },
            ]
        ]
        cls.get_address_txs(address_txs_mock_responses, expected_addresses_txs)
