from decimal import Decimal

from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.models import Settings
from exchange.direct_debit.constants import DEFAULT_MIN_DEPOSIT_AMOUNT


class DirectDebitConfigsTests(TestCase):
    fixtures = ('test_data',)

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'

    def test_v2_options_direct_debit_fees(self):
        response = self.client.get('/v2/options').json()
        expected_fees = {
            'rate': '0.002',
            'min': 1_000_0,
            'max': 5_000_0,
        }
        assert response['nobitex']['directDebitFee'] == expected_fees

    def test_v2_options_direct_debit_min_deposit(self):
        response = self.client.get('/v2/options').json()
        assert response['nobitex']['directDebitMinDeposit'] == str(DEFAULT_MIN_DEPOSIT_AMOUNT)

        Settings.set('direct_debit_min_amount_in_deposit', Decimal(3_000_0))

        response = self.client.get('/v2/options').json()
        assert response['nobitex']['directDebitMinDeposit'] == '30000'
