from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

from exchange.base.models import Currencies
from exchange.blockchain.api.atom.atom_node import AtomAllthatnode
from exchange.blockchain.staking.staking_interface import StakingInterface


class TestAtomStakingInterface(TestCase):
    def test_atom_get_staking_data(self):
        address = 'cosmos16k9dx050vdst9jvwjlpt7tnc2v77v0c6lxu4wk'
        mocked_responses = [
            {'balances': [{'denom': 'uatom', 'amount': '24993011'}], 'pagination': {'next_key': None, 'total': '1'}},
            {'delegation_responses': [{'delegation': {'delegator_address': 'cosmos16k9dx050vdst9jvwjlpt7tnc2v77v0c6lxu4wk', 'validator_address': 'cosmosvaloper1rpgtz9pskr5geavkjz02caqmeep7cwwpv73axj', 'shares': '25010002.480295200295235857'}, 'balance': {'denom': 'uatom', 'amount': '25000000'}}], 'pagination': {'next_key': None, 'total': '1'}},
            {'rewards': [{'validator_address': 'cosmosvaloper1rpgtz9pskr5geavkjz02caqmeep7cwwpv73axj', 'reward': [{'denom': 'uatom', 'amount': '1966621.111050596549999999'}]}], 'total': [{'denom': 'uatom', 'amount': '1966621.111050596549999999'}]},
        ]
        AtomAllthatnode.get_api().request = Mock()
        AtomAllthatnode.get_api().request.side_effect = mocked_responses
        staking_info = StakingInterface.get_info(network='ATOM', address=address, currency=Currencies.atom)
        assert staking_info.address =='cosmos16k9dx050vdst9jvwjlpt7tnc2v77v0c6lxu4wk'
        assert staking_info.rewards_balance == Decimal('1.966621111050596549999999')
        assert staking_info.staked_balance == Decimal(25)
        assert staking_info.total_balance == Decimal('49.993011')
