from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

import pytest

from exchange.blockchain.api.common_apis.web3 import Web3API
from exchange.blockchain.api.polygon.ankr_validators_share_contract import AnkrValidatorShareContract
from exchange.blockchain.staking.matic_staking import MaticStaking
from exchange.blockchain.staking.staking_interface import StakingInterface
from exchange.blockchain.utils import BlockchainUtilsMixin


@pytest.mark.slow
class TestPolygonStaking(TestCase):
    addresses = ['0x20aB9553C4a2afCa5EB9D9261158abd650cAcE3B']

    def test_get_staked_balance(self):
        for address in self.addresses:
            assert MaticStaking().get_staked_balance(address) is not None

    def test_get_rewards_balance(self):
        for address in self.addresses:
            assert MaticStaking().get_rewards_balance(address) is not None

    def test_get_free_balance(self):
        for address in self.addresses:
            assert MaticStaking().get_free_balance(address) is not None

    def test_get_staking_info(self):
        for address in self.addresses:
            staking_info = StakingInterface.get_info('MATIC', address)
            assert staking_info.address is not None
            assert staking_info.staked_balance is not None
            assert staking_info.total_balance is not None
            assert staking_info.rewards_balance is not None
            assert staking_info.free_balance is not None

            assert staking_info.staked_balance + staking_info.free_balance == staking_info.total_balance


class TestPolygonStakingMock(TestCase):
    addresses = ['0x20aB9553C4a2afCa5EB9D9261158abd650cAcE3B']

    def test_get_staking_info(self):
        mocked_staked_balance_responses = [200000000000000000000]
        mocked_rewards_balance_responses = [3764129916270958681]
        mocked_free_balance_responses = [
            {'symbol': 'matic', 'amount': 95, 'address': '0x20aB9553C4a2afCa5EB9D9261158abd650cAcE3B'}
        ]

        provider = AnkrValidatorShareContract.get_instance()

        mocked_staked_balance_responses = map(lambda x: BlockchainUtilsMixin.from_unit(x, provider.PRECISION), mocked_staked_balance_responses)
        provider.get_staked_balance = Mock(
            side_effect=mocked_staked_balance_responses)

        mocked_rewards_balance_responses = map(lambda x: BlockchainUtilsMixin.from_unit(x, provider.PRECISION), mocked_rewards_balance_responses)
        provider.get_rewards_balance = Mock(
            side_effect=mocked_rewards_balance_responses)

        Web3API.get_api().get_token_balance = Mock(side_effect=mocked_free_balance_responses)

        for address in self.addresses:
            staking_info = StakingInterface.get_info('MATIC', address)
            assert staking_info.address == address
            assert staking_info.staked_balance == 200
            assert staking_info.total_balance == 295
            assert staking_info.rewards_balance == Decimal('3.764129916270958681')
            assert staking_info.free_balance == 95

            assert staking_info.staked_balance + staking_info.free_balance == staking_info.total_balance
