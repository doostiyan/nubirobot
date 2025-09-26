from decimal import Decimal
from exchange.accounts.models import User
from exchange.base.models import Currencies
from exchange.settings import NOBITEX_OPTIONS
from exchange.wallet.models import Wallet, WithdrawRequest
from rest_framework.test import APITestCase
from tests.base.utils import create_withdraw_request
from pytest_django.asserts import assertTemplateUsed
from django.test.utils import override_settings
from django.core.cache import cache


class DirectConfirmWithdrawTest(APITestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        Wallet.create_user_wallets(self.user)
        self.user.user_type = User.USER_TYPES.verified
        self.user.save()
        bitcoin_price = Decimal(997_000_000_0)
        cache.set('orderbook_BTCIRT_best_active_buy', bitcoin_price)
        self.my_nobitex_option = NOBITEX_OPTIONS
        self.my_nobitex_option['withdrawLimits'][90] = {'dailyCoin': Decimal('1_000_000_000_0'),
                                                        'dailyRial': Decimal('1_000_000_000_0'),
                                                        'dailySummation': Decimal('1_000_000_000_0'),
                                                        'monthlySummation': Decimal('15_000_000_000_0')}

    def test_direct_confirm_withdraw_success(self):
        with override_settings(NOBITEX_OPTIONS=self.my_nobitex_option):
            withdraw_request = create_withdraw_request(user=self.user, currency=Currencies.btc, amount=0.5, status=1)
            response = self.client.get(f'/direct/confirm-withdraw/{withdraw_request.id}/{withdraw_request.token}')
            assertTemplateUsed(response, 'wallet/withdraw_confirm_success.html')
            withdraw_request.refresh_from_db()
            self.assertEqual(withdraw_request.status, WithdrawRequest.STATUS.verified)

    def test_direct_confirm_withdraw_failed_cuz_limitation(self):
        with override_settings(NOBITEX_OPTIONS=self.my_nobitex_option):
            withdraw_request = create_withdraw_request(user=self.user, currency=Currencies.btc, amount=2, status=1)
            response = self.client.get(f'/direct/confirm-withdraw/{withdraw_request.id}/{withdraw_request.token}')
            assertTemplateUsed(response, 'wallet/withdraw_confirm_failure.html')
            self.assertEqual(response.context['status'], 'limited')
            withdraw_request.refresh_from_db()
            self.assertEqual(withdraw_request.status, WithdrawRequest.STATUS.new)

    def test_direct_confirm_withdraw_failed_cuz_bad_request(self):
        with override_settings(NOBITEX_OPTIONS=self.my_nobitex_option):
            withdraw_request = create_withdraw_request(user=self.user, currency=Currencies.btc, amount=1, status=1)
            response = self.client.get(f'/direct/confirm-withdraw/{withdraw_request.id}/aaaaaa-bad-token-bbbbbbb')
            assertTemplateUsed(response, 'wallet/withdraw_confirm_failure.html')
            self.assertEqual(response.context['status'], 'bad_request')
            withdraw_request.refresh_from_db()
            self.assertEqual(withdraw_request.status, WithdrawRequest.STATUS.new)
