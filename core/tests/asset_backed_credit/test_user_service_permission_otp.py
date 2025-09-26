from typing import Optional

import pytest
import responses
from django.http import HttpResponse
from rest_framework import status

from exchange.accounts.models import Notification, User, UserOTP, UserSms
from exchange.asset_backed_credit.externals.base import NOBITEX_BASE_URL
from exchange.asset_backed_credit.models import Service, UserFinancialServiceLimit, UserServicePermission
from exchange.asset_backed_credit.models.otp import OTPLog
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies, Settings
from tests.asset_backed_credit.helper import ABCMixins, APIHelper


class GrantedPermissionTests(APIHelper, ABCMixins):
    URL = ''

    def setUp(self):
        self.user = User.objects.get(pk=201)
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
                    contract_id='225',
                ),
                Service(
                    tp=Service.TYPES.loan,
                    provider=Service.PROVIDERS.azki,
                    is_active=True,
                    is_available=True,
                    contract_id='56889',
                ),
            ],
        )

        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.credit, min_limit=500)
        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.loan, min_limit=500)
        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.debit, min_limit=500)

        UserFinancialServiceLimit.set_service_limit(service=self.services[0], max_limit=1000000)
        UserFinancialServiceLimit.set_service_limit(service=self.services[1], max_limit=100000)
        UserFinancialServiceLimit.set_service_limit(service=self.services[2], max_limit=300000)
        UserFinancialServiceLimit.set_service_limit(service=self.services[3], max_limit=300000)
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
        user_otp = (
            UserOTP.objects.filter(
                user=self.user,
                otp_type=UserOTP.OTP_TYPES.mobile,
                otp_usage=UserOTP.OTP_Usage.grant_permission_to_financial_service,
            )
            .order_by('pk')
            .last()
        )
        assert user_otp
        return user_otp


