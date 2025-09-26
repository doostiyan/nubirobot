import uuid
from unittest.mock import patch

import pytest
import responses
from django.test import TestCase, override_settings
from responses import matchers

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import FeatureUnavailable, InternalAPIError
from exchange.asset_backed_credit.externals.restriction import (
    UserRemoveRestrictionAPI,
    UserRemoveRestrictionRequest,
    UserRestrictionType,
)
from exchange.base.models import Settings
from tests.asset_backed_credit.helper import INTERNAL_TEST_JWT_TOKEN, ABCMixins


class UserRemoveRestrictionAPITest(TestCase, ABCMixins):
    def setUp(self):
        self.user = User.objects.get(id=201)
        self.url = UserRemoveRestrictionAPI.url % self.user.uid
        self.restriction = UserRestrictionType.CHANGE_MOBILE.value
        self.user_service = self.create_user_service(user=self.user)
        Settings.set('abc_use_restriction_internal_api', 'yes')

    @responses.activate
    def test_remove_user_restriction_successfully(self):
        responses.post(
            url=self.url,
            json={},
            status=200,
            match=[
                matchers.json_params_matcher(
                    {
                        'refId': 12,
                        'restriction': 'ChangeMobile',
                    },
                )
            ],
        )

        UserRemoveRestrictionAPI().request(
            user_id=self.user.uid,
            data=UserRemoveRestrictionRequest(restriction=UserRestrictionType.CHANGE_MOBILE, ref_id=12),
            idempotency=self.user_service.external_id,
        )

    @override_settings(
        ABC_AUTHENTICATION_INTERNAL_USER_ENABLED=True,
        ABC_INTERNAL_API_JWT_TOKEN=INTERNAL_TEST_JWT_TOKEN,
    )
    @responses.activate
    @patch('rest_framework.authentication.TokenAuthentication.authenticate')
    def test_remove_user_restriction_of_not_existing_user(self, mock_authenticate):
        mock_authenticate.return_value = (self.user, None)
        responses.post(
            url=self.url,
            json={},
            status=200,
            match=[
                matchers.json_params_matcher(
                    {
                        'refId': self.user_service.id,
                        'restriction': 'ChangeMobile',
                    },
                )
            ],
        )

        with pytest.raises(InternalAPIError):
            UserRemoveRestrictionAPI().request(
                user_id=uuid.uuid4(),
                data=UserRemoveRestrictionRequest(
                    restriction=UserRestrictionType.CHANGE_MOBILE, ref_id=self.user_service.id
                ),
                idempotency=self.user_service.external_id,
            )

    def test_remove_user_restriction_when_feature_flag_is_not_enabled_raises_error(self):
        Settings.set('abc_use_restriction_internal_api', 'no')
        with pytest.raises(FeatureUnavailable):
            UserRemoveRestrictionAPI().request(
                user_id=uuid.uuid4(),
                data=UserRemoveRestrictionRequest(
                    restriction=UserRestrictionType.CHANGE_MOBILE, ref_id=self.user_service.id
                ),
                idempotency=self.user_service.external_id,
            )
