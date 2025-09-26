from decimal import Decimal
from unittest import TestCase

import pytest

from exchange.blockchain.api.polygon.ankr_validators_share_contract import AnkrValidatorShareContract


@pytest.mark.slow
class TestAnkrValidatorShareContract(TestCase):
    api = AnkrValidatorShareContract()
    addresses = ['0x20aB9553C4a2afCa5EB9D9261158abd650cAcE3B']

    def test_get_rewards_response(self):
        for address in self.addresses:
            rewards_balance = self.api.get_rewards_balance(address)
            assert rewards_balance is not None
            assert type(rewards_balance) is Decimal

    def test_get_staked_balance(self):
        for address in self.addresses:
            rewards_balance = self.api.get_staked_balance(address)
            assert rewards_balance is not None
            assert type(rewards_balance) is Decimal
