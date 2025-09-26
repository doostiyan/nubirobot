from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase, TransactionTestCase
from django.test.utils import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from exchange.accounts.custom_signals import ACCOUNT_USER_TYPE_CHANGED
from exchange.accounts.models import (
    BankAccount,
    Tag,
    UpgradeLevel3Request,
    User,
    UserLevelChangeHistory,
    UserTag,
    VerificationRequest,
)
from exchange.accounts.userlevels import UserLevelManager
from exchange.base.models import Currencies, Settings
from exchange.settings import NOBITEX_OPTIONS
from exchange.shetab.models import ShetabDeposit
from exchange.wallet.estimator import PriceEstimator
from exchange.wallet.models import BankDeposit, Transaction, Wallet, WithdrawRequest, WithdrawRequestLimit
from tests.base.utils import (
    TransactionTestFastFlushMixin,
    check_nobitex_response,
    create_withdraw_request,
    make_user_upgradable_to_level3,
    set_feature_status,
)


class UserLevelsTest(TestCase):
    def reverse_data(self):
        cache.set('orderbook_BTCIRT_best_active_buy', None)
        self.user.user_type = self.old_user_type
        self.user.save()

        self.wallet.balance = self.old_balance
        self.wallet.save()

    def setUp(self):
        self.user = User.objects.get(pk=201)
        Wallet.create_user_wallets(self.user)
        self.client = Client()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        bitcoin_price = Decimal(997_000_000_0)
        cache.set('orderbook_BTCIRT_best_active_buy', bitcoin_price)

        self.old_user_type = self.user.user_type
        self.user.user_type = User.USER_TYPES.verified  # level3
        self.user.save()

        self.wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        self.old_balance = self.wallet.balance
        self.wallet.balance = 10
        self.wallet.save()

        self.addCleanup(self.reverse_data)

    def test_is_eligible_to_withdraw_daily_coin(self):
        my_nobitex_option = NOBITEX_OPTIONS
        my_nobitex_option['withdrawLimits'][90] = {'dailyCoin': Decimal('1_000_000_000_0'),
                                                   'dailyRial': Decimal('1_000_000_000_0'),
                                                   'dailySummation': Decimal('1_000_000_000_0'),
                                                   'monthlySummation': Decimal('15_000_000_000_0')}

        with override_settings(NOBITEX_OPTIONS=my_nobitex_option):
            assert self.user.user_type == User.USER_TYPES.verified
            assert not UserLevelManager.is_eligible_to_withdraw(self.user, Currencies.btc, Decimal('1.5'))
            assert UserLevelManager.is_eligible_to_withdraw(self.user, Currencies.btc, 1)
            assert PriceEstimator.get_rial_value_by_best_price(2, Currencies.btc, 'buy') == 1_994_000_000_0

            withdraw_request = WithdrawRequest.objects.create(
                wallet=self.wallet,
                amount=Decimal('1.5'),
            )
            self.addCleanup(withdraw_request.delete)
            assert withdraw_request.id
            assert withdraw_request.rial_value
            response = self.client.post('/users/wallets/withdraw-confirm', data={
                'withdraw': withdraw_request.id,
                'otp': withdraw_request.otp,
            }).json()
            assert response['status'] == 'failed'
            assert response['message'] == 'WithdrawAmountLimitation'

            withdraw_request1 = WithdrawRequest.objects.create(
                wallet=self.wallet,
                amount=1,
            )
            response1 = self.client.post('/users/wallets/withdraw-confirm', data={
                'withdraw': withdraw_request1.id,
                'otp': withdraw_request1.otp,
            }).json()
            assert response1['status'] == 'ok'
            withdraw_request1.delete()

            # -----------------------------------------------1-------------------------
            withdraw_request2 = WithdrawRequest.objects.create(
                wallet=self.wallet,
                amount=Decimal('0.2'),
            )
            self.addCleanup(withdraw_request2.delete)
            response2 = self.client.post('/users/wallets/withdraw-confirm', data={
                'withdraw': withdraw_request2.id,
                'otp': withdraw_request2.otp,
            }).json()
            assert response2['status'] == 'ok'

            # -----------------------------------------------2-------------------------
            withdraw_request3 = WithdrawRequest.objects.create(
                wallet=self.wallet,
                amount=Decimal('0.2'),
            )
            self.addCleanup(withdraw_request3.delete)
            response3 = self.client.post('/users/wallets/withdraw-confirm', data={
                'withdraw': withdraw_request3.id,
                'otp': withdraw_request3.otp,
            }).json()
            assert response3['status'] == 'ok'

            # -----------------------------------------------3-------------------------
            withdraw_request4 = WithdrawRequest.objects.create(
                wallet=self.wallet,
                amount=Decimal('0.2'),
            )
            self.addCleanup(withdraw_request4.delete)
            response4 = self.client.post('/users/wallets/withdraw-confirm', data={
                'withdraw': withdraw_request4.id,
                'otp': withdraw_request4.otp,
            }).json()
            assert response4['status'] == 'ok'

            # -----------------------------------------------4-------------------------
            withdraw_request5 = WithdrawRequest.objects.create(
                wallet=self.wallet,
                amount=Decimal('0.2'),
            )
            self.addCleanup(withdraw_request5.delete)
            response5 = self.client.post('/users/wallets/withdraw-confirm', data={
                'withdraw': withdraw_request5.id,
                'otp': withdraw_request5.otp,
            }).json()
            assert response5['status'] == 'ok'

            # -----------------------------------------------5-------------------------
            withdraw_request6 = WithdrawRequest.objects.create(
                wallet=self.wallet,
                amount=Decimal('0.2'),
            )
            self.addCleanup(withdraw_request6.delete)
            response6 = self.client.post('/users/wallets/withdraw-confirm', data={
                'withdraw': withdraw_request6.id,
                'otp': withdraw_request6.otp,
            }).json()
            assert response6['status'] == 'ok'

            # -----------------------------------------------6-------------------------
            withdraw_request7 = WithdrawRequest.objects.create(
                wallet=self.wallet,
                amount=Decimal('0.2'),
            )
            self.addCleanup(withdraw_request7.delete)
            response7 = self.client.post('/users/wallets/withdraw-confirm', data={
                'withdraw': withdraw_request7.id,
                'otp': withdraw_request7.otp,
            }).json()
            assert response7['status'] == 'failed'
            assert response7['message'] == 'WithdrawAmountLimitation'

            cache.set('orderbook_BTCIRT_best_active_buy', None)
            PriceEstimator.get_price_range.clear()

            withdraw_request8 = WithdrawRequest.objects.create(
                wallet=self.wallet,
                amount=1,
            )
            self.addCleanup(withdraw_request8.delete)
            response8 = self.client.post('/users/wallets/withdraw-confirm', data={
                'withdraw': withdraw_request8.id,
                'otp': withdraw_request8.otp,
            }).json()
            assert response8['status'] == 'ok'

    def test_is_eligible_to_withdraw_special_limit(self):
        PriceEstimator.get_price_range.clear()
        assert self.user.user_type == User.USER_TYPES.verified
        assert not UserLevelManager.is_eligible_to_withdraw(self.user, Currencies.btc, Decimal('1.5'), 'BSC')
        assert UserLevelManager.is_eligible_to_withdraw(self.user, Currencies.btc, 1, 'BSC')

        withdraw_limit = WithdrawRequestLimit.objects.create(
            user=self.user,
            tp=WithdrawRequestLimit.LIMITATION_TYPE.daily_coin,
            limitation=0.5,
            currency=Currencies.btc,
            network='BSC'
        )
        self.addCleanup(withdraw_limit.delete)
        assert not UserLevelManager.is_eligible_to_withdraw(self.user, Currencies.btc, 1, 'BSC')

        # check other networks
        assert UserLevelManager.is_eligible_to_withdraw(self.user, Currencies.btc, 1)

    def test_is_eligible_to_bank_id_deposit(self):
        # eligible all users except who having a specific tag (استعلام)

        # Above level2
        assert self.user.user_type == User.USER_TYPES.verified
        assert UserLevelManager.is_eligible_to_bank_id_deposit(self.user)

        # Level1
        self.user.user_type = User.USER_TYPES.level1
        assert UserLevelManager.is_eligible_to_bank_id_deposit(self.user)

        # Level2
        self.user.user_type = User.USER_TYPES.level2
        assert UserLevelManager.is_eligible_to_bank_id_deposit(self.user)

        # Below level2
        self.user.user_type = User.USER_TYPES.trader
        assert UserLevelManager.is_eligible_to_bank_id_deposit(self.user)

        # With Tag
        tag = Tag.objects.create(name='استعلام')
        UserTag.objects.create(user=self.user, tag=tag)
        assert not UserLevelManager.is_eligible_to_bank_id_deposit(self.user)

    def test_is_eligible_to_change_mobile(self):
        # > level3
        not_eligible_levels = ['active', 'trusted', 'nobitex', 'system', 'bot', 'staff']
        for level in not_eligible_levels:
            self.user.user_type = User.USER_TYPES._identifier_map[level]
            assert not UserLevelManager.is_eligible_to_change_mobile(self.user)

        # <= level3
        eligible_levels = User.USER_TYPES._identifier_map.keys() - not_eligible_levels
        for level in eligible_levels:
            self.user.user_type = User.USER_TYPES._identifier_map[level]
            assert UserLevelManager.is_eligible_to_change_mobile(self.user)

    def test_is_eligible_to_withdraw_with_variety_network(self):
        assert self.user.user_type == User.USER_TYPES.verified
        assert not UserLevelManager.is_eligible_to_withdraw(self.user, Currencies.btc, Decimal('1.5'), 'BSC')
        assert not UserLevelManager.is_eligible_to_withdraw(self.user, Currencies.btc, Decimal('1.5'), 'BTC')
        assert UserLevelManager.is_eligible_to_withdraw(self.user, Currencies.btc, Decimal('1'), 'BSC')
        assert UserLevelManager.is_eligible_to_withdraw(self.user, Currencies.btc, Decimal('1'), 'BTC')

        WithdrawRequestLimit.objects.create(
            user=self.user,
            tp=WithdrawRequestLimit.LIMITATION_TYPE.daily_currency,
            limitation=0.5,
            currency=Currencies.btc,
            network='BSC',
        )
        WithdrawRequestLimit.objects.create(
            user=self.user,
            tp=WithdrawRequestLimit.LIMITATION_TYPE.daily_currency,
            limitation=0.3,
            currency=Currencies.btc,
            network='BTC',
        )
        create_withdraw_request(
            user=self.user,
            currency=Currencies.btc,
            address='UQC5uTmBRojmKMGaliGNbENM3XKv_hX2L60cT09oYG3zW',
            amount=Decimal('0.4'),
            network='BSC',
            status=WithdrawRequest.STATUS.verified,
        )
        create_withdraw_request(
            user=self.user,
            currency=Currencies.btc,
            address='UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2fTkafy3zW',
            amount=Decimal('0.1'),
            network='BTC',
            status=WithdrawRequest.STATUS.verified,
        )
        assert not UserLevelManager.is_eligible_to_withdraw(self.user, Currencies.btc, Decimal('0.2'), 'BSC')
        assert UserLevelManager.is_eligible_to_withdraw(self.user, Currencies.btc, Decimal('0.1'), 'BSC')
        assert not UserLevelManager.is_eligible_to_withdraw(self.user, Currencies.btc, Decimal('0.3'), 'BTC')
        assert UserLevelManager.is_eligible_to_withdraw(self.user, Currencies.btc, Decimal('0.2'), 'BTC')

    def test_is_eligible_to_withdraw_with_none_network(self):
        assert self.user.user_type == User.USER_TYPES.verified

        WithdrawRequestLimit.objects.create(
            user=self.user,
            tp=WithdrawRequestLimit.LIMITATION_TYPE.daily_currency,
            limitation=0.5,
            currency=Currencies.btc,
            network='BSC',
        )
        WithdrawRequestLimit.objects.create(
            user=self.user,
            tp=WithdrawRequestLimit.LIMITATION_TYPE.daily_currency,
            limitation=0.9,
            currency=Currencies.btc,
            network=None,
        )
        create_withdraw_request(
            user=self.user,
            currency=Currencies.btc,
            address='UQC5uTmBRojmKMGaliGNbENM3XKv_hX2L60cT09oYG3zW',
            amount=Decimal('0.4'),
            network='BSC',
            status=WithdrawRequest.STATUS.verified,
        )
        create_withdraw_request(
            user=self.user,
            currency=Currencies.btc,
            address='UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2fTkafy3zW',
            amount=Decimal('0.1'),
            network='BTC',
            status=WithdrawRequest.STATUS.verified,
        )
        assert not UserLevelManager.is_eligible_to_withdraw(self.user, Currencies.btc, Decimal('0.2'), 'BSC')
        assert UserLevelManager.is_eligible_to_withdraw(self.user, Currencies.btc, Decimal('0.1'), 'BSC')
        assert not UserLevelManager.is_eligible_to_withdraw(self.user, Currencies.btc, Decimal('0.5'), 'BTC')
        # 0.9 is limitation - (0.4 + 0.1) previous withdraws = 0.5
        assert UserLevelManager.is_eligible_to_withdraw(self.user, Currencies.btc, Decimal('0.4'), 'BTC')


