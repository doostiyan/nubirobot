import json as py_json
from unittest.mock import patch
from urllib.parse import urljoin
from attr import dataclass

from django.test import TestCase, override_settings
import pytest
import responses

from exchange.accounts.models import BankAccount, User
from exchange.base.models import Currencies
from exchange.wallet.models import Wallet, WithdrawRequest
from exchange.wallet.settlement import TomanSettlement


@dataclass
class MockResponse:
    status_code: int
    text: str

    def raise_for_status(self):
        if 400 <= self.status_code < 500:
            raise ValueError()

    def json(self):
        return py_json.loads(self.text)

    def set_result(self, status_code: int, result: dict):
        self.status_code = status_code
        self.text = py_json.dumps(result)

class TestTomanSettlement(TestCase):
    def setUp(self):
        self.settlement_url = urljoin(TomanSettlement.SANDBOX_API_URL, '/settlements/v2/')
        self.get_info_url = urljoin(TomanSettlement.SANDBOX_API_URL, '/settlements/tracking/')

        self.user = User.objects.get(pk=201)
        w1 = Wallet.get_user_wallet(self.user, Currencies.rls)
        tx = w1.create_transaction('manual', 100000)
        tx.commit()
        w1.refresh_from_db()

        bank_account = BankAccount.objects.create(
            user=self.user, shaba_number='546546546546546546546546', confirmed=True
        )

        self.wd = WithdrawRequest.objects.create(
            wallet=w1, amount=1000, status=WithdrawRequest.STATUS.accepted, target_account=bank_account,
        )
        self.toman_settlement = TomanSettlement(self.wd)

    def test_base_url(self):
        with override_settings(IS_PROD=False):
            assert self.toman_settlement.base_url == 'https://settlement-staging.qbitpay.org'
        with override_settings(IS_PROD=True):
            assert self.toman_settlement.base_url == 'https://settlement.tomanpay.net'

    def login(self):
        responses.post(
            'https://auth.qbitpay.org/oauth2/token/',
            status=200,
            json={
                'access_token': 'abcd',
                'expires_in': 100000,
            },
        )

    @responses.activate
    def test_do_settle_effect(self):
        responses.post(self.settlement_url, status=200, json=dict(uuid='1234'))
        uid = self.toman_settlement.do_settle()
        self.wd.refresh_from_db()

        assert uid == str(self.wd.pk)
        assert self.wd.status == WithdrawRequest.STATUS.sent
        assert self.wd.amount == 1000
        assert self.wd.blockchain_url == f'nobitex://app/wallet/rls/transaction/WT{self.wd.id}'

    @patch('exchange.shetab.handlers.toman.TomanClient.request')
    def test_do_settle_req_params(self, mock):
        mock.return_value = MockResponse(status_code=200, text='')
        self.toman_settlement.do_settle()
        mock.assert_called_once_with(
            'https://settlement-staging.qbitpay.org/settlements/v2/',
            'POST',
            json={
                'full_name': 'User One',
                'amount': 990,
                'description': f'واریز {self.wd.pk} به نوبیتکس',
                'tracker_id': self.wd.pk,
                'iban': '546546546546546546546546',
            },
        )

    @responses.activate
    def test_do_not_settle(self):
        self.login()

        def assert_unchanged():
            assert self.wd.status == WithdrawRequest.STATUS.manual_accepted

        responses.post(self.settlement_url, status=400, json={'detail': 'خطا'})
        with pytest.raises(ValueError):
            self.toman_settlement.do_settle()
        assert_unchanged()

        responses.post(self.settlement_url, status=401)
        with pytest.raises(ValueError):
            self.toman_settlement.do_settle()

        assert_unchanged()

        responses.post(self.settlement_url, status=500)
        with pytest.raises(ValueError):
            self.toman_settlement.do_settle()

        assert_unchanged()

    @responses.activate
    def test_get_info(self):
        self.login()
        responses.get(
            urljoin(self.get_info_url, str(self.wd.pk)),
            status=200,
            json=dict(uuid='1234', track_id=self.wd.pk, amount=self.wd.amount),
        )
        wd = self.toman_settlement.get_info()
        assert wd['track_id'] == self.wd.pk
        assert wd['amount'] == self.wd.amount

    @responses.activate
    def test_update_status_effect(self):
        with override_settings(IS_PROD=False):
            responses.get(
                urljoin(self.get_info_url, str(self.wd.pk)),
                status=200,
                json=dict(status=-1, bank_id=999),
            )

            old_status = self.wd.status
            old_blockchain_url = self.wd.blockchain_url
            self.toman_settlement.update_status()
            self.wd.refresh_from_db()
            assert self.wd.status == old_status
            assert self.wd.blockchain_url == old_blockchain_url

        with override_settings(IS_PROD=True):
            responses.get(
                urljoin(TomanSettlement.API_URL, '/settlements/tracking/') + str(self.wd.pk),
                status=200,
                json=dict(status=-1, bank_id=999),
            )
            old_status = self.wd.status
            old_blockchain_url = self.wd.blockchain_url
            self.toman_settlement.update_status()
            self.wd.refresh_from_db()
            assert self.wd.status == old_status
            assert self.wd.blockchain_url == 'nobitex://withdraw/AUTO--1/WT999'
