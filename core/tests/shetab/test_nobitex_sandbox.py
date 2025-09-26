
from unittest.mock import Mock
from django.test import TestCase, override_settings
from django.urls import reverse
import pytest
from rest_framework.test import APITestCase
from exchange import settings

from exchange.accounts.models import BankCard, User
from exchange.base.helpers import get_base_api_url
from exchange.base.models import Settings
from exchange.shetab.handlers.nobitex import NobitexHandler
from exchange.shetab.models import ShetabDeposit

class NobitexSandboxTest(APITestCase):
    URL = '/users/wallets/deposit/sandbox-gateway'

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.deposit = ShetabDeposit.objects.create(
            user=self.user,
            selected_card=BankCard.objects.create(
                user=self.user,
                card_number='1234123412341234',
                owner_name=self.user.get_full_name(),
                bank_id=10,
                confirmed=True,
                status=BankCard.STATUS.confirmed,
            ),
            amount=123133,
            broker=ShetabDeposit.BROKER.nobitex,
            nextpay_id='123',
        )

    def test_sandbox_nobitex(self):
        resp = self.client.get(self.URL + f'?depositId={self.deposit.id}')
        assert resp.status_code == 200

    @override_settings(IS_PROD=True)
    def test_sandbox_nobitex_in_prod(self):
        resp = self.client.get(self.URL + f'?depositId={self.deposit.id}')
        assert resp.status_code == 403

    def test_sandbox_nobitex_when_deposit_not_exists(self):
        resp = self.client.get(self.URL + '?depositId=-1')
        assert resp.status_code == 404


class CreateShetabWithNobitexSandboxTest(APITestCase):
    URL = '/users/wallets/deposit/shetab'

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.user.user_type = User.USER_TYPES.verified
        self.user.save()
        self.bank_card = BankCard.objects.create(
            user=self.user,
            card_number='1234123412341234',
            owner_name=self.user.get_full_name(),
            bank_id=10,
            confirmed=True,
            status=BankCard.STATUS.confirmed,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def test_create_deposit_with_nobitex_sandbox(self):
        resp = self.client.post(self.URL, dict(amount=1000, selectedCard=self.bank_card.id))
        assert resp.status_code == 200
        result = resp.json()
        assert result['status'] == 'ok'
        assert result['deposit']['gateway'] == 'Nobitex'
        assert result['deposit']['next'] == (
            get_base_api_url(trailing_slash=False) + reverse('sandbox_gateway') + f'?depositId={result["deposit"]["id"]}'
        )

    @override_settings(IS_PROD=True)
    def test_create_deposit_in_prod(self):
        Settings.set('shetab_deposit_backend', 'vandar')

        resp = self.client.post(self.URL, dict(amount=1000, selectedCard=self.bank_card.id))
        assert resp.status_code == 200
        result = resp.json()
        assert result['status'] == 'ok'
        assert result['deposit']['gateway'] == 'Vandar'

class NobitexShetabHandlerTest(TestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.deposit = ShetabDeposit.objects.create(
            user=self.user,
            selected_card=BankCard.objects.create(
                user=self.user,
                card_number='1234123412341234',
                owner_name=self.user.get_full_name(),
                bank_id=10,
                confirmed=True,
                status=BankCard.STATUS.confirmed,
            ),
            amount=123133,
            broker=ShetabDeposit.BROKER.nobitex,
            nextpay_id='123',
        )

    @override_settings(IS_PROD=True)
    def test_nobitex_handler_sync_in_prod(self):
        with pytest.raises(TypeError):
            NobitexHandler.sync(self.deposit, Mock())

    def test_nobitex_handler_sync_unmatched_broker(self):
        self.deposit.broker = ShetabDeposit.BROKER.vandar
        self.deposit.status_code = -1000
        self.deposit.save()
        resp = NobitexHandler.sync(self.deposit, Mock())
        self.deposit.refresh_from_db()
        assert resp is None
        assert self.deposit.status_code == -1000

    def test_nobitex_handler_sync_when_is_requested(self):
        class MockedRequest:
            POST = dict(amount=1)

        # Unmatched amount
        NobitexHandler.sync(self.deposit, MockedRequest)
        self.deposit.refresh_from_db()
        assert self.deposit.status_code == 102997

        # No amount
        MockedRequest.POST = {}
        NobitexHandler.sync(self.deposit, MockedRequest)
        self.deposit.refresh_from_db()
        assert self.deposit.status_code == 102998

        # accept
        MockedRequest.POST = dict(amount=self.deposit.amount, status='accept')
        NobitexHandler.sync(self.deposit, MockedRequest)
        self.deposit.refresh_from_db()
        assert self.deposit.status_code == 1
        assert self.deposit.user_card_number == '1234123412341234'

        # reject
        MockedRequest.POST = dict(amount=self.deposit.amount, status='reject')
        NobitexHandler.sync(self.deposit, MockedRequest)
        self.deposit.refresh_from_db()
        assert self.deposit.status_code == 102999
        assert not self.deposit.is_status_done
        assert self.deposit.user_card_number == '1234123412341234'

    def test_nobitex_handler_sync_when_not_requested(self):
        self.deposit.nextpay_id = None
        self.deposit.save()

        NobitexHandler.sync(self.deposit, Mock())
        self.deposit.refresh_from_db()
        assert self.deposit.status_code == 0
        assert self.deposit.nextpay_id == str(self.deposit.pk)
        assert self.deposit.gateway_redirect_url == (
            get_base_api_url(trailing_slash=False) + reverse('sandbox_gateway') + f'?depositId={self.deposit.pk}'
        )
