from unittest.mock import MagicMock

from django.test import TestCase

from exchange.accounts.models import VerificationProfile
from exchange.asset_backed_credit.api.views import user_eligibility_api
from exchange.asset_backed_credit.models import InternalUser
from exchange.base.api import NobitexAPIError
from exchange.base.models import Settings
from tests.asset_backed_credit.helper import ABCMixins


class UserEligibilityDecoratorTests(TestCase, ABCMixins):
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

        self.mock_request_verified = MagicMock()
        self.mock_request_verified.user = self.verified_user

        self.mock_request_unverified = MagicMock()
        self.mock_request_unverified.user = self.unverified_user

        self.mock_view = MagicMock(return_value='view_response')

    def test_user_eligibility_success(self):
        decorated_view = user_eligibility_api(self.mock_view)
        response = decorated_view(self.mock_request_verified)
        assert response == 'view_response'

    def test_unverified_user_not_eligible(self):
        decorated_view = user_eligibility_api(self.mock_view)

        with self.assertRaises(NobitexAPIError) as context:
            decorated_view(self.mock_request_unverified)

        assert context.exception.status_code == 400
        assert context.exception.code == 'UserLevelRestriction'
        assert context.exception.description == 'User is not verified as level 1.'

    def test_when_internal_eligibility_is_enabled_and_internal_user_is_eligible(self):
        Settings.set('abc_use_internal_user_eligibility', 'yes')
        user = self.create_user()
        InternalUser.create(user.uid, user_type=InternalUser.USER_TYPES.level1, mobile_identity_confirmed=True)
        self.mock_request_verified.user = user

        decorated_view = user_eligibility_api(self.mock_view)
        response = decorated_view(self.mock_request_verified)
        assert response == 'view_response'

    def test_when_internal_eligibility_is_enabled_and_internal_user_is_not_eligible(self):
        Settings.set('abc_use_internal_user_eligibility', 'yes')
        user = self.create_user()
        InternalUser.create(user.uid, user_type=InternalUser.USER_TYPES.level1)
        self.mock_request_unverified.user = user

        decorated_view = user_eligibility_api(self.mock_view)

        with self.assertRaises(NobitexAPIError) as context:
            decorated_view(self.mock_request_unverified)

        assert context.exception.status_code == 400
        assert context.exception.code == 'UserLevelRestriction'
        assert context.exception.description == 'User has no confirmed mobile number.'