class GrantedPermissionOTPTests(GrantedPermissionTests):
    URL = '/asset-backed-credit/services/{service_id}/permission/request'
    usage = UserOTP.OTP_Usage.grant_permission_to_financial_service

    def _check_user_permission_service(self, service: Service, _: UserOTP):
        user_permission = UserServicePermission.objects.order_by('pk').last()
        assert user_permission.user == self.user
        assert user_permission.service == service

    def test_get_otp_failed_parse_error(self):
        # service_type has wrong type
        response = self._post_request(
            url=self.URL.format(service_id='fff'),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_otp_failed_not_confirmed_mobile(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': False})
        response = self._post_request(url=self.URL.format(service_id=self.services[0].id))
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'OTPRequestFailure',
            'User has not confirmed mobile',
        )

    def test_get_otp_failed_service_does_not_exist(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        response = self._post_request(url=self.URL.format(service_id=self.services[2].id))
        self._check_response(response, status.HTTP_404_NOT_FOUND)

    def test_get_otp_failed_user_has_limitation(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        response = self._post_request(url=self.URL.format(service_id=self.services[1].id))
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
        response = self._post_request(url=self.URL.format(service_id=self.services[0].id))
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
        response = self._post_request(url=self.URL.format(service_id=self.services[3].id))
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'ServiceUnavailableError',
            'در حال حاضر، سرویس‌دهنده ظرفیتی برای اعطای وام ندارد. لطفا روزهای آینده دوباره این صفحه را بررسی کنید.',
        )

    def test_get_otp_failed_unavailable_service_android_agent(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        UserServicePermission.objects.create(user=self.user, created_at=ir_now(), service=self.services[3])
        response = self._post_request(
            url=self.URL.format(service_id=self.services[3].id), headers={'User-Agent': 'Android/6.8.0-dev'}
        )
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'در حال حاضر، سرویس‌دهنده ظرفیتی برای اعطای وام ندارد. لطفا روزهای آینده دوباره این صفحه را بررسی کنید.',
            'ServiceUnavailableError',
        )

    def test_get_otp_successful(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        self._change_parameters_in_object(self.user, {'mobile': '09120000000'})
        response = self._post_request(url=self.URL.format(service_id=self.services[0].id))

        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        user_sms = UserSms.objects.order_by('pk').last()
        assert user_sms
        assert user_sms.user == self.user

        user_otp_1 = self._get_otp()

        self._check_user_permission_service(self.services[0], user_otp_1)

        # try again (same service)
        self.user.refresh_from_db()
        response = self._post_request(
            url=self.URL.format(service_id=self.services[0].id), data={'type': 'mobile', 'usage': self.usage}
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
        assert user_otp_1.otp_status == UserOTP.OTP_STATUS.new

        # these are added
        user_otp_2.otp_status = UserOTP.OTP_STATUS.used
        user_otp_2.save()

        # try again (not same), because last otp is used.
        self.services[2].is_active = True
        self.services[2].save(update_fields=['is_active'])
        self.user.refresh_from_db()
        response = self._post_request(
            url=self.URL.format(service_id=self.services[2].id),
        )
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )

        user_otp_3 = self._get_otp()
        assert user_otp_3.code != user_otp_2.code
        self._check_user_permission_service(self.services[2], user_otp_3)

        user_otp_3.otp_status = UserOTP.OTP_STATUS.used
        user_otp_3.save()

        # try again (not same) and related user otp is deleted by another cron
        response = self._post_request(
            url=self.URL.format(service_id=self.services[0].id),
        )
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        user_otp_4 = self._get_otp()
        assert user_otp_4.code != user_otp_3.code
        assert UserServicePermission.objects.last().service == self.services[2]

    def test_successful_when_user_has_revoked_permission(self):
        UserServicePermission.objects.create(
            user=self.user, created_at=ir_now(), revoked_at=ir_now(), service=self.services[0]
        )

        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        self._change_parameters_in_object(self.user, {'mobile': '09120000000'})

        response = self._post_request(url=self.URL.format(service_id=self.services[0].id))
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )

        assert UserServicePermission.objects.filter(user=self.user, service=self.services[0]).count() == 2
        latest_permission = (
            UserServicePermission.objects.filter(
                user=self.user,
                service=self.services[0],
            )
            .order_by('pk')
            .last()
        )

        assert not latest_permission.is_active()

    @responses.activate
    def test_success_when_send_otp_internal_api_is_enabled(self):
        responses.post(
            url=f'{NOBITEX_BASE_URL}/internal/users/{self.user.uid}/send-otp',
            json={},
            status=status.HTTP_200_OK,
        )
        Settings.set('abc_use_send_otp_internal_api', 'yes')
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        self._change_parameters_in_object(self.user, {'mobile': '09120000000'})

        response = self._post_request(url=self.URL.format(service_id=self.services[0].id))

        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        otp_log = OTPLog.objects.filter(user=self.user).order_by('pk').last()
        assert otp_log
        assert otp_log.send_api_response_code == status.HTTP_200_OK
        assert otp_log.send_api_called_at
        assert otp_log.verify_api_response_code is None
        assert otp_log.verify_api_called_at is None

    @responses.activate
    def test_fails_when_send_otp_internal_api_is_enabled_but_raises_error(self):
        responses.post(
            url=f'{NOBITEX_BASE_URL}/internal/users/{self.user.uid}/send-otp',
            json={},
            status=status.HTTP_400_BAD_REQUEST,
        )
        Settings.set('abc_use_send_otp_internal_api', 'yes')
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        self._change_parameters_in_object(self.user, {'mobile': '09120000000'})

        response = self._post_request(url=self.URL.format(service_id=self.services[0].id))

        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
        )
        otp_log = OTPLog.objects.filter(user=self.user).order_by('pk').last()
        assert otp_log
        assert otp_log.send_api_response_code == status.HTTP_400_BAD_REQUEST
        assert otp_log.send_api_called_at
        assert otp_log.verify_api_response_code is None
        assert otp_log.verify_api_called_at is None

    def test_failed_request_for_azki_and_android_client_version_is_less_than_704(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        self._change_parameters_in_object(self.user, {'mobile': '09120000000'})

        response = self._post_request(
            url=self.URL.format(service_id=self.services[4].id), headers={'User-Agent': 'Android/6.0.2'}
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
            url=self.URL.format(service_id=self.services[4].id), headers={'User-Agent': 'Android/7.0.4'}
        )

        assert response.status_code == status.HTTP_200_OK

    def test_success_request_for_not_azki_and_android_client_version_is_less_than_704(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        self._change_parameters_in_object(self.user, {'mobile': '09120000000'})

        UserFinancialServiceLimit.set_user_service_limit(user=self.user, service=self.services[1], max_limit=1_000_000)
        response = self._post_request(
            url=self.URL.format(service_id=self.services[1].id), headers={'User-Agent': 'Android/7.0.4'}
        )
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.skip
class VerifyGrantedPermissionOTPTests(GrantedPermissionTests):
    URL = '/asset-backed-credit/services/{}/activate'

    def test_verify_otp_failed_service_unavailable(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        self._change_parameters_in_object(self.user, {'mobile': '09120000000'})
        request_url = '/asset-backed-credit/services/{service_id}/permission/request'
        _ = self._post_request(url=request_url.format(service_id=self.services[0].id))

        otp = self._get_otp()
        permission = UserServicePermission.objects.filter(user=self.user).order_by('pk').last()
        assert not permission.created_at

        self.services[0].is_available = False
        self.services[0].save()

        response = self._post_request(url=self.URL.format(self.services[0].id), data={'otp': otp.code})
        self._check_response(response, status.HTTP_422_UNPROCESSABLE_ENTITY, 'failed', 'ServiceUnavailableError')

    def test_verify_otp_successful_with_new_permission_request_use_case(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        self._change_parameters_in_object(self.user, {'mobile': '09120000000'})
        request_url = '/asset-backed-credit/services/{service_id}/permission/request'
        _ = self._post_request(url=request_url.format(service_id=self.services[0].id))

        otp = self._get_otp()
        permission = UserServicePermission.objects.filter(user=self.user).order_by('pk').last()
        assert not permission.created_at

        response = self._post_request(url=self.URL.format(self.services[0].id), data={'otp': otp.code})
        self._check_response(response, status.HTTP_200_OK, 'ok')

        permission.refresh_from_db()
        otp.refresh_from_db()

        assert permission.created_at
        assert otp.otp_status == UserOTP.OTP_STATUS.used

        notif = Notification.objects.filter(user=self.user).order_by('-created_at').first()
        assert notif
        assert notif.message == (f'سرویس {permission.service.readable_name} برای شما در نوبیتکس فعال شده است.')

    def test_verify_permission_request_first_new_then_old_style_otp_request(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        self._change_parameters_in_object(self.user, {'mobile': '09120000000'})

        self.services[2].is_active = True
        self.services[2].save()

        UserFinancialServiceLimit.set_user_service_limit(user=self.user, service=self.services[1], max_limit=100000)

        self._request_otp_new(service_id=self.services[0].id)

        first_otp = self._get_otp()
        permission = UserServicePermission.objects.filter(user=self.user).order_by('pk').last()
        assert permission.service == self.services[0]
        assert not permission.created_at

        self._request_otp_old(service_id=self.services[2].id)

        second_otp = self._get_otp()
        permission = UserServicePermission.objects.filter(user=self.user).order_by('pk').last()
        assert permission.service == self.services[2]
        assert not permission.created_at

        assert first_otp.code != second_otp.code

        first_otp.refresh_from_db()
        assert first_otp.otp_status == UserOTP.OTP_STATUS.disabled

        response = self._post_request(url=self.URL.format(self.services[0].id), data={'otp': first_otp.code})
        self._check_response(response, status.HTTP_422_UNPROCESSABLE_ENTITY, 'failed')

        response = self._post_request(url=self.URL.format(self.services[2].id), data={'otp': second_otp.code})
        self._check_response(response, status.HTTP_200_OK, 'ok')

        permission = UserServicePermission.objects.filter(user=self.user).order_by('pk').last()
        assert permission.created_at is not None
        assert permission.service == self.services[2]

    def test_verify_permission_request_first_old_then_new_style_otp_request(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        self._change_parameters_in_object(self.user, {'mobile': '09120000000'})

        UserFinancialServiceLimit.set_user_service_limit(user=self.user, service=self.services[1], max_limit=100000)

        self._request_otp_old(service_id=self.services[1].id)

        first_otp = self._get_otp()
        permission = UserServicePermission.objects.filter(user=self.user).order_by('pk').last()
        assert permission.service == self.services[1]
        assert not permission.created_at

        self._request_otp_new(service_id=self.services[0].id)

        second_otp = self._get_otp()
        permission = UserServicePermission.objects.filter(user=self.user).order_by('pk').last()
        assert permission.service == self.services[0]
        assert not permission.created_at

        assert first_otp.code == second_otp.code

        response = self._post_request(url=self.URL.format(self.services[1].id), data={'otp': first_otp.code})
        self._check_response(response, status.HTTP_200_OK, 'ok')

        permission = (
            UserServicePermission.objects.filter(user=self.user, service=self.services[1]).order_by('pk').last()
        )
        assert permission.created_at is not None

        response = self._post_request(url=self.URL.format(self.services[0].id), data={'otp': second_otp.code})
        self._check_response(response, status.HTTP_422_UNPROCESSABLE_ENTITY, 'failed')

        permission = (
            UserServicePermission.objects.filter(user=self.user, service=self.services[0]).order_by('pk').last()
        )
        assert permission.created_at is None

    def test_verify_permission_request_first_old_then_new_style_otp_request_2(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        self._change_parameters_in_object(self.user, {'mobile': '09120000000'})

        UserFinancialServiceLimit.set_user_service_limit(user=self.user, service=self.services[1], max_limit=100000)

        self._request_otp_old(service_id=self.services[1].id)

        first_otp = self._get_otp()
        permission = UserServicePermission.objects.filter(user=self.user).order_by('pk').last()
        assert permission.service == self.services[1]
        assert not permission.created_at

        self._request_otp_new(service_id=self.services[0].id)

        second_otp = self._get_otp()
        permission = UserServicePermission.objects.filter(user=self.user).order_by('pk').last()
        assert permission.service == self.services[0]
        assert not permission.created_at

        assert first_otp.code == second_otp.code

        response = self._post_request(url=self.URL.format(self.services[0].id), data={'otp': first_otp.code})
        self._check_response(response, status.HTTP_200_OK, 'ok')

        permission = (
            UserServicePermission.objects.filter(user=self.user, service=self.services[0]).order_by('pk').last()
        )
        assert permission.created_at is not None

        response = self._post_request(url=self.URL.format(self.services[1].id), data={'otp': second_otp.code})
        self._check_response(response, status.HTTP_422_UNPROCESSABLE_ENTITY, 'failed')

        permission = (
            UserServicePermission.objects.filter(user=self.user, service=self.services[1]).order_by('pk').last()
        )
        assert permission.created_at is None

    def test_verify_permission_request_cannot_verify_not_requested_service(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        self._change_parameters_in_object(self.user, {'mobile': '09120000000'})

        UserFinancialServiceLimit.set_user_service_limit(user=self.user, service=self.services[1], max_limit=100000)

        self.services[2].is_active = True
        self.services[2].save()

        self._request_otp_old(service_id=self.services[1].id)

        first_otp = self._get_otp()
        permission = UserServicePermission.objects.filter(user=self.user).order_by('pk').last()
        assert permission.service == self.services[1]
        assert not permission.created_at

        self._request_otp_new(service_id=self.services[0].id)

        second_otp = self._get_otp()
        permission = UserServicePermission.objects.filter(user=self.user).order_by('pk').last()
        assert permission.service == self.services[0]
        assert not permission.created_at

        assert first_otp.code == second_otp.code

        response = self._post_request(url=self.URL.format(self.services[2].id), data={'otp': first_otp.code})
        self._check_response(response, status.HTTP_422_UNPROCESSABLE_ENTITY, 'failed')

    def test_verify_permission_request_cannot_verify_not_requested_service_2(self):
        self._change_parameters_in_object(self.user.get_verification_profile(), {'mobile_confirmed': True})
        self._change_parameters_in_object(self.user, {'mobile': '09120000000'})

        UserFinancialServiceLimit.set_user_service_limit(user=self.user, service=self.services[1], max_limit=100000)

        self.services[2].is_active = True
        self.services[2].save()

        self._request_otp_new(service_id=self.services[1].id)

        first_otp = self._get_otp()
        permission = UserServicePermission.objects.filter(user=self.user).order_by('pk').last()
        assert permission.service == self.services[1]
        assert not permission.created_at

        self._request_otp_old(service_id=self.services[0].id)

        second_otp = self._get_otp()
        permission = UserServicePermission.objects.filter(user=self.user).order_by('pk').last()
        assert permission.service == self.services[0]
        assert not permission.created_at

        assert first_otp.code != second_otp.code

        response = self._post_request(url=self.URL.format(self.services[2].id), data={'otp': second_otp.code})
        self._check_response(response, status.HTTP_422_UNPROCESSABLE_ENTITY, 'failed')

    def _request_otp_old(self, service_id):
        request_url = '/otp/request'
        resp = self._post_request(
            url=request_url, data={'type': 'mobile', 'usage': 'grant-financial-service', 'serviceId': service_id}
        )
        assert resp.status_code == status.HTTP_200_OK

    def _request_otp_new(self, service_id):
        request_url = '/asset-backed-credit/services/{service_id}/permission/request'
        resp = self._post_request(url=request_url.format(service_id=service_id))
        assert resp.status_code == status.HTTP_200_OK
