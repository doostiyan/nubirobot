from _decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

import pytest

from exchange.blockchain.api.dot.subscan import SubscanAPI
from exchange.blockchain.staking.staking_interface import StakingInterface


class TestDotStaking(TestCase):
    addresses = ['12T43xT6EyKUCntMLkBLuw8buVRTZ5ZAVQDF1bGr53LpCpvZ']

    @pytest.mark.slow
    def test_get_staking_info(self):
        for address in self.addresses:
            staking_info = StakingInterface.get_info('DOT', address)
            assert staking_info.address is not None
            assert staking_info.staked_balance is not None
            assert staking_info.total_balance is not None
            assert staking_info.delegated_balance is not None
            assert staking_info.free_balance is not None

            assert staking_info.staked_balance + staking_info.free_balance == staking_info.total_balance

    def test_get_staking_info_mock(self):
        address = '12T43xT6EyKUCntMLkBLuw8buVRTZ5ZAVQDF1bGr53LpCpvZ'
        api = SubscanAPI.get_api()
        api.request = Mock()
        api.request.return_value = {'code': 0, 'message': 'Success', 'generated_at': 1671612248, 'data': {'account': {'account_display': {'address': '12T43xT6EyKUCntMLkBLuw8buVRTZ5ZAVQDF1bGr53LpCpvZ'},'address': '12T43xT6EyKUCntMLkBLuw8buVRTZ5ZAVQDF1bGr53LpCpvZ', 'balance': '159.904395901', 'balance_lock': '158', 'bonded': '1580000000000', 'count_extrinsic': 3, 'democracy_lock': '0', 'derive_token': {}, 'election_lock': '0', 'is_council_member': False, 'is_erc20': False,'is_evm_contract': False, 'is_registrar': False, 'is_techcomm_member': False, 'lock': '158','multisig': {}, 'nonce': 3, 'proxy': {}, 'registrar_info': None, 'reserved': '0','role': 'nominator','staking_info': {'controller': '12T43xT6EyKUCntMLkBLuw8buVRTZ5ZAVQDF1bGr53LpCpvZ','controller_display': {'address': '12T43xT6EyKUCntMLkBLuw8buVRTZ5ZAVQDF1bGr53LpCpvZ'},'reward_account': 'stash'},'stash': '12T43xT6EyKUCntMLkBLuw8buVRTZ5ZAVQDF1bGr53LpCpvZ', 'unbonding': '0','vesting': None}}}

        staking_info = StakingInterface.get_info('DOT', address)

        assert staking_info.staked_balance == Decimal('158')
        assert staking_info.total_balance == Decimal('159.904395901')
        assert staking_info.delegated_balance == Decimal('158.0000000000')
        assert staking_info.free_balance == Decimal('1.904395901')
