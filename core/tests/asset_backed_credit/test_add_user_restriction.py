import uuid
from unittest.mock import patch

import pytest
import responses
from django.test import TestCase, override_settings
from responses import matchers

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import FeatureUnavailable, InternalAPIError
from exchange.asset_backed_credit.externals.restriction import (
    UserAddRestrictionAPI,
    UserAddRestrictionRequest,
    UserRestrictionType,
)
from exchange.base.models import Settings
from tests.asset_backed_credit.helper import INTERNAL_TEST_JWT_TOKEN, ABCMixins


class UserAddRestrictionAPITest(TestCase, ABCMixins):
    def setUp(self):
        self.user = User.objects.get(id=201)
        self.url = UserAddRestrictionAPI.url % self.user.uid
        self.idempotency = uuid.uuid4()
        Settings.set('abc_use_restriction_internal_api', 'yes')

    @responses.activate
    def test_add_user_restriction_successfully(self):
        responses.post(
            url=self.url,
            json={},
            status=200,
            match=[
                matchers.json_params_matcher(
                    {
                        'considerations': None,
                        'description': None,
                        'durationHours': None,
                        'refId': 128,
                        'restriction': 'ChangeMobile',
                    }
                )
            ],
        )

        UserAddRestrictionAPI().request(
            user_id=self.user.uid,
            data=UserAddRestrictionRequest(restriction=UserRestrictionType.CHANGE_MOBILE, ref_id=128),
            idempotency=self.idempotency,
        )

    @responses.activate
    def test_add_user_restriction_with_full_restriction_data_successfully(self):
        responses.post(
            url=self.url,
            json={},
            status=200,
            match=[
                matchers.json_params_matcher(
                    {
                        'considerations': 'test consideration',
                        'description': 'ACTIVE_TARA_CREDIT',
                        'refId': 135,
                        'restriction': 'ChangeMobile',
                        'durationHours': 5,
                    }
                )
            ],
        )

        UserAddRestrictionAPI().request(
            user_id=self.user.uid,
            data=UserAddRestrictionRequest(
                restriction=UserRestrictionType.CHANGE_MOBILE,
                considerations='test consideration',
                description='ACTIVE_TARA_CREDIT',
                duration_hours=5,
                ref_id=135,
            ),
            idempotency=self.idempotency,
        )

    @responses.activate
    @override_settings(
        ABC_AUTHENTICATION_INTERNAL_USER_ENABLED=True,
        ABC_INTERNAL_API_JWT_TOKEN=INTERNAL_TEST_JWT_TOKEN,
    )
    @patch('rest_framework.authentication.TokenAuthentication.authenticate')
    def test_add_restriction_to_not_existing_user(self, mock_authenticate):
        mock_authenticate.return_value = (self.user, None)
        responses.post(
            url=self.url,
            json={},
            status=200,
            match=[
                matchers.json_params_matcher(
                    {
                        'considerations': 'test consideration 2',
                        'description': None,
                        'ACTIVE_TARA_CREDIT': None,
                        'refId': 794,
                        'restriction': 'ChangeMobile',
                        'durationHours': 15,
                    }
                )
            ],
        )

        with pytest.raises(InternalAPIError):
            UserAddRestrictionAPI().request(
                user_id=uuid.uuid4(),
                data=UserAddRestrictionRequest(
                    restriction=UserRestrictionType.CHANGE_MOBILE,
                    considerations='test consideration 2',
                    description='ACTIVE_TARA_CREDIT',
                    duration_hours=15,
                    ref_id=794,
                ),
                idempotency=self.idempotency,
            )

    def test_add_restriction_with_feature_not_being_enabled_raises_error(self):
        Settings.set('abc_use_restriction_internal_api', 'no')

        with pytest.raises(FeatureUnavailable):
            UserAddRestrictionAPI().request(
                user_id=self.user.uid,
                data=UserAddRestrictionRequest(restriction=UserRestrictionType.CHANGE_MOBILE, ref_id=1236),
                idempotency=self.idempotency,
            )
