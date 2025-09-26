from typing import Optional
from unittest.mock import patch

import pytest
import responses
from django.core.management import call_command
from django.http import HttpResponse
from django.test import override_settings
from rest_framework import status

from exchange.accounts.models import Notification, User, UserOTP, UserSms
from exchange.asset_backed_credit.externals.otp import VerifyOTPAPI
from exchange.asset_backed_credit.models import InternalUser, Service, UserFinancialServiceLimit, UserServicePermission
from exchange.asset_backed_credit.models.otp import OTPLog
from exchange.base.calendar import ir_now
from exchange.base.models import Settings
from tests.asset_backed_credit.helper import ABCMixins, APIHelper


class GrantedPermissionTests(APIHelper, ABCMixins):
    URL = ''

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.internal_user = self.create_internal_user(self.user)
        self._set_client_credentials(self.user.auth_token.key)
        self.services = Service.objects.bulk_create(
            [
                Service(
                    tp=Service.TYPES.credit,
                    provider=Service.PROVIDERS.tara,
                    is_active=True,
                    is_available=True,
                    contract_id='123',
                ),
                Service(
                    tp=Service.TYPES.loan,
                    provider=Service.PROVIDERS.tara,
                    is_active=True,
                    is_available=True,
                    contract_id='223',
                ),
                Service(
                    tp=Service.TYPES.debit,
                    provider=Service.PROVIDERS.tara,
                    is_active=False,
                    is_available=True,
                    contract_id='223',
                ),
                Service(
                    tp=Service.TYPES.loan,
                    provider=Service.PROVIDERS.vency,
                    is_active=True,
                    is_available=False,
                    contract_id='223',
                ),
                Service(
                    tp=Service.TYPES.loan,
                    provider=Service.PROVIDERS.azki,
                    is_active=True,
                    is_available=True,
                    contract_id='45932',
                ),
            ],
        )

        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.credit, min_limit=500)
        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.loan, min_limit=500)
        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.debit, min_limit=500)

        UserFinancialServiceLimit.set_service_limit(service=self.services[0], max_limit=1000000)
        UserFinancialServiceLimit.set_service_limit(service=self.services[1], max_limit=100000)
        UserFinancialServiceLimit.set_service_limit(service=self.services[2], max_limit=300000)
        UserFinancialServiceLimit.set_service_limit(service=self.services[4], max_limit=300000)
        UserFinancialServiceLimit.set_user_service_limit(user=self.user, service=self.services[1], max_limit=0)

    def _set_client_credentials(self, auth_token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {auth_token}')

    def _post_request(
        self, url: Optional[str] = None, data: Optional[dict] = None, headers: Optional[dict] = None
    ) -> HttpResponse:
        if not url:
            url = self.URL
        return self.client.post(path=url, data=data, headers=headers)

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

    def _get_otp(self) -> UserOTP:
        user_otp = UserOTP.objects.filter(
            user=self.user,
            otp_type=UserOTP.OTP_TYPES.mobile,
            otp_usage=UserOTP.OTP_Usage.grant_permission_to_financial_service,
        ).last()
        assert user_otp
        return user_otp


class GrantedPermissionOTPTests(GrantedPermissionTests):
    URL = '/otp/request'

    def _check_user_permission_service(self, service: Service, user_otp: UserOTP):
        user_permission = UserServicePermission.objects.last()
        assert user_permission.user == self.user
        assert user_permission.service == service
        assert user_permission.user_otp == user_otp

    def test_get_otp_failed_parse_error(self):
        # service_type has wrong type
        response = self._post_request(
            data={'type': 'mobile', 'usage': 'grant-financial-service', 'serviceId': 'fff'},
        )
        self._check_response(
            response,
            status.HTTP_400_BAD_REQUEST,
            'failed',
            'ParseError',
            'Invalid integer value: "fff"',
        )
        # not send service id
        response = self._post_request(
            data={'type': 'mobile', 'usage': 'grant-financial-service'},
        )
        self._check_response(
            response,
            status.HTTP_400_BAD_REQUEST,
            'failed',
            'ParseError',
            'Missing integer value',
        )

    def test_get_otp_failed_not_confirmed_mobile(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': False})
        response = self._post_request(
            data={'type': 'mobile', 'usage': 'grant-financial-service', 'serviceId': self.services[2].id},
        )
        self._check_response(
            response,
            status.HTTP_200_OK,
            'failed',
            'InvalidUsageForUser',
            'User has not confirmed mobile.',
        )

    def test_get_otp_failed_service_does_not_exist(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        response = self._post_request(
            data={'type': 'mobile', 'usage': 'grant-financial-service', 'serviceId': self.services[2].id},
        )
        self._check_response(response, status.HTTP_404_NOT_FOUND)

    def test_get_otp_failed_user_has_limitation(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        response = self._post_request(
            data={'type': 'mobile', 'usage': 'grant-financial-service', 'serviceId': self.services[1].id},
        )
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'UserLimitation',
            'You are limited to activate the service.',
        )

    def test_get_otp_failed_activated_permission(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        UserServicePermission.objects.create(user=self.user, created_at=ir_now(), service=self.services[0])
        response = self._post_request(
            data={'type': 'mobile', 'usage': 'grant-financial-service', 'serviceId': self.services[0].id},
        )
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'ServiceAlreadyActivated',
            'Service is already activated.',
        )

    def test_get_otp_failed_unavailable_service(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        UserServicePermission.objects.create(user=self.user, created_at=ir_now(), service=self.services[3])
        response = self._post_request(
            data={'type': 'mobile', 'usage': 'grant-financial-service', 'serviceId': self.services[3].id},
        )
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'ServiceUnavailableError',
            'در حال حاضر، سرویس‌دهنده ظرفیتی برای اعطای وام ندارد. لطفا روزهای آینده دوباره این صفحه را بررسی کنید.',
        )

    def test_get_otp_successful(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        self._change_parameters_in_object(self.user, {'mobile': '09120000000'})
        response = self._post_request(
            data={'type': 'mobile', 'usage': 'grant-financial-service', 'serviceId': self.services[0].id},
        )
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        user_sms = UserSms.objects.last()
        assert user_sms
        assert user_sms.user == self.user

        user_otp_1 = self._get_otp()

        self._check_user_permission_service(self.services[0], user_otp_1)

        # try again (same service)
        self.user.refresh_from_db()
        response = self._post_request(
            data={'type': 'mobile', 'usage': 'grant-financial-service', 'serviceId': self.services[0].id},
        )
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        user_otp_2 = self._get_otp()
        assert user_otp_2.code == user_otp_1.code
        self._check_user_permission_service(self.services[0], user_otp_2)

        user_otp_1.refresh_from_db()
        assert user_otp_1.otp_status == UserOTP.OTP_STATUS.disabled

        # try again (not same)
        self.services[2].is_active = True
        self.services[2].save(update_fields=['is_active'])
        self.user.refresh_from_db()
        response = self._post_request(
            data={'type': 'mobile', 'usage': 'grant-financial-service', 'serviceId': self.services[2].id},
        )
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        user_otp_3 = self._get_otp()
        assert user_otp_3.code != user_otp_2.code
        self._check_user_permission_service(self.services[2], user_otp_3)

        user_otp_2.refresh_from_db()
        assert user_otp_2.otp_status == UserOTP.OTP_STATUS.disabled

        user_service_permission = UserServicePermission.objects.last()
        user_service_permission.user_otp = None
        user_service_permission.save(update_fields=['user_otp'])

        # try again (not same) and related user otp is deleted by another cron
        response = self._post_request(
            data={'type': 'mobile', 'usage': 'grant-financial-service', 'serviceId': self.services[0].id},
        )
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        user_otp_4 = self._get_otp()
        assert user_otp_4.code != user_otp_3.code
        self._check_user_permission_service(self.services[0], user_otp_4)

    def test_failed_request_for_azki_and_android_client_version_is_less_than_704(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        self._change_parameters_in_object(self.user, {'mobile': '09120000000'})
        response = self._post_request(
            data={'type': 'mobile', 'usage': 'grant-financial-service', 'serviceId': self.services[4].id},
            headers={'User-Agent': 'Android/7.0.3'},
        )
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            code='PleaseUpdateApp',
            message='Please Update App',
        )

    def test_success_request_for_azki_and_android_client_version_is_704_or_more(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        self._change_parameters_in_object(self.user, {'mobile': '09120000000'})

        response = self._post_request(
            data={'type': 'mobile', 'usage': 'grant-financial-service', 'serviceId': self.services[4].id},
            headers={'User-Agent': 'Android/7.0.4'},
        )
        assert response.status_code == status.HTTP_200_OK

    def test_success_request_for_not_azki_and_android_client_version_is_less_than_704(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        self._change_parameters_in_object(self.user, {'mobile': '09120000000'})

        UserFinancialServiceLimit.set_user_service_limit(user=self.user, service=self.services[1], max_limit=1_000_000)
        response = self._post_request(
            data={'type': 'mobile', 'usage': 'grant-financial-service', 'serviceId': self.services[1].id},
            headers={'User-Agent': 'Android/7.0.4'},
        )
        print(response.json())
        assert response.status_code == status.HTTP_200_OK


class VerifyGrantedPermissionOTPTests(GrantedPermissionTests):
    URL = '/asset-backed-credit/services/{}/activate'

    def test_verify_otp_failed_pars_error(self):
        # not send OTP
        response = self._post_request(
            url=self.URL.format(self.services[1].id),
            data={},
        )
        self._check_response(
            response,
            status.HTTP_400_BAD_REQUEST,
            'failed',
            'ParseError',
            'Missing string value',
        )

    def test_verify_otp_failed_service_does_not_exist(self):
        response = self._post_request(
            url=self.URL.format(self.services[2].id),
            data={'otp': '12345'},
        )
        self._check_response(response, status.HTTP_404_NOT_FOUND)

    def test_verify_otp_failed_user_has_limitation(self):
        response = self._post_request(
            url=self.URL.format(self.services[1].id),
            data={'otp': '12345'},
        )
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'UserLimitation',
            'You are limited to activate the service.',
        )

    def test_verify_otp_failed_user_does_not_send_request(self):
        response = self._post_request(
            url=self.URL.format(self.services[0].id),
            data={'otp': '12345'},
        )
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'GrantedPermissionDoseNotFound',
            'You need to request an OTP to activate this service.',
        )

    def test_verify_otp_failed_not_same_service(self):
        # fix user preconditions
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        self._change_parameters_in_object(self.user, {'mobile': '09120000000'})
        # create inactive UserPermissionService
        response = self._post_request(
            url=GrantedPermissionOTPTests.URL,
            data={'type': 'mobile', 'usage': 'grant-financial-service', 'serviceId': self.services[0].id},
        )
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        # try again (not same)
        self.services[2].is_active = True
        self.services[2].save(update_fields=['is_active'])
        response = self._post_request(
            url=self.URL.format(self.services[2].id),
            data={'otp': '12345'},
        )
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'ServiceMismatchError',
            'The selected service is not existed for verifying otp.',
        )

    def test_verify_otp_failed_already_activate(self):
        # fix user preconditions
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        self._change_parameters_in_object(self.user, {'mobile': '09120000000'})
        # create inactive UserPermissionService
        response = self._post_request(
            url=GrantedPermissionOTPTests.URL,
            data={'type': 'mobile', 'usage': 'grant-financial-service', 'serviceId': self.services[0].id},
        )
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        # activate last granted permission service
        last_inactive_permission = UserServicePermission.get_last_inactive_permission(self.user)
        assert last_inactive_permission
        last_inactive_permission.activate()
        last_inactive_permission.refresh_from_db()

        # try activate that the granted permission service is activated
        response = self._post_request(
            url=self.URL.format(self.services[0].id),
            data={'otp': '12345'},
        )
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'GrantedPermissionDoseNotFound',
            'You need to request an OTP to activate this service.',
        )

    def test_verify_otp_failed_otp_not_same(self):
        # fix user preconditions
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        self._change_parameters_in_object(self.user, {'mobile': '09120000000'})
        # create inactive UserPermissionService
        response = self._post_request(
            url=GrantedPermissionOTPTests.URL,
            data={'type': 'mobile', 'usage': 'grant-financial-service', 'serviceId': self.services[0].id},
        )
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        otp = self._get_otp().code
        response = self._post_request(
            url=self.URL.format(self.services[0].id),
            data={'otp': otp + '1'},
        )
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'OTPValidationError',
            'OTP does not verified:not found',
        )

    def test_verify_otp_successful(self):
        # fix user preconditions
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        self._change_parameters_in_object(self.user, {'mobile': '09120000000'})
        # create inactive UserPermissionService
        response = self._post_request(
            url=GrantedPermissionOTPTests.URL,
            data={'type': 'mobile', 'usage': 'grant-financial-service', 'serviceId': self.services[0].id},
        )
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        permission = UserServicePermission.objects.filter(user=self.user).last()
        assert not permission.created_at
        otp = self._get_otp().code
        response = self._post_request(
            url=self.URL.format(self.services[0].id),
            data={'otp': otp},
        )
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        permission.refresh_from_db()
        assert permission.created_at
        assert permission.user_otp.otp_status == UserOTP.OTP_STATUS.used

        notif = Notification.objects.filter(user=self.user).order_by('-created_at').first()
        assert notif
        assert notif.message == (f'سرویس {permission.service.readable_name} برای شما در نوبیتکس فعال شده است.')

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_verify_otp_email_notif(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        self._change_parameters_in_object(self.user.get_verification_profile(), {'email_confirmed': True})
        self._change_parameters_in_object(self.user, {'mobile': '09120000000'})
        Settings.set_dict('email_whitelist', [self.user.email])
        call_command('update_email_templates')
        response = self._post_request(
            url=GrantedPermissionOTPTests.URL,
            data={'type': 'mobile', 'usage': 'grant-financial-service', 'serviceId': self.services[0].id},
        )
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        permission = UserServicePermission.objects.filter(user=self.user).last()
        assert not permission.created_at
        otp = self._get_otp().code
        self._post_request(
            url=self.URL.format(self.services[0].id),
            data={'otp': otp},
        )
        permission.refresh_from_db()
        assert permission.created_at
        with patch('django.db.connection.close'):
            call_command('send_queued_mail')

    @patch('exchange.asset_backed_credit.externals.notification.notification_provider.send_email')
    def test_verify_otp_success_sends_correct_email_data(self, mocked_notification_provider):
        self._change_parameters_in_object(
            self.user.get_verification_profile(), {'mobile_confirmed': True, 'email_confirmed': True}
        )
        self._change_parameters_in_object(self.user, {'mobile': '09120000000', 'email': 'example@example.com'})
        # create inactive UserPermissionService
        service = self.services[0]
        response = self._post_request(
            url=GrantedPermissionOTPTests.URL,
            data={'type': 'mobile', 'usage': 'grant-financial-service', 'serviceId': service.id},
        )
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        permission = UserServicePermission.objects.filter(user=self.user).last()
        assert not permission.created_at
        otp = self._get_otp().code
        response = self._post_request(
            url=self.URL.format(service.id),
            data={'otp': otp},
        )
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        permission.refresh_from_db()
        assert permission.created_at
        assert permission.user_otp.otp_status == UserOTP.OTP_STATUS.used

        # assert sent email data
        mocked_notification_provider.assert_called_once_with(
            to_email='example@example.com',
            template='abc/abc_service_activated',
            data={
                'financial_service': 'اعتبار تارا',
                'help_link': 'https://nobitex.ir/help/discover/credit/activating-credit-purchasing/',
            },
            priority='low',
        )

    @responses.activate
    def test_verify_otp_success_when_internal_api_is_enabled(self):
        responses.post(
            url=VerifyOTPAPI.url.format(self.user.uid),
            json={},
            status=status.HTTP_200_OK,
        )
        Settings.set('abc_use_verify_otp_internal_api', 'yes')
        otp_log = OTPLog.objects.create(
            user=self.user,
            internal_user=self.internal_user,
            otp_type=OTPLog.OTP_TYPES.mobile,
            usage=OTPLog.OTP_USAGE.grant_permission_to_financial_service,
            send_api_response_code=status.HTTP_200_OK,
            send_api_called_at=ir_now(),
        )
        permission = UserServicePermission.get_or_create_inactive_permission(self.user, self.services[0])
        response = self._post_request(
            url=self.URL.format(self.services[0].id),
            data={'otp': '123456'},
        )
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        permission.refresh_from_db()
        assert permission.created_at
        notif = Notification.objects.filter(user=self.user).order_by('-created_at').first()
        assert notif
        assert notif.message == (f'سرویس {permission.service.readable_name} برای شما در نوبیتکس فعال شده است.')
        otp_log.refresh_from_db()
        assert otp_log.verify_api_called_at
        assert otp_log.verify_api_response_code == status.HTTP_200_OK

    @responses.activate
    def test_verify_otp_fails_when_internal_api_is_enabled_but_raises_error(self):
        responses.post(
            url=VerifyOTPAPI.url.format(self.user.uid),
            json={},
            status=status.HTTP_400_BAD_REQUEST,
        )
        Settings.set('abc_use_verify_otp_internal_api', 'yes')
        otp_log = OTPLog.objects.create(
            user=self.user,
            internal_user=self.internal_user,
            otp_type=OTPLog.OTP_TYPES.mobile,
            usage=OTPLog.OTP_USAGE.grant_permission_to_financial_service,
            send_api_response_code=status.HTTP_200_OK,
            send_api_called_at=ir_now(),
        )
        permission = UserServicePermission.get_or_create_inactive_permission(self.user, self.services[0])
        response = self._post_request(
            url=self.URL.format(self.services[0].id),
            data={'otp': '123456'},
        )
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='OTPValidationError',
            message='OTP verification failed.',
            status_data='failed',
        )
        permission.refresh_from_db()
        assert permission.created_at is None
        otp_log.refresh_from_db()
        assert otp_log.verify_api_called_at
        assert otp_log.verify_api_response_code == status.HTTP_400_BAD_REQUEST
