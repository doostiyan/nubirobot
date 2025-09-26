from typing import Optional

from django.http import HttpResponse
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User, UserOTP


class TestTfaAPI(APITestCase):
    URL_REQUEST = '/users/tfa/request'

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def _change_parameters_in_object(self, obj, update_fields: dict):
        obj.__dict__.update(**update_fields)
        obj.save()

    def _check_response(
        self,
        response: HttpResponse,
        status_code: int,
        status_data: Optional[str] = None,
        code: Optional[str] = None,
        message: Optional[str] = None,
    ):
        assert response.status_code == status_code
        data = response.json()
        if status_data:
            assert data['status'] == status_data
        if code:
            assert data['code'] == code
        if message:
            assert data['message'] == message
        return data

    def test_tfa_request_user_has_not_email(self):
        self._change_parameters_in_object(
            self.user,
            {'email': None},
        )
        self._change_parameters_in_object(
            self.user.get_verification_profile(),
            {'email_confirmed': False},
        )
        response = self.client.post(path=self.URL_REQUEST)
        self._check_response(
            response,
            status.HTTP_400_BAD_REQUEST,
            'failed',
            'UnverifiedEmail',
            'User does not have a verified email.',
        )

    def test_tfa_request_user_has_not_mobile(self):
        self._change_parameters_in_object(
            self.user,
            {'mobile': None, 'email': 'x@gmail.com'},
        )
        self._change_parameters_in_object(
            self.user.get_verification_profile(),
            {'email_confirmed': True, 'mobile_confirmed': False},
        )
        response = self.client.post(path=self.URL_REQUEST)
        self._check_response(
            response,
            status.HTTP_200_OK,
            'failed',
            'UnverifiedMobile',
            'You must have a mobile phone and a verified email to enable tfa.',
        )

    def test_tfa_request_ok(self):
        self._change_parameters_in_object(
            self.user,
            {'mobile': '09121111111', 'email': 'x@gmail.com'},
        )
        self._change_parameters_in_object(
            self.user.get_verification_profile(),
            {'email_confirmed': True, 'mobile_confirmed': True},
        )
        response = self.client.post(path=self.URL_REQUEST)
        result = self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        assert 'device' in result


class TestCreateOTP(TestCase):
    def setUp(self):
        self.user, _ = User.objects.get_or_create(username='john.doe')

    def test_get_or_create_otp(self):
        otp = UserOTP.get_or_create_otp(
            tp=UserOTP.OTP_TYPES.mobile,
            user=self.user,
            usage=UserOTP.OTP_Usage.grant_permission_to_financial_service,
        )

        assert otp.otp_type == UserOTP.OTP_TYPES.mobile
        assert otp.otp_usage == UserOTP.OTP_Usage.grant_permission_to_financial_service

        another_otp = UserOTP.get_or_create_otp(
            tp=UserOTP.OTP_TYPES.mobile,
            user=self.user,
            usage=UserOTP.OTP_Usage.grant_permission_to_financial_service,
        )

        assert otp.code == another_otp.code

        otp.mark_as_used()

        another_otp = UserOTP.get_or_create_otp(
            tp=UserOTP.OTP_TYPES.mobile,
            user=self.user,
            usage=UserOTP.OTP_Usage.grant_permission_to_financial_service,
        )

        assert otp.code != another_otp.code
