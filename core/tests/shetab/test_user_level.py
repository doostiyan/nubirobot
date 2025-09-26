import datetime

from rest_framework.test import APITestCase

from exchange.accounts.models import BankCard, User, VerificationProfile
from exchange.base.calendar import ir_now
from exchange.shetab.models import ShetabDeposit


class TestUserLevelEffectOnShetabDeposit(APITestCase):
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

    def request_and_assert_failed(self, amount, code):
        resp = self.client.post(self.URL, dict(amount=amount, selectedCard=self.bank_card.id))
        assert resp.status_code == 200
        result = resp.json()
        assert result['status'] == 'failed'
        assert result['message'] == 'RialDepositLimitation'
        assert result['code'] == code

    def request_and_assert_not_failed(self, amount):
        resp = self.client.post(self.URL, dict(amount=amount, selectedCard=self.bank_card.id))
        assert resp.status_code == 200
        result = resp.json()
        assert result['status'] == 'ok'

    def test_create_deposit_level2_no_identified_mobile(self):
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(
            mobile_identity_confirmed=False)

        self.request_and_assert_failed(26_000_000_0, 'Amount Level Limitation')
        self.request_and_assert_not_failed(8_000_000_0)

        ShetabDeposit.objects.create(user=self.user, amount=2_000_000_0, status_code=ShetabDeposit.STATUS.pay_success)
        self.request_and_assert_failed(16_000_000_0, 'Amount Daily Limitation')
        self.request_and_assert_not_failed(10_000_000_0)

    def test_create_deposit_level2_with_identified_mobile(self):
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(
            mobile_identity_confirmed=True)

        self.request_and_assert_not_failed(6_000_000_0)
        self.request_and_assert_failed(26_000_000_0, 'Amount Level Limitation')

        ShetabDeposit.objects.create(user=self.user, amount=15_000_000_0, status_code=ShetabDeposit.STATUS.pay_success)
        self.request_and_assert_failed(5_000_000_0, 'Amount Daily Limitation')
        self.request_and_assert_not_failed(3_000_000_0)

    def test_create_deposit_level1_to_level2(self):
        self.user.user_type = User.USER_TYPES.level1
        self.user.save()
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(
            mobile_identity_confirmed=False)

        self.request_and_assert_failed(26_000_000_0, 'Amount Level Limitation')
        self.request_and_assert_not_failed(15_000_000_0)

        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        self.request_and_assert_failed(26_000_000_0, 'Amount Level Limitation')

        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(
            mobile_identity_confirmed=True)

        self.request_and_assert_failed(26_000_000_0, 'Amount Level Limitation')
        self.request_and_assert_failed(24_000_000_0, 'Amount Daily Limitation')
        self.request_and_assert_not_failed(10_000_000_0)

    def test_shetab_deposit_daily_limitation_for_level1_to_level2(self):
        self.user.user_type = User.USER_TYPES.level1
        self.user.save()
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(
            mobile_identity_confirmed=False,
        )

        create_date_time = ir_now().replace(hour=0, minute=0, second=0, microsecond=0)
        deposit = ShetabDeposit.objects.create(
            user=self.user,
            amount=20_000_000_0,
            status_code=ShetabDeposit.STATUS.pay_success,
        )
        deposit.created_at = create_date_time - datetime.timedelta(minutes=10)
        deposit.save(update_fields=['created_at'])
        self.request_and_assert_not_failed(20_000_000_0)

        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(
            mobile_identity_confirmed=False,
        )
        deposit = ShetabDeposit.objects.create(
            user=self.user,
            amount=5_000_000_0,
            status_code=ShetabDeposit.STATUS.pay_success,
        )
        deposit.created_at = create_date_time - datetime.timedelta(minutes=3)
        deposit.save(update_fields=['created_at'])
        self.request_and_assert_not_failed(5_000_000_0)
        self.request_and_assert_failed(500_000_0, 'Amount Daily Limitation')

    def test_create_deposit_level3(self):
        self.user.user_type = User.USER_TYPES.verified
        self.user.save()
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(
            mobile_identity_confirmed=False
        )

        self.request_and_assert_failed(26_000_000_0, 'Amount Level Limitation')
        self.request_and_assert_not_failed(24_000_000_0)

        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(
            mobile_identity_confirmed=True
        )

        self.request_and_assert_failed(26_000_000_0, 'Amount Level Limitation')
        self.request_and_assert_failed(25_000_000_0, 'Amount Daily Limitation')
        self.request_and_assert_not_failed(1_000_000_0)

    def test_create_deposit_trader(self):
        self.user.user_type = User.USER_TYPES.trader
        self.user.save()
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(
            mobile_identity_confirmed=False
        )

        self.request_and_assert_failed(26_000_000_0, 'Amount Level Limitation')
        self.request_and_assert_not_failed(24_000_000_0)

        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(
            mobile_identity_confirmed=True
        )

        self.request_and_assert_failed(26_000_000_0, 'Amount Level Limitation')
        self.request_and_assert_failed(25_000_000_0, 'Amount Daily Limitation')
        self.request_and_assert_not_failed(1_000_000_0)
