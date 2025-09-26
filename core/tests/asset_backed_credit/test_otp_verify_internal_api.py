from uuid import uuid4

import pytest
import responses
from django.test import TestCase
from responses import matchers
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import FeatureUnavailable, InternalAPIError
from exchange.asset_backed_credit.externals.base import NOBITEX_BASE_URL
from exchange.asset_backed_credit.externals.otp import InternalOTPType, InternalOTPUsage, VerifyOTPAPI, VerifyOTPRequest
from exchange.base.models import Settings


class VerifyOTPIternalAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.get(id=201)
        self.internal_api_success_response = {}
        self.data = VerifyOTPRequest(
            otp_code='123456',
            otp_type=InternalOTPType.MOBILE,
            otp_usage=InternalOTPUsage.GRANT_PERMISSION_TO_FINANCIAL_SERVICE,
        )
        self.idempotency = uuid4()
        self.url = f'{NOBITEX_BASE_URL}/internal/users/{self.user.uid}/verify-otp'
        Settings.set('abc_use_verify_otp_internal_api', 'yes')

    @responses.activate
    def test_verify_otp_success(self):
        responses.post(
            url=self.url,
            json=self.internal_api_success_response,
            status=status.HTTP_200_OK,
            match=[
                matchers.json_params_matcher(
                    {
                        'otpCode': '123456',
                        'otpType': InternalOTPType.MOBILE.value,
                        'otpUsage': InternalOTPUsage.GRANT_PERMISSION_TO_FINANCIAL_SERVICE.value,
                    },
                )
            ],
        )
        response = VerifyOTPAPI().request(self.user.uid, self.data, self.idempotency)
        assert response.status_code == status.HTTP_200_OK

    @responses.activate
    def test_verify_otp_with_feature_not_being_enabled(self):
        Settings.set('abc_use_verify_otp_internal_api', 'no')
        responses.post(
            url=self.url,
            json=self.internal_api_success_response,
            status=status.HTTP_200_OK,
        )
        with pytest.raises(FeatureUnavailable):
            VerifyOTPAPI().request(self.user.uid, self.data, self.idempotency)

    @responses.activate
    def test_verify_otp_with_internal_api_raises_error(self):
        responses.post(
            url=self.url,
            status=status.HTTP_400_BAD_REQUEST,
        )
        with pytest.raises(InternalAPIError):
            VerifyOTPAPI().request(self.user.uid, self.data, self.idempotency)
