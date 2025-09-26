import datetime
from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

import pytest

from exchange.blockchain.api.bnb.bnbchain import Bnbchain
from exchange.blockchain.utils import BlockchainUtilsMixin


class TestBnbchainMocked(TestCase):
    address = 'bnb1n75v3v6ssk4e5uqrtuk09vlz4n32r9vs270qh9'

    def test_get_delegated_balance(self):
        api = Bnbchain.get_api()
        api.request = Mock()
        api.request.return_value = {'delegated': 1.3, 'unbonding': 0, 'asset': 'BNB'}
        balance = api.get_delegated_balance(self.address)
        assert balance == Decimal('1.3')

    def test_get_staking_reward(self):
        api = Bnbchain.get_api()
        api.request = Mock()
        api.request.return_value = {'total': 15, 'rewardDetails': [{'id': 34116597, 'chainId': 'bsc', 'validator': 'bva1c6aqe9ndzcn2nsan963z43xg6kgrvzynl97785', 'valName': 'TW Staking', 'delegator': 'bnb1n75v3v6ssk4e5uqrtuk09vlz4n32r9vs270qh9', 'reward': 0.00013033, 'height': 294555118, 'rewardTime': '2023-02-04T00:00:00.000+00:00'}, {'id': 34067100, 'chainId': 'bsc', 'validator': 'bva1c6aqe9ndzcn2nsan963z43xg6kgrvzynl97785', 'valName': 'TW Staking', 'delegator': 'bnb1n75v3v6ssk4e5uqrtuk09vlz4n32r9vs270qh9', 'reward': 0.00012552, 'height': 294349888, 'rewardTime': '2023-02-03T00:00:00.000+00:00'}, {'id': 34014760, 'chainId': 'bsc', 'validator': 'bva1c6aqe9ndzcn2nsan963z43xg6kgrvzynl97785', 'valName': 'TW Staking', 'delegator': 'bnb1n75v3v6ssk4e5uqrtuk09vlz4n32r9vs270qh9', 'reward': 0.00011665, 'height': 294144914, 'rewardTime': '2023-02-02T00:00:00.000+00:00'}, {'id': 33958286, 'chainId': 'bsc', 'validator': 'bva1c6aqe9ndzcn2nsan963z43xg6kgrvzynl97785', 'valName': 'TW Staking', 'delegator': 'bnb1n75v3v6ssk4e5uqrtuk09vlz4n32r9vs270qh9', 'reward': 0.00014416, 'height': 293938579, 'rewardTime': '2023-02-01T00:00:00.000+00:00'}, {'id': 33913520, 'chainId': 'bsc', 'validator': 'bva1c6aqe9ndzcn2nsan963z43xg6kgrvzynl97785', 'valName': 'TW Staking', 'delegator': 'bnb1n75v3v6ssk4e5uqrtuk09vlz4n32r9vs270qh9', 'reward': 0.00012207, 'height': 293732529, 'rewardTime': '2023-01-31T00:00:00.000+00:00'}, {'id': 33854824, 'chainId': 'bsc', 'validator': 'bva1c6aqe9ndzcn2nsan963z43xg6kgrvzynl97785', 'valName': 'TW Staking', 'delegator': 'bnb1n75v3v6ssk4e5uqrtuk09vlz4n32r9vs270qh9', 'reward': 0.00010354, 'height': 293527357, 'rewardTime': '2023-01-30T00:00:00.000+00:00'}, {'id': 33813753, 'chainId': 'bsc', 'validator': 'bva1c6aqe9ndzcn2nsan963z43xg6kgrvzynl97785', 'valName': 'TW Staking', 'delegator': 'bnb1n75v3v6ssk4e5uqrtuk09vlz4n32r9vs270qh9', 'reward': 0.00010745, 'height': 293321603, 'rewardTime': '2023-01-29T00:00:00.000+00:00'}, {'id': 33754960, 'chainId': 'bsc', 'validator': 'bva1c6aqe9ndzcn2nsan963z43xg6kgrvzynl97785', 'valName': 'TW Staking', 'delegator': 'bnb1n75v3v6ssk4e5uqrtuk09vlz4n32r9vs270qh9', 'reward': 0.00010574, 'height': 293115648, 'rewardTime': '2023-01-28T00:00:00.000+00:00'}, {'id': 33697187, 'chainId': 'bsc', 'validator': 'bva1c6aqe9ndzcn2nsan963z43xg6kgrvzynl97785', 'valName': 'TW Staking', 'delegator': 'bnb1n75v3v6ssk4e5uqrtuk09vlz4n32r9vs270qh9', 'reward': 0.00010244, 'height': 292910609, 'rewardTime': '2023-01-27T00:00:00.000+00:00'}, {'id': 33662210, 'chainId': 'bsc', 'validator': 'bva1c6aqe9ndzcn2nsan963z43xg6kgrvzynl97785', 'valName': 'TW Staking', 'delegator': 'bnb1n75v3v6ssk4e5uqrtuk09vlz4n32r9vs270qh9', 'reward': 0.00010315, 'height': 292706042, 'rewardTime': '2023-01-26T00:00:00.000+00:00'}, {'id': 33611530, 'chainId': 'bsc', 'validator': 'bva1c6aqe9ndzcn2nsan963z43xg6kgrvzynl97785', 'valName': 'TW Staking', 'delegator': 'bnb1n75v3v6ssk4e5uqrtuk09vlz4n32r9vs270qh9', 'reward': 9.691e-05, 'height': 292502051, 'rewardTime': '2023-01-25T00:00:00.000+00:00'}, {'id': 33560353, 'chainId': 'bsc', 'validator': 'bva1c6aqe9ndzcn2nsan963z43xg6kgrvzynl97785', 'valName': 'TW Staking', 'delegator': 'bnb1n75v3v6ssk4e5uqrtuk09vlz4n32r9vs270qh9', 'reward': 9.676e-05, 'height': 292299787, 'rewardTime': '2023-01-24T00:00:00.000+00:00'}, {'id': 33499795, 'chainId': 'bsc', 'validator': 'bva1c6aqe9ndzcn2nsan963z43xg6kgrvzynl97785', 'valName': 'TW Staking', 'delegator': 'bnb1n75v3v6ssk4e5uqrtuk09vlz4n32r9vs270qh9', 'reward': 0.00012886, 'height': 292096762, 'rewardTime': '2023-01-23T00:00:00.000+00:00'}, {'id': 33459580, 'chainId': 'bsc', 'validator': 'bva1c6aqe9ndzcn2nsan963z43xg6kgrvzynl97785', 'valName': 'TW Staking', 'delegator': 'bnb1n75v3v6ssk4e5uqrtuk09vlz4n32r9vs270qh9', 'reward': 0.00011303, 'height': 291892969, 'rewardTime': '2023-01-22T00:00:00.000+00:00'}, {'id': 33388609, 'chainId': 'bsc', 'validator': 'bva1c6aqe9ndzcn2nsan963z43xg6kgrvzynl97785', 'valName': 'TW Staking', 'delegator': 'bnb1n75v3v6ssk4e5uqrtuk09vlz4n32r9vs270qh9', 'reward': 9.843e-05, 'height': 291688404, 'rewardTime': '2023-01-21T00:00:00.000+00:00'}]}
        start_date = datetime.datetime(2023, 1, 21)
        end_date = datetime.datetime(2023, 4, 30)
        balance = api.get_staking_reward(self.address, start_date, end_date)
        assert balance == Decimal('0.00169504')

    def test_calculate_duration(self):
        input_data = [
            # (start_date, end_date)
            (datetime.date(2023, 3, 13), datetime.date(2023, 3, 15)),
            (datetime.date(2023, 3, 13), datetime.date(2023, 3, 13)),
            (None, None),
        ]
        expected_data = [
            # (start_date, end_date, duration)
            (datetime.date(2023, 3, 13), datetime.date(2023, 3, 15), 3),
            (datetime.date(2023, 3, 13), datetime.date(2023, 3, 13), 1),
            (datetime.date.today() - datetime.timedelta(days=Bnbchain.REQUEST_MAX_LIMIT - 1), datetime.date.today(),
             100),
        ]
        for index, data in enumerate(input_data):
            results = Bnbchain.calculate_duration(data[0], data[1])
            assert expected_data[index][2] == results[0]
            assert expected_data[index][0] == results[1]
            assert expected_data[index][1] == results[2]


@pytest.mark.slow
class TestBnbchainRequest(TestCase):
    address = 'bnb1n75v3v6ssk4e5uqrtuk09vlz4n32r9vs270qh9'

    def test_get_delegated_balance(self):
        api = Bnbchain.get_api()
        response = api.request('get_staked_balance', address=self.address)
        assert list(response) == ['delegated', 'unbonding', 'asset']

    def test_get_staking_reward(self):
        api = Bnbchain.get_api()
        response = api.request('get_staking_reward', address=self.address, offset=0, limit=2)
        assert BlockchainUtilsMixin.dict_reset_values(response) == {'total': 0, 'rewardDetails': [{'id': 0, 'chainId': 0, 'validator': 0, 'valName': 0, 'delegator': 0, 'reward': 0, 'height': 0, 'rewardTime': 0}, {'id': 0, 'chainId': 0, 'validator': 0, 'valName': 0, 'delegator': 0, 'reward': 0, 'height': 0, 'rewardTime': 0}]}
