from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

import pytest

from exchange.blockchain.api.atom.atom_node import AtomscanNode, AtomAllthatnode
from exchange.blockchain.utils import ValidationError


class TestAtomNodeAPI(TestCase):
    def test_validate_address(self):
        api = AtomscanNode()
        valid_addresses = ['cosmos1fm3tu2tgt57pcgst8g09frv6x2p6jy0p4h080x',
                           'cosmos1j8pp7zvcu9z8vd882m284j29fn2dszh05cqvf9']
        for address in valid_addresses:
            assert api.validate_address(address)

    def test_validate_address_not_valid_address(self):
        address = '0xe09caa4b6e78a79fd0be3a0278cd5071f17694ed'
        api = AtomscanNode()
        with self.assertRaises(ValidationError):
            api.validate_address(address)

    def test_get_delegated_balance(self):
        address = 'cosmos16k9dx050vdst9jvwjlpt7tnc2v77v0c6lxu4wk'
        api = AtomAllthatnode()
        api.request = Mock()
        api.request.return_value = {'delegation_responses': [{'delegation': {'delegator_address': 'cosmos16k9dx050vdst9jvwjlpt7tnc2v77v0c6lxu4wk', 'validator_address': 'cosmosvaloper1rpgtz9pskr5geavkjz02caqmeep7cwwpv73axj', 'shares': '25010002.480295200295235857'}, 'balance': {'denom': 'uatom', 'amount': '25000000'}}], 'pagination': {'next_key': None, 'total': '1'}}
        balance = api.get_delegated_balance(address)
        assert balance == Decimal(25.000000)

    def test_get_rewards_balance(self):
        address = 'cosmos16k9dx050vdst9jvwjlpt7tnc2v77v0c6lxu4wk'
        api = AtomAllthatnode()
        api.request = Mock()
        api.request.return_value = {'rewards': [{'validator_address': 'cosmosvaloper1rpgtz9pskr5geavkjz02caqmeep7cwwpv73axj', 'reward': [{'denom': 'uatom', 'amount': '1965523.358177451899999999'}]}], 'total': [{'denom': 'uatom', 'amount': '1965523.358177451899999999'}]}
        balance = api.get_staking_reward(address)
        assert balance == Decimal('1.965523358177451899999999')


@pytest.mark.slow
class TestAtomNodeLive(TestCase):
    address = 'cosmos16k9dx050vdst9jvwjlpt7tnc2v77v0c6lxu4wk'
    api = AtomAllthatnode()

    def test_get_delegated_balance_live(self):
        balance = self.api.get_delegated_balance(self.address)
        assert type(balance) is Decimal

    def test_get_rewards_balance_live(self):
        balance = self.api.get_staking_reward(self.address)
        assert type(balance) is Decimal


@pytest.mark.slow
class TestAtomNodeRequest(TestCase):
    address = 'cosmos16k9dx050vdst9jvwjlpt7tnc2v77v0c6lxu4wk'
    api = AtomAllthatnode()

    def test_get_delegated_balance_request(self):
        response = self.api.request('get_staked_balance', address=self.address, headers=self.api.get_header())
        assert self.api.dict_reset_values(response) == {'delegation_responses': [{'delegation': {'delegator_address': 0, 'validator_address': 0, 'shares': 0}, 'balance': {'denom': 0, 'amount': 0}}], 'pagination': {'next_key': 0, 'total': 0}}
