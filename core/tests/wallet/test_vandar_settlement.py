import math
from unittest.mock import patch

import pytest
import responses
from responses import matchers
from rest_framework.test import APITestCase

from exchange.accounts.models import BankAccount, User
from exchange.base.models import Currencies, Settings
from exchange.wallet.models import WithdrawRequest
from exchange.wallet.settlement import VandarSettlement
from tests.base.utils import create_withdraw_request


class VandarSettlementTest(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.get(id=201)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        self.withdraw = create_withdraw_request(
            self.user,
            Currencies.rls,
            210_000_000_0,
            'None: 546546546546546546546546',
            WithdrawRequest.STATUS.accepted,
        )
        self.withdraw.target_account = BankAccount.objects.create(
            bank_id=BankAccount.BANK_ID.vandar,
            account_number='123',
            shaba_number='123',
            user=self.user,
        )
        self.withdraw.save()

        self.vandar_settlement = VandarSettlement(self.withdraw)
        Settings.set('vandar_shaba_number', 'IR260620000000203443585001')

        self.successful_response = {
            'status': 1,
            'data': {
                'settlement': [
                    {
                        'id': '406f20d0-397a-11ec-b752-6b667e3fe6ba',
                        'iban_id': '083510a0-f998-11eb-8c11-27d425426e06',
                        'transaction_id': 163559577615,
                        'amount': 50000,
                        'amount_toman': 5000,
                        'wage_toman': 0,
                        'payment_number': None,
                        'status': 'PENDING',
                        'wallet': '221500',
                        'description': 'تسویه حساب وندار',
                        'settlement_date': '2021-10-30',
                        'settlement_time': '15:39:36',
                        'settlement_date_jalali': '1400/08/08',
                        'settlement_done_time_prediction': '1400/08/08 16:00:00',
                        'is_instant': None,
                        'prediction': {
                            'date': '1400/8/8',
                            'time': '16:00:00',
                            'extra': 'امروز',
                        },
                        'receipt_url': 'https://vand.ar/Mcz6C',
                        'type': 'A2A',
                    }
                ]
            },
        }

    def assert_successful(self):
        self.withdraw.refresh_from_db()
        assert self.withdraw.status == WithdrawRequest.STATUS.sent
        assert self.withdraw.updates == str(self.successful_response['data']['settlement'])
        assert self.withdraw.blockchain_url == f'nobitex://app/wallet/rls/transaction/WV{self.withdraw.pk}'
        assert self.withdraw.withdraw_from is None

    @responses.activate
    @patch('exchange.wallet.settlement.VandarSettlement.get_token', return_value='abcd')
    def test_vandar_do_settle(self, get_token):
        api_data = {
            'amount': int(math.ceil(self.vandar_settlement.net_amount / 10)),
            'iban': Settings.get('vandar_shaba_number'),
            'track_id': self.withdraw.pk,
            'payment_number': self.withdraw.target_account.account_number,
            'is_instant': True,
            'type': 'A2A',
        }
        responses.post(
            'https://api.vandar.io/v3/business/developers/settlement/store',
            json=self.successful_response,
            match=[matchers.json_params_matcher(api_data)],
        )

        self.vandar_settlement.do_settle()
        self.assert_successful()

    @responses.activate
    @patch('exchange.wallet.settlement.VandarSettlement.get_token', return_value='abcd')
    def test_vandar_do_settle_when_vandar_shaba_not_set(self, get_token):
        Settings.objects.filter(key='vandar_shaba_number').delete()

        responses.post(
            'https://api.vandar.io/v3/business/developers/settlement/store',
            json=self.successful_response,
        )
        with pytest.raises(ValueError, match='Vandar settlement: vandar_shaba_number setting is undefined!'):
            self.vandar_settlement.do_settle()
