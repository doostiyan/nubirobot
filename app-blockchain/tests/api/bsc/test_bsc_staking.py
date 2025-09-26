from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from exchange.blockchain.api.bsc.bsc_web3_new import BSCWeb3Api, BSCWeb3Parser
from exchange.blockchain.api.general.dtos.get_validator_description_response import GetValidatorDescriptionResponse
from exchange.blockchain.api.general.dtos.get_validator_info_response import GetValidatorInfoResponse, ValidatorStatus
from exchange.blockchain.api.general.exceptions.invalid_response_exception import InvalidResponseError

# Constants
VALIDATOR_COUNT = 3
VALIDATOR_ADDRESSES_COUNT = 2
MAX_COMMISSION_RATE = 10000  # max commission rate in basis points

def test__get_validator_info__active(api, parser, validator_info_mock, created_time_iso, jail_until_iso):
    api.get_validator_info = Mock(return_value=validator_info_mock)

    parsed_response = parser.parse_get_validator_info(validator_info_mock, is_address_in_validators=True)
    assert isinstance(parsed_response, GetValidatorInfoResponse)
    assert parsed_response.status == ValidatorStatus.ACTIVE
    assert parsed_response.jail_until == jail_until_iso
    assert parsed_response.created_time == created_time_iso


def test__get_validator_info__jailed(api, parser, created_time, jail_until, created_time_iso, jail_until_iso):
    mock_response = (created_time, True, jail_until)
    api.get_validator_info = Mock(return_value=mock_response)

    parsed_response = parser.parse_get_validator_info(mock_response, is_address_in_validators=True)
    assert isinstance(parsed_response, GetValidatorInfoResponse)
    assert parsed_response.status == ValidatorStatus.JAILED
    assert parsed_response.jail_until == jail_until_iso
    assert parsed_response.created_time == created_time_iso


def test__get_validator_info__inactive(api, parser, validator_info_mock, created_time_iso, jail_until_iso):
    api.get_validator_info = Mock(return_value=validator_info_mock)

    parsed_response = parser.parse_get_validator_info(validator_info_mock, is_address_in_validators=False)
    assert isinstance(parsed_response, GetValidatorInfoResponse)
    assert parsed_response.status == ValidatorStatus.IN_ACTIVE
    assert parsed_response.jail_until == jail_until_iso
    assert parsed_response.created_time == created_time_iso


def test__get_validator_total_stake_from_contract__successful(api, parser):
    mock_response = Decimal('1000.5')
    api.get_validator_total_stake_from_contract = Mock(return_value=mock_response)

    parsed_response = parser.parse_get_validator_total_stake_from_contract(mock_response)
    assert isinstance(parsed_response, Decimal)
    assert parsed_response == Decimal('1000.5')


def test__get_validator_description__successful(api, parser, validator_description_mock):
    api.get_validator_description = Mock(return_value=validator_description_mock)

    parsed_response = parser.parse_get_validator_description(validator_description_mock)
    assert isinstance(parsed_response, GetValidatorDescriptionResponse)
    assert parsed_response.validator_name == 'Test Validator'
    assert parsed_response.website == 'https://test.com'


def test__get_validator_commission__successful(api, parser, validator_commission_mock):
    api.get_validator_commission = Mock(return_value=validator_commission_mock)

    parsed_response = parser.parse_get_validator_commission(validator_commission_mock)
    assert isinstance(parsed_response, Decimal)
    assert parsed_response == Decimal('500')


def test__get_reward_rate__successful(api, parser, reward_rate_mock):
    api.get_reward_rate = Mock(return_value=reward_rate_mock)

    parsed_response = parser.parse_get_reward_rate(reward_rate_mock)
    assert isinstance(parsed_response, Decimal)
    assert parsed_response == Decimal('0.105')


def test__get_all_validators_operator_addresses__successful(api, parser, validator_operator_addresses_mock):
    api.get_all_validators_operator_addresses = Mock(return_value=validator_operator_addresses_mock)

    parsed_response = parser.parse_get_all_operator_addresses(validator_operator_addresses_mock)
    assert isinstance(parsed_response, list)
    assert len(parsed_response) == VALIDATOR_COUNT
    assert parsed_response == ['addr1', 'addr2', 'addr3']


