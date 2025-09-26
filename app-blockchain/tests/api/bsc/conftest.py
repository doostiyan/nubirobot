from decimal import Decimal
from unittest.mock import Mock

import pytest

from exchange.blockchain.api.bsc.bsc_web3_new import BSCWeb3Api, BSCWeb3Parser


@pytest.fixture
def created_time():
    return 1672531200  # 2023-01-01T00:00:00+00:00


@pytest.fixture
def jail_until():
    return 1704067200  # 2024-01-01T00:00:00+00:00


@pytest.fixture
def created_time_iso():
    return '2023-01-01T00:00:00+00:00'


@pytest.fixture
def jail_until_iso():
    return '2024-01-01T00:00:00+00:00'


@pytest.fixture
def api():
    return BSCWeb3Api()


@pytest.fixture
def parser():
    return BSCWeb3Parser()


@pytest.fixture
def validator_info_mock(created_time, jail_until):
    return (created_time, False, jail_until)


@pytest.fixture
def reward_rate_mock():
    return {
        'data': {
            'assets': [
                {
                    'metrics': [
                        {
                            'metricKey': 'real_reward_rate',
                            'defaultValue': '10.5',
                            'createdAt': '2024-01-01T00:00:00Z'
                        }
                    ]
                }
            ]
        }
    }


@pytest.fixture
def txs_staked_balance_mock():
    return {
        'result': [
            {
                'to': '0x0000000000000000000000000000000000002002',
                'from': '0x1234567890123456789012345678901234567890',
                'value': '1000000000000000000',
                'input': '0x123456789012345678901234567890123456789012345678901234567890123456789012345'
            },
            {
                'to': '0x0000000000000000000000000000000000002002',
                'from': '0x1234567890123456789012345678901234567890',
                'value': '2000000000000000000',
                'input': '0x123456789012345678901234567890123456789012345678901234567890123456789012345'
            }
        ]
    }


@pytest.fixture
def validator_description_mock():
    return ['Test Validator', None, 'https://test.com']


@pytest.fixture
def validator_commission_mock():
    return 500


@pytest.fixture
def validator_operator_addresses_mock():
    return ['addr1', 'addr2', 'addr3']


@pytest.fixture
def empty_txs_staked_balance_mock():
    return {'result': []}


@pytest.fixture
def invalid_txs_staked_balance_mock():
    return {
        'result': [
            {
                'to': '0x1234567890123456789012345678901234567890',
                'from': '0x0000000000000000000000000000000000002002',
                'value': '1000000000000000000',
                'input': '0x'
            }
        ]
    }


@pytest.fixture
def invalid_validator_description_mock():
    return ['', '', '']


@pytest.fixture
def reward_rate_api_mock():
    return {
        'data': {
            'reward_rate': '0.1'
        }
    }


@pytest.fixture
def invalid_reward_rate_api_mock():
    return {
        'data': None
    }


@pytest.fixture
def multiple_txs_staked_balance_mock():
    return {
        'result': [
            {
                'to': '0x0000000000000000000000000000000000002002',
                'from': '0x1234567890123456789012345678901234567890',
                'value': '1000000000000000000',
                'input': '0x123456789012345678901234567890123456789012345678901234567890123456789012345'
            },
            {
                'to': '0x0000000000000000000000000000000000002002',
                'from': '0x1234567890123456789012345678901234567890',
                'value': '2000000000000000000',
                'input': '0x123456789012345678901234567890123456789012345678901234567890123456789012345'
            },
            {
                'to': '0x1234567890123456789012345678901234567890',
                'from': '0x0000000000000000000000000000000000002002',
                'value': '500000000000000000',
                'input': '0x'
            }
        ]
    }


@pytest.fixture
def empty_validator_addresses_mock():
    return []


@pytest.fixture
def single_validator_address_mock():
    return ['0x1234567890123456789012345678901234567890']


@pytest.fixture
def multiple_validator_addresses_mock():
    return [
        '0x1234567890123456789012345678901234567890',
        '0x0987654321098765432109876543210987654321',
        '0xabcdef1234567890abcdef1234567890abcdef12'
    ]


@pytest.fixture
def empty_validator_description_mock():
    return ['', '', '']


@pytest.fixture
def max_length_validator_description_mock():
    return [
        'A' * 100,  # max length moniker
        'B' * 100,  # max length identity
        'C' * 100   # max length website
    ]
