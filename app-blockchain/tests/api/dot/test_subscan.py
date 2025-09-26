import json
from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

import pytest
from exchange.blockchain.api.dot.subscan import SubscanAPI


class TestSubscanAPI(TestCase):
    api = SubscanAPI()

    def test_get_staking_data(self):
        self.api.request = Mock()
        self.api.request.return_value = {'code': 0, 'message': 'Success', 'generated_at': 1671612248, 'data': {
            'account': {'account_display': {'address': '12T43xT6EyKUCntMLkBLuw8buVRTZ5ZAVQDF1bGr53LpCpvZ'},
                        'address': '12T43xT6EyKUCntMLkBLuw8buVRTZ5ZAVQDF1bGr53LpCpvZ', 'balance': '159.904395901',
                        'balance_lock': '158', 'bonded': '1580000000000', 'count_extrinsic': 3, 'democracy_lock': '0',
                        'derive_token': {}, 'election_lock': '0', 'is_council_member': False, 'is_erc20': False,
                        'is_evm_contract': False, 'is_registrar': False, 'is_techcomm_member': False, 'lock': '158',
                        'multisig': {}, 'nonce': 3, 'proxy': {}, 'registrar_info': None, 'reserved': '0',
                        'role': 'nominator',
                        'staking_info': {'controller': '12T43xT6EyKUCntMLkBLuw8buVRTZ5ZAVQDF1bGr53LpCpvZ',
                                         'controller_display': {
                                             'address': '12T43xT6EyKUCntMLkBLuw8buVRTZ5ZAVQDF1bGr53LpCpvZ'},
                                         'reward_account': 'stash'},
                        'stash': '12T43xT6EyKUCntMLkBLuw8buVRTZ5ZAVQDF1bGr53LpCpvZ', 'unbonding': '0',
                        'vesting': None}}}

        staking_info = self.api.get_staking_info('12T43xT6EyKUCntMLkBLuw8buVRTZ5ZAVQDF1bGr53LpCpvZ')

        assert staking_info.staked_balance == Decimal('158')
        assert staking_info.total_balance == Decimal('159.904395901')
        assert staking_info.delegated_balance == Decimal('158.0000000000')
        assert staking_info.free_balance == Decimal('1.904395901')

    @pytest.mark.slow
    def test_get_staking_info_api_request(self):
        api = SubscanAPI.get_api()
        data = {
            'key': '12T43xT6EyKUCntMLkBLuw8buVRTZ5ZAVQDF1bGr53LpCpvZ',
        }
        headers = {'Content-Type': 'application/json', 'x-api-key': api.get_api_key()}
        response = api.request('get_staking_data', headers=headers, body=json.dumps(data))

        assert list(response.keys()) == ['code', 'message', 'generated_at', 'data']
        assert list(response.get('data').keys()) == ['account']
        assert set(response.get('data').get('account').keys()) == {'account_display', 'address', 'balance',
                                                                   'balance_lock', 'bonded', 'count_extrinsic',
                                                                   'democracy_lock', 'election_lock',
                                                                   'is_council_member', 'is_erc20',
                                                                   'is_evm_contract',
                                                                   'is_fellowship_member', 'is_registrar',
                                                                   'is_techcomm_member', 'lock', 'multisig', 'nonce',
                                                                   'proxy', 'registrar_info', 'reserved', 'role',
                                                                   'staking_info', 'stash', 'substrate_account',
                                                                   'unbonding', 'vesting', 'assets_tag',
                                                                   'conviction_lock', 'delegate', 'evm_account',
                                                                   'is_erc721', 'is_module_account'}
