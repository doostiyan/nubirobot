from decimal import Decimal
from random import choices
from unittest.mock import patch

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import (
    Card,
    DebitSettlementTransaction,
    Service,
    UserFinancialServiceLimit,
    UserService,
    UserServicePermission,
)
from exchange.asset_backed_credit.tasks import task_settle_pending_user_settlements
from exchange.asset_backed_credit.types import DEBIT_FEATURE_FLAG
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies, Settings
from exchange.wallet.functions import transfer_balance
from exchange.wallet.models import Wallet as ExchangeWallet
from tests.asset_backed_credit.helper import ABCMixins
from tests.features.utils import BetaFeatureTestMixin


class TestDebitCardSettlementsAPI(BetaFeatureTestMixin, ABCMixins, APITestCase):
    URL = '/asset-backed-credit/debit/cards/{card_id}/transfers'

    feature = DEBIT_FEATURE_FLAG

    @classmethod
    def setUpTestData(cls):
        Settings.set('abc_debit_wallet_enabled', 'yes')

        user, _ = User.objects.get_or_create(username='debit_user')
        another_user, _ = User.objects.get_or_create(username='another_debit_user')
        service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit, is_active=True
        )
        UserFinancialServiceLimit.set_service_limit(service=service, min_limit=50_000, max_limit=100_000_000)

        cls.user = user
        cls.another_user = another_user
        cls.service = service

    def setUp(self):
        self.client.force_authenticate(user=self.user)

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_card_not_found_error(self):
        self.request_feature(self.user, 'done')

        url = self.URL.format(card_id=3)
        response = self.client.get(path=url, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['status'] == 'failed'
        assert response.json()['code'] == 'CardNotFound'
        assert response.json()['message'] == 'card not found.'

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_card_not_found_error_user_has_card(self):
        self.request_feature(self.user, 'done')

        _ = self._create_card(user=self.user)
        another_card = self._create_card(user=self.another_user)

        url = self.URL.format(card_id=another_card.id)
        response = self.client.get(path=url, format='json')

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['status'] == 'failed'
        assert response.json()['code'] == 'CardNotFound'
        assert response.json()['message'] == 'card not found.'

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_service_not_found(self):
        self.request_feature(self.user, 'done')

        card = self._create_card(user=self.user)
        _ = self._create_card(user=self.another_user)

        with patch('exchange.asset_backed_credit.models.service.Service.get_matching_active_service', lambda **_: None):
            url = self.URL.format(card_id=card.id)
            response = self.client.get(path=url, format='json')

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['status'] == 'failed'
        assert response.json()['code'] == 'ServiceNotFoundError'
        assert response.json()['message'] == 'ServiceNotFoundError'

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    @patch('exchange.market.markprice.MarkPriceCalculator.get_mark_price', lambda _, __: 50_000)
    @patch('exchange.asset_backed_credit.services.settlement._send_notification', lambda _: None)
    @patch('exchange.market.models.Market.get_last_trade_price', lambda _: 50_000)
    def test_success(self):
        self.request_feature(self.user, 'done')

        card = self._create_card(user=self.user, card_status=Card.STATUS.activated, pan='6063100020003000')

        self.charge_exchange_wallet(self.user, Currencies.rls, amount=2_000_000, tp=ExchangeWallet.WALLET_TYPE.spot)
        self.charge_exchange_wallet(self.user, Currencies.rls, amount=3_000_000, tp=ExchangeWallet.WALLET_TYPE.debit)
        self.charge_exchange_wallet(self.user, Currencies.usdt, amount=1000, tp=ExchangeWallet.WALLET_TYPE.spot)

        self._create_transfer_from_debit_wallet_transaction(500_000, Currencies.rls)
        self._create_payment_transaction(card, 100_000, 10)
        self._create_payment_transaction(card, 200_000, 20)

        self._create_transfer_from_debit_wallet_transaction(500_000, Currencies.rls)
        self._create_payment_transaction(card, 300_000, 30)

        self._create_transfer_from_debit_wallet_transaction(500_000, Currencies.rls)
        self._create_transfer_to_debit_wallet_transaction(30, Currencies.usdt)

        url = self.URL.format(card_id=card.id) + '?page=1&pageSize=2'
        response = self.client.get(path=url, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.json()['status'] == 'ok'
        assert response.json()['hasNext']
        transfers = response.json()['transfers']

        assert transfers[0]['amount'] == 30
        assert transfers[0]['balance'] == 30
        assert transfers[0]['type'] == 'واریز'
        assert transfers[0]['currency'] == 'usdt'

        assert transfers[1]['amount'] == 500_000
        assert transfers[1]['balance'] == 900_000
        assert transfers[1]['type'] == 'برداشت'
        assert transfers[1]['currency'] == 'rls'

        url = self.URL.format(card_id=card.id) + '?page=2&pageSize=2'
        response = self.client.get(path=url, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.json()['status'] == 'ok'
        assert not response.json()['hasNext']
        transfers = response.json()['transfers']

        assert transfers[0]['amount'] == 500_000
        assert transfers[0]['balance'] == 1_700_000
        assert transfers[0]['type'] == 'برداشت'
        assert transfers[0]['currency'] == 'rls'

        assert transfers[1]['amount'] == 500_000
        assert transfers[1]['balance'] == 2_500_000
        assert transfers[1]['type'] == 'برداشت'
        assert transfers[1]['currency'] == 'rls'

    def test_feature_is_not_activated(self):
        url = self.URL.format(card_id='10')
        response = self.client.get(path=url, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'status': 'failed',
            'code': 'FeatureUnavailable',
            'message': 'abc_debit feature is not available for your user',
        }

    def _create_card(self, user, card_status=Card.STATUS.requested, pan=None):
        permission = UserServicePermission.objects.create(user=user, service=self.service, created_at=ir_now())
        user_service = UserService.objects.create(
            user=user,
            user_service_permission=permission,
            service=self.service,
            current_debt=10_000_000,
            initial_debt=10_000_000,
        )
        if not pan:
            pan = '6063' + ''.join(choices(['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'], k=12))

        return Card.objects.create(user=user, user_service=user_service, status=card_status, pan=pan)

    @staticmethod
    def _create_payment_transaction(card, amount: int, trace_id: int):
        DebitSettlementTransaction.create(
            user_service=card.user_service,
            amount=Decimal(amount),
            status=DebitSettlementTransaction.STATUS.confirmed,
            pan=card.pan,
            rrn=f'rrn: {amount}',
            trace_id=f'trace_id: {trace_id}',
            terminal_id=f'terminal_id: {trace_id}',
            rid=f'rid: {trace_id}',
        )
        task_settle_pending_user_settlements()

    def _create_transfer_from_debit_wallet_transaction(self, amount, currency):
        transfer_balance(
            user=self.user,
            currency=currency,
            amount=amount,
            src_type=ExchangeWallet.WALLET_TYPE.debit,
            dst_type=ExchangeWallet.WALLET_TYPE.spot,
        )

    def _create_transfer_to_debit_wallet_transaction(self, amount, currency):
        transfer_balance(
            user=self.user,
            currency=currency,
            amount=amount,
            src_type=ExchangeWallet.WALLET_TYPE.spot,
            dst_type=ExchangeWallet.WALLET_TYPE.debit,
        )
