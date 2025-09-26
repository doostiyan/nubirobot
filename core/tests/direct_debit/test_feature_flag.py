from decimal import Decimal

from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.models import Settings
from exchange.base.serializers import serialize_decimal
from exchange.features.models import QueueItem
from tests.direct_debit.helper import DirectDebitMixins


class TestApiBanks(APITestCase, DirectDebitMixins):
    def setUp(self):
        self.user = User.objects.get(id=202)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.user.auth_token.key}'
        self.bank = self.create_bank(max_daily_transaction_amount=Decimal(1000), max_daily_transaction_count=5)
        self.contact = self.create_contract(user=self.user, bank=self.bank)

    def test_get_banks_checking_feature_flag(self):
        url = '/direct-debit/banks'
        response = self.client.get(url)
        assert response.status_code == 200
        output = response.json()
        assert output['status'] == 'failed'
        assert output['code'] == 'FeatureUnavailable'

        Settings.set('direct_debit_check_feature_flag', 'no')

        assert not QueueItem.objects.filter(
            user=self.user,
            feature=QueueItem.FEATURES.direct_debit,
            status=QueueItem.STATUS.done,
        ).exists()

        response = self.client.get(url)
        assert response.status_code == 200
        output = response.json()
        assert output['status'] == 'ok'
        assert output['banks'] == [
            {
                'id': self.bank.id,
                'bankName': self.bank.name,
                'bankID': self.bank.bank_id,
                'isActive': self.bank.is_active,
                'dailyMaxTransactionAmount': serialize_decimal(self.bank.daily_max_transaction_amount),
                'dailyMaxTransactionCount': self.bank.daily_max_transaction_count,
                'maxTransactionAmount': serialize_decimal(self.bank.max_transaction_amount),
            }
        ]