class TestUserLevelEvents(TransactionTestFastFlushMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create(
            username='TestUserLevelEvents@nobitex.ir',
            email='TestUserLevelEvents@nobitex.ir',
            password='!',
            first_name='test',
            last_name='test',
            user_type=User.USER_TYPES.level0,
        )

    @patch.object(ACCOUNT_USER_TYPE_CHANGED, 'send')
    def test_user_type_change(self, patch_event):
        assert self.user.user_type == User.USER_TYPES.level0
        self.user.address = 'test'
        self.user.save()
        patch_event.assert_not_called()

        self.user.user_type = User.USER_TYPES.level1
        self.user.save()
        patch_event.assert_called_with(
            sender=self.user.__class__,
            user=self.user,
            previous_type=User.USER_TYPES.level0,
            current_type=User.USER_TYPES.level1
        )


class TestUpdateVerificationStatus(APITestCase):
    def setUp(self) -> None:
        cache.clear()
        set_feature_status("kyc2", True)
        self.user = User.objects.get(pk=201)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        self.vp = self.user.get_verification_profile()
        self.vp.email_confirmed = True
        self.vp.save()
        self.url = '/users/upgrade/level3'

    def _send_upgrade_request(self):
        return self.client.post(self.url).json()

    def tearDown(self) -> None:
        BankDeposit.objects.all().delete()
        Transaction.objects.all().delete()
        WithdrawRequest.objects.all().delete()
        VerificationRequest.objects.all().delete()

    def _prepare_user_information_for(self, level):
        self.vp.mobile_confirmed = True
        if level == User.USER_TYPES.level0:
            self.vp.save()
            return

        self.vp.identity_confirmed = True
        if level == User.USER_TYPES.level1:
            self.vp.save()
            return

        self.user.update_verification_status()
        self.user.city = 'test'
        self.user.address = 'test st'
        self.user.save()
        self.vp.selfie_confirmed = True
        self.vp.address_confirmed = True
        if level == User.USER_TYPES.level2:
            self.vp.save()
            return

    def _test_user_type(self, level: User.USER_TYPES) -> None:
        self.user.refresh_from_db()
        self.user.update_verification_status()
        assert self.user.user_type == level

    def test_level1(self):
        assert self.user.user_type == User.USER_TYPES.level0

        self._prepare_user_information_for(User.USER_TYPES.level1)
        self._test_user_type(User.USER_TYPES.level1)

        self.vp.email_confirmed = False
        self.vp.save()
        self._test_user_type(User.USER_TYPES.level1)

        self.vp.mobile_identity_confirmed = True
        self.vp.save()
        self._test_user_type(User.USER_TYPES.level1)

        self.vp.email_confirmed = True
        self.vp.save()
        self._test_user_type(User.USER_TYPES.level1)

    def test_level2(self):
        assert self.user.user_type == User.USER_TYPES.level0

        self._prepare_user_information_for(User.USER_TYPES.level1)
        self._test_user_type(User.USER_TYPES.level1)

        self.user.city = 'test'
        self.user.save()
        self._test_user_type(User.USER_TYPES.level1)

        self.user.address = 'test st'
        self.user.save()
        self._test_user_type(User.USER_TYPES.level1)

        self.vp.address_confirmed = True
        self.vp.save()
        self._test_user_type(User.USER_TYPES.level1)

        self.vp.selfie_confirmed = True
        self.vp.save()
        self._test_user_type(User.USER_TYPES.level2)

        self.vp.identity_liveness_confirmed = True
        self.vp.selfie_confirmed = False
        self.vp.save()
        self._test_user_type(User.USER_TYPES.level2)

    def test_level3_mobile_identity_fail(self):
        assert self.user.user_type == User.USER_TYPES.level0

        self._prepare_user_information_for(User.USER_TYPES.level2)
        self._test_user_type(User.USER_TYPES.level2)
        make_user_upgradable_to_level3(self.user, mobile_identity=False)

        r = self._send_upgrade_request()
        check_nobitex_response(r, 'failed', 'NotMobileIdentityConfirmed', 'User is not eligible to upgrade level3')

        self._test_user_type(User.USER_TYPES.level2)

    def test_level3_min_days_not_passed_fail(self):
        assert self.user.user_type == User.USER_TYPES.level0

        self._prepare_user_information_for(User.USER_TYPES.level2)
        self._test_user_type(User.USER_TYPES.level2)
        make_user_upgradable_to_level3(self.user, use_day_limitation=False)

        r = self._send_upgrade_request()
        check_nobitex_response(r, 'failed', 'DaysLimitationViolated', 'User is not eligible to upgrade level3')

        self._test_user_type(User.USER_TYPES.level2)

    def test_level3_trades_less_than_limitation_fail(self):
        assert self.user.user_type == User.USER_TYPES.level0

        self._prepare_user_information_for(User.USER_TYPES.level2)
        self._test_user_type(User.USER_TYPES.level2)
        make_user_upgradable_to_level3(self.user, add_trades=False)

        r = self._send_upgrade_request()
        check_nobitex_response(r, 'failed', 'InsufficientTrades', 'User is not eligible to upgrade level3')

        self._test_user_type(User.USER_TYPES.level2)

    def test_level3_success(self):
        assert self.user.user_type == User.USER_TYPES.level0

        self._prepare_user_information_for(User.USER_TYPES.level2)
        self._test_user_type(User.USER_TYPES.level2)

        make_user_upgradable_to_level3(self.user)
        self._send_upgrade_request()

        _request = UpgradeLevel3Request.objects.filter(
            user=self.user,
            status=UpgradeLevel3Request.STATUS.pre_conditions_approved,
        ).first()
        assert _request
        assert not _request.closed_at

        _request.approve()
        assert _request.status == UpgradeLevel3Request.STATUS.approved
        assert _request.closed_at


class TestEmailOnUserTypeChange(TransactionTestFastFlushMixin, TransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create(
            username='TestEmailOnUserTypeChange@nobitex.ir',
            email='TestEmailOnUserTypeChange@nobitex.ir',
            password='!',
            first_name='test',
            last_name='test',
            user_type=User.USER_TYPES.level0,
        )
        self.vp = self.user.get_verification_profile()
        self.vp.email_confirmed = True
        self.vp.save()
        set_feature_status('kyc2', True)

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'critical': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_send_email_on_user_type_change(self):
        Settings.set_dict('email_whitelist', [self.user.email])
        call_command('update_email_templates')

        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        with patch('django.db.connection.close'):
            call_command('send_queued_mail')


class TestUserTypeChangeHistory(TransactionTestFastFlushMixin, TransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create(
            username='TestUserTypeChangeHistory@nobitex.ir',
            email='TestUserTypeChangeHistory@nobitex.ir',
            password='!',
            first_name='test',
            last_name='test',
            user_type=User.USER_TYPES.level0,
        )
        self.vp = self.user.get_verification_profile()
        self.vp.email_confirmed = True
        self.vp.save()

    def test_user_type_changed_log(self):
        assert self.user.user_type == User.USER_TYPES.level0
        assert not self.user.user_type_histories.all()

        self.user.user_type = User.USER_TYPES.level1
        self.user.save()

        assert self.user.user_type == User.USER_TYPES.level1
        assert self.user.user_type_histories.all()

        _log: UserLevelChangeHistory = self.user.user_type_histories.first()
        assert _log.from_level == User.USER_TYPES.level0
        assert _log.to_level == User.USER_TYPES.level1

    def test_user_type_downgrade_log(self):
        self.user.user_type = User.USER_TYPES.level1
        self.user.save()

        assert self.user.user_type == User.USER_TYPES.level1
        assert self.user.user_type_histories.all()

        _log: UserLevelChangeHistory = self.user.user_type_histories.first()
        assert _log.from_level == User.USER_TYPES.level0
        assert _log.to_level == User.USER_TYPES.level1

        # downgrade user
        self.user.user_type = User.USER_TYPES.level0
        self.user.save()

        assert self.user.user_type == User.USER_TYPES.level0
        assert self.user.user_type_histories.all()

        _log: UserLevelChangeHistory = self.user.user_type_histories.first()
        assert _log.from_level == User.USER_TYPES.level1
        assert _log.to_level == User.USER_TYPES.level0
