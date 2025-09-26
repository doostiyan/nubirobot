from datetime import timedelta
from decimal import Decimal
from random import choices
from unittest.mock import patch

import jdatetime
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


class TestDebitCardSettlementsAPI(BetaFeatureTestMixin, APITestCase, ABCMixins):
    URL = '/asset-backed-credit/debit/cards/{card_id}/settlements'

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
    @patch('exchange.asset_backed_credit.externals.price.PriceProvider.get_nobitex_price', lambda _: 50_000)
    def test_success(self):
        self.request_feature(self.user, 'done')

        card = self._create_card(user=self.user, card_status=Card.STATUS.activated, pan='6063100020003000')
        self._create_settlements(card)

        _ids = DebitSettlementTransaction.objects.order_by('id').values_list('id', flat=True)
        dt1 = ir_now() - timedelta(days=1)
        dt2 = ir_now() - timedelta(days=2)
        dt3 = ir_now() - timedelta(days=3)
        DebitSettlementTransaction.objects.filter(id=_ids[0]).update(created_at=dt3)
        DebitSettlementTransaction.objects.filter(id=_ids[1]).update(created_at=dt2)
        DebitSettlementTransaction.objects.filter(id=_ids[2]).update(created_at=dt1)

        url = self.URL.format(card_id=card.id) + '?page=1&pageSize=5'
        response = self.client.get(path=url, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.json()['status'] == 'ok'
        assert not response.json()['hasNext']
        settlements = response.json()['settlements']

        assert len(settlements) == 5

        assert settlements[0]['amount'] == 500_000
        assert settlements[0]['balance'] == 1_500_000
        assert settlements[0]['type'] == 'خرید'

        assert settlements[1]['amount'] == 400_000
        assert settlements[1]['balance'] == 2_000_000
        assert settlements[1]['type'] == 'خرید'

        assert settlements[2]['amount'] == 300_000
        assert settlements[2]['balance'] == 1_400_000
        assert settlements[2]['type'] == 'خرید'

        assert settlements[3]['amount'] == 200_000
        assert settlements[3]['balance'] == 2_200_000
        assert settlements[3]['type'] == 'خرید'

        assert settlements[4]['amount'] == 100_000
        assert settlements[4]['balance'] == 2_400_000
        assert settlements[4]['type'] == 'خرید'

        url = self.URL.format(card_id=card.id) + '?page=1&pageSize=3'
        response = self.client.get(path=url, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.json()['status'] == 'ok'
        assert response.json()['hasNext']
        settlements = response.json()['settlements']

        assert len(settlements) == 3

        assert settlements[0]['amount'] == 500_000
        assert settlements[0]['balance'] == 1_500_000
        assert settlements[0]['type'] == 'خرید'

        assert settlements[1]['amount'] == 400_000
        assert settlements[1]['balance'] == 2_000_000
        assert settlements[1]['type'] == 'خرید'

        assert settlements[2]['amount'] == 300_000
        assert settlements[2]['balance'] == 1_400_000
        assert settlements[2]['type'] == 'خرید'

        url = self.URL.format(card_id=card.id) + '?page=2&pageSize=3'
        response = self.client.get(path=url, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.json()['status'] == 'ok'
        assert not response.json()['hasNext']
        settlements = response.json()['settlements']

        assert len(settlements) == 2

        assert settlements[0]['amount'] == 200_000
        assert settlements[0]['balance'] == 2_200_000
        assert settlements[0]['type'] == 'خرید'

        assert settlements[1]['amount'] == 100_000
        assert settlements[1]['balance'] == 2_400_000
        assert settlements[1]['type'] == 'خرید'

        from_date = jdatetime.datetime.fromgregorian(datetime=dt2).strftime('%Y-%m-%d')
        to_date = jdatetime.datetime.fromgregorian(datetime=dt1).strftime('%Y-%m-%d')
        url = f'{self.URL.format(card_id=card.id)}?fromDate={from_date}&toDate={to_date}'
        response = self.client.get(path=url, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.json()['status'] == 'ok'
        settlements = response.json()['settlements']

        assert len(settlements) == 2

        assert settlements[0]['amount'] == 300_000
        assert settlements[0]['balance'] == 1_400_000
        assert settlements[0]['type'] == 'خرید'

        assert settlements[1]['amount'] == 200_000
        assert settlements[1]['balance'] == 2_200_000
        assert settlements[1]['type'] == 'خرید'

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

    def test_feature_is_not_activated(self):
        url = self.URL.format(card_id='10')
        response = self.client.get(path=url, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'status': 'failed',
            'code': 'FeatureUnavailable',
            'message': 'abc_debit feature is not available for your user',
        }

    def _create_settlements(self, card):
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

        self._create_payment_transaction(card, 400_000, 40)
        self._create_payment_transaction(card, 500_000, 50, status=DebitSettlementTransaction.STATUS.unknown_confirmed)

    @staticmethod
    def _create_payment_transaction(card, amount: int, trace_id: int, **options):
        DebitSettlementTransaction.create(
            user_service=card.user_service,
            amount=Decimal(amount),
            status=options.get('status') or DebitSettlementTransaction.STATUS.confirmed,
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
