from django.test import TestCase

from exchange.accounts.models import VerificationProfile
from exchange.asset_backed_credit.models import InternalUser
from exchange.asset_backed_credit.services.user import is_user_mobile_identity_confirmed, is_user_verified_level_one
from exchange.base.models import Settings
from tests.asset_backed_credit.helper import ABCMixins


class UserProviderTest(TestCase, ABCMixins):
    def setUp(self):
        self.verified_user = self.create_user()
        VerificationProfile.objects.filter(user=self.verified_user).update(
            email_confirmed=True,
            mobile_confirmed=True,
            identity_confirmed=True,
            phone_confirmed=True,
            address_confirmed=True,
            bank_account_confirmed=True,
            mobile_identity_confirmed=True,
        )
        self.verified_user.refresh_from_db()
        self.unverified_user = self.create_user()
        VerificationProfile.objects.filter(user=self.unverified_user).update(
            email_confirmed=False,
            mobile_confirmed=False,
            identity_confirmed=False,
            phone_confirmed=False,
            address_confirmed=False,
            bank_account_confirmed=False,
            mobile_identity_confirmed=False,
        )
        self.unverified_user.refresh_from_db()

    def test_user_level_one_when_user_has_level_one(self):
        has_level1 = is_user_verified_level_one(self.verified_user)
        assert has_level1

    def test_user_mobile_identity_confirmed_when_user_has_mobile_identity_confirmed(self):
        is_mobile_verified = is_user_mobile_identity_confirmed(self.verified_user)
        assert is_mobile_verified

    def test_user_level_one_when_user_level_one_is_not_verified(self):
        has_level1 = is_user_verified_level_one(self.unverified_user)
        assert has_level1 == False

    def test_user_mobile_identity_confirmed_when_user_mobile_identity_is_not_verified(self):
        is_mobile_verified = is_user_mobile_identity_confirmed(self.unverified_user)
        assert is_mobile_verified == False

    def test_user_level_one_verification_when_internal_eligibility_is_enabled_and_internal_user_exists_with_unverified_level_one(
        self,
    ):
        Settings.set('abc_use_internal_user_eligibility', 'yes')
        user = self.create_user()
        InternalUser.create(user.uid, user_type=InternalUser.USER_TYPES.level0)

        has_level1 = is_user_verified_level_one(user)
        assert has_level1 == False

    def test_user_level_one_verification_when_internal_eligibility_is_enabled_and_internal_user_exists_with_verified_level_one(
        self,
    ):
        Settings.set('abc_use_internal_user_eligibility', 'yes')
        user = self.create_user()
        InternalUser.create(user.uid, user_type=InternalUser.USER_TYPES.level1)

        has_level1 = is_user_verified_level_one(user)
        assert has_level1 == True

    def test_user_level_one_verification_when_internal_eligibility_is_enabled_and_internal_user_exists_with_higher_level(
        self,
    ):
        Settings.set('abc_use_internal_user_eligibility', 'yes')
        user = self.create_user()
        InternalUser.create(user.uid, user_type=InternalUser.USER_TYPES.trusted)

        has_level1 = is_user_verified_level_one(user)
        assert has_level1 == True

    def test_user_mobile_identity_confirmed_when_internal_eligibility_is_enabled_and_internal_user_exists_with_unverified_mobile_identity(
        self,
    ):
        Settings.set('abc_use_internal_user_eligibility', 'yes')
        user = self.create_user()
        InternalUser.create(user.uid, mobile_identity_confirmed=False)

        is_mobile_verified = is_user_mobile_identity_confirmed(user)
        assert is_mobile_verified == False

    def test_user_mobile_identity_confirmed_when_internal_eligibility_is_enabled_and_internal_user_exists_with_verified_mobile_identity(
        self,
    ):
        Settings.set('abc_use_internal_user_eligibility', 'yes')
        user = self.create_user()
        InternalUser.create(user.uid, mobile_identity_confirmed=True)

        is_mobile_verified = is_user_mobile_identity_confirmed(user)
        assert is_mobile_verified == True