def test__get_txs_staked_balance__successful(api, parser, txs_staked_balance_mock):
    api.get_txs_staked_balance = Mock(return_value=txs_staked_balance_mock)

    balance, validator_addresses = parser.parse_get_txs_staked_balance(txs_staked_balance_mock)
    assert isinstance(balance, Decimal)
    assert balance == Decimal('3.0')
    assert isinstance(validator_addresses, list)
    assert len(validator_addresses) == VALIDATOR_ADDRESSES_COUNT


@patch('requests.post')
def test__get_reward_rate_api__successful(mock_post, api, reward_rate_api_mock):
    mock_post.return_value.json.return_value = reward_rate_api_mock
    mock_post.return_value.raise_for_status = Mock()

    response = api.get_reward_rate('TEST')
    assert response == reward_rate_api_mock
    mock_post.assert_called_once()


@patch('requests.post')
def test__get_reward_rate_api__invalid_response(mock_post, parser, invalid_reward_rate_api_mock):
    mock_post.return_value.json.return_value = invalid_reward_rate_api_mock
    mock_post.return_value.raise_for_status = Mock()

    with pytest.raises(InvalidResponseError):
        parser.parse_get_reward_rate(invalid_reward_rate_api_mock)


def test__parse_get_txs_staked_balance__empty_result(parser, empty_txs_staked_balance_mock):
    balance, validator_addresses = parser.parse_get_txs_staked_balance(empty_txs_staked_balance_mock)
    assert balance == Decimal('0')
    assert len(validator_addresses) == 0


def test__parse_get_txs_staked_balance__invalid_transaction(parser, invalid_txs_staked_balance_mock):
    balance, validator_addresses = parser.parse_get_txs_staked_balance(invalid_txs_staked_balance_mock)
    assert balance == Decimal('0')
    assert len(validator_addresses) == 0


def test__parse_get_txs_staked_balance__multiple_transactions(parser, multiple_txs_staked_balance_mock):
    balance, validator_addresses = parser.parse_get_txs_staked_balance(multiple_txs_staked_balance_mock)
    assert balance == Decimal('2.5')
    assert len(validator_addresses) == VALIDATOR_ADDRESSES_COUNT


def test__parse_get_validator_commission__zero(parser):
    mock_response = 0
    parsed_response = parser.parse_get_validator_commission(mock_response)
    assert isinstance(parsed_response, Decimal)
    assert parsed_response == Decimal('0')


def test__parse_get_validator_commission__max_value(parser):
    mock_response = MAX_COMMISSION_RATE
    parsed_response = parser.parse_get_validator_commission(mock_response)
    assert isinstance(parsed_response, Decimal)
    assert parsed_response == Decimal('10000')


def test__parse_get_all_validators_operator_addresses__empty(parser, empty_validator_addresses_mock):
    parsed_response = parser.parse_get_all_operator_addresses(empty_validator_addresses_mock)
    assert isinstance(parsed_response, list)
    assert len(parsed_response) == 0


def test__parse_get_all_validators_operator_addresses__single(parser, single_validator_address_mock):
    parsed_response = parser.parse_get_all_operator_addresses(single_validator_address_mock)
    assert isinstance(parsed_response, list)
    assert len(parsed_response) == 1
    assert parsed_response == single_validator_address_mock


def test__parse_get_all_validators_operator_addresses__multiple(parser, multiple_validator_addresses_mock):
    parsed_response = parser.parse_get_all_operator_addresses(multiple_validator_addresses_mock)
    assert isinstance(parsed_response, list)
    assert len(parsed_response) == VALIDATOR_COUNT
    assert parsed_response == multiple_validator_addresses_mock


def test__parse_get_validator_description__empty(parser, empty_validator_description_mock):
    parsed_response = parser.parse_get_validator_description(empty_validator_description_mock)
    assert isinstance(parsed_response, GetValidatorDescriptionResponse)
    assert parsed_response.validator_name == ''
    assert parsed_response.website == ''


def test__parse_get_validator_description__max_length(parser, max_length_validator_description_mock):
    parsed_response = parser.parse_get_validator_description(max_length_validator_description_mock)
    assert isinstance(parsed_response, GetValidatorDescriptionResponse)
    assert parsed_response.validator_name == 'A' * 100
    assert parsed_response.website == 'C' * 100
