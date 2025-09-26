import datetime
import random
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
import responses
from django.core.management import call_command
from django.http import HttpResponse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase, override_settings

from exchange.accounts.crons import DeleteUncompletedMergeRequest
from exchange.accounts.merge import MergeRequestStatusChangedContext
from exchange.accounts.models import (
    Notification,
    ReferralProgram,
    Tag,
    User,
    UserEvent,
    UserMergeRequest,
    UserOTP,
    UserSms,
    UserTag,
)
from exchange.accounts.tasks import task_reject_merge_request, task_send_user_sms, task_user_merge
from exchange.base.calendar import get_earliest_time, ir_now
from exchange.base.models import Currencies, Settings
from exchange.wallet.models import Wallet
from tests.accounts.test_models import MockEmail
from tests.base.utils import mock_on_commit


class MergeTests(APITestCase):
    URL = ''

    def setUp(self):
        self.users: List[User] = [User.objects.get(pk=201), User.objects.get(pk=202)]
        self._set_client_credentials(self.users[0].auth_token.key)
        self._config_users()

    def _config_users(self):
        for user in self.users:
            vp = user.get_verification_profile()
            vp.email_confirmed = True
            vp.save()

    def _set_client_credentials(self, auth_token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {auth_token}')

    def _post_request(self, url: Optional[str] = None, data: Optional[dict] = None) -> HttpResponse:
        if not url:
            url = self.URL
        return self.client.post(path=url, data=data)

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

    def _change_parameters_in_object(self, obj, update_fields: dict):
        obj.__dict__.update(**update_fields)
        obj.save()

    def _check_change_request(
        self,
        data: Optional[dict] = None,
        user_event_obj: Optional[UserEvent] = None,
        user_otp_obj: Optional[UserOTP] = None,
    ):
        if data:
            merge_request = UserMergeRequest.objects.last()
            assert 'merge_request' in data
            assert data['merge_request']['status'] == merge_request.get_status_display()

        if user_event_obj:
            user_event = UserEvent.objects.last()
            assert user_event.action == user_event_obj.action
            assert user_event.action_type == user_event_obj.action_type

        if user_otp_obj:
            user_otp = UserOTP.objects.last()
            assert user_otp.otp_type == user_otp_obj.otp_type
            assert user_otp.otp_usage == user_otp_obj.otp_usage
            assert user_otp.otp_status == user_otp_obj.otp_status
            assert user_otp.user == user_otp_obj.user

    def _check_user_otps(self, items: dict, user, otp_type: int):
        for key, value in items.items():
            assert (
                UserOTP.objects.filter(
                    user=user,
                    otp_type=otp_type,
                    otp_usage=UserOTP.OTP_Usage.user_merge,
                    otp_status=key,
                ).count()
                == value
            )

    def _check_user_events(self, items: dict, user):
        for key, value in items.items():
            assert (
                UserEvent.objects.filter(
                    user=user,
                    action=UserEvent.ACTION_CHOICES.user_merge,
                    action_type=key,
                ).count()
                == value
            )

    def _charge_wallet(
        self,
        user: User,
        currency: int,
        initial_balance: int = 10,
        tp=Wallet.WALLET_TYPE.spot,
    ) -> Wallet:
        wallet = Wallet.get_user_wallet(user, currency, tp)
        wallet.create_transaction('manual', initial_balance).commit()
        wallet.refresh_from_db()

    def _create_referral_program(self, user: User):
        ReferralProgram.create(user, 15)

    def _check_email_sent(self, recipient_email: str, template: str):
        email = MockEmail.all_mock_emails[-1]
        assert email.email == recipient_email
        assert email.template == template

    def _check_user_sms(self, user: User, sms: UserSms):
        last_sms = UserSms.objects.filter(user=user).last()
        assert last_sms.user == sms.user
        assert last_sms.tp == sms.tp
        assert last_sms.to == sms.to
        assert last_sms.template == sms.template


class CreateMergeRequestTests(MergeTests):
    URL = '/users/create-merge-request'

    def test_parameter_api(self):
        response = self._post_request()
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'InvalidUserError',
            'User Does Not Exist.',
        )

        response = self._post_request(data={'email': 'x@gmail.com', 'mobile': '09120000000'})
        self._check_response(
            response,
            status.HTTP_400_BAD_REQUEST,
            'failed',
            'ParseError',
            'Fill one of Email Or Mobile Fields.',
        )

        response = self._post_request(data={'email': 'x@x.com'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'InvalidUserError',
            'User Does Not Exist.',
        )

    def test_for_email_main_account_user_level_failed(self):
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.verified, 'email': None})
        self._change_parameters_in_object(self.users[1], {'email': '202@gmail.com'})
        response = self._post_request(data={'email': '202@gmail.com'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'IncompatibleUserLevelError',
            'User has not allowed request: Main Account level is too high',
        )

    def test_for_email_main_account_has_email_failed(self):
        self._change_parameters_in_object(
            self.users[0],
            {'user_type': User.USER_TYPES.level1, 'email': '201@gmail.com'},
        )
        self._change_parameters_in_object(self.users[1], {'email': '202@gmail.com'})
        response = self._post_request(data={'email': '202@gmail.com'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'UserHasEmailError',
            'User has email.',
        )

    def test_for_email_second_account_user_level(self):
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.level1, 'email': None})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level1, 'email': '202@gmail.com'},
        )
        response = self._post_request(data={'email': '202@gmail.com'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'IncompatibleUserLevelError',
            'User has not allowed request: Second Account level is too high',
        )

    def test_for_email_low_level_user_to_high_level_user(self):
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.blocked, 'email': None})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com'},
        )
        response = self._post_request(data={'email': '202@gmail.com'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'IncompatibleUserLevelError',
            'User has not allowed request: Main account level is too low',
        )

    def test_for_email_user_has_transactions(self):
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.level1, 'email': None})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com'},
        )
        self._charge_wallet(self.users[1], Currencies.rls)
        response = self._post_request(data={'email': '202@gmail.com'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'HasTransactionError',
            'User has transaction.',
        )

    def test_for_email_user_has_referral(self):
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.level1, 'email': None})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com'},
        )
        self._create_referral_program(self.users[1])
        response = self._post_request(data={'email': '202@gmail.com'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'HasReferralProgramError',
            'User has referral program.',
        )

    def test_for_email_check_need_approval_merge_request(self):
        UserMergeRequest.objects.create(
            status=UserMergeRequest.STATUS.need_approval,
            merge_by=UserMergeRequest.MERGE_BY.email,
            main_user=self.users[0],
            second_user=self.users[1],
        )
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.level1, 'email': None})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com'},
        )
        response = self._post_request(data={'email': '202@gmail.com'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'HasActiveMergeRequestError',
            'User has active merge request.',
        )

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_for_email_merge_request(self, send_email, _):
        MockEmail.flush()
        send_email.side_effect = MockEmail.get_mock_send_email()

        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.level1, 'email': None})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com'},
        )
        response = self._post_request(data={'email': '202@gmail.com'})
        data = self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.requested: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
            },
            user=self.users[0],
        )
        self._check_change_request(
            data,
            UserEvent(
                user=self.users[0],
                action=UserEvent.ACTION_CHOICES.user_merge,
                action_type=UserEvent.USER_MERGE_ACTION_TYPES.requested,
            ),
            UserOTP(
                user=self.users[0],
                otp_type=UserOTP.OTP_TYPES.email,
                otp_usage=UserOTP.OTP_Usage.user_merge,
                otp_status=UserOTP.OTP_STATUS.new,
            ),
        )
        # check with new request again:
        response = self._post_request(data={'email': '202@gmail.com'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'HasActiveMergeRequestError',
            'User has active merge request.',
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.requested: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
            },
            user=self.users[0],
        )
        assert (
            UserMergeRequest.objects.filter(
                main_user=self.users[0],
                status=UserMergeRequest.STATUS.email_otp_sent,
            ).count()
            == 1
        )
        self._check_email_sent('202@gmail.com', 'merge/otp_message')

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_for_mobile_merge_request_level0_with_level0(self, _):
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.level0, 'mobile': None})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com', 'mobile': '09121111111'},
        )
        response = self._post_request(data={'mobile': '09121111111'})
        data = self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.requested: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
            },
            user=self.users[0],
        )
        self._check_change_request(
            data,
            UserEvent(
                user=self.users[0],
                action=UserEvent.ACTION_CHOICES.user_merge,
                action_type=UserEvent.USER_MERGE_ACTION_TYPES.requested,
            ),
            UserOTP(
                user=self.users[0],
                otp_type=UserOTP.OTP_TYPES.mobile,
                otp_usage=UserOTP.OTP_Usage.user_merge,
                otp_status=UserOTP.OTP_STATUS.new,
            ),
        )
        # check with new request again:
        response = self._post_request(data={'mobile': '09121111111'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'HasActiveMergeRequestError',
            'User has active merge request.',
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.requested: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
            },
            user=self.users[0],
        )
        assert (
            UserMergeRequest.objects.filter(
                main_user=self.users[0],
                status=UserMergeRequest.STATUS.new_mobile_otp_sent,
            ).count()
            == 1
        )
        self._check_user_sms(
            self.users[0],
            UserSms(
                user=self.users[0],
                tp=UserSms.TYPES.user_merge,
                to='09121111111',
                template=UserSms.TEMPLATES.user_merge_otp,
            ),
        )

    @override_settings(IS_PROD=True)
    def test_for_mobile_merge_request_level1_with_mobile_identity_confirmed_shahkar_not_respond(self):
        self._change_parameters_in_object(
            self.users[0],
            {'user_type': User.USER_TYPES.level1, 'email': None, 'mobile': '09121111112'},
        )
        self._change_parameters_in_object(
            self.users[0].get_verification_profile(),
            {'mobile_confirmed': True, 'mobile_identity_confirmed': True},
        )
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com', 'mobile': '09121111111'},
        )
        response = self._post_request(data={'mobile': '09121111111'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'CheckMobileIdentityError',
            'Check mobile identity error.',
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.requested: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_identity: 1,
            },
            user=self.users[0],
        )

    @responses.activate
    @override_settings(IS_PROD=True)
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_for_mobile_merge_request_level1_with_mobile_identity_confirmed(self, _):
        national_code = '0010000000'
        mobile = '09121111111'
        Settings.set('finnotech_verification_api_token', 'XXX')
        responses.get(
            url=f'https://apibeta.finnotech.ir/mpg/v2/clients/nobitex/shahkar/verify?'
            f'nationalCode={national_code}&mobile={mobile}',
            json={
                'trackId': 'b14bade6-77a3-4d62-9f5a-9a46af700dce',
                'result': {
                    'isValid': True,
                },
                'status': 'DONE',
            },
            status=200,
        )

        self._change_parameters_in_object(
            self.users[0],
            {
                'user_type': User.USER_TYPES.level1,
                'email': None,
                'mobile': '09121111112',
                'national_code': national_code,
            },
        )
        self._change_parameters_in_object(
            self.users[0].get_verification_profile(),
            {'mobile_confirmed': True, 'mobile_identity_confirmed': True},
        )
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com', 'mobile': mobile},
        )
        response = self._post_request(data={'mobile': mobile})
        data = self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.requested: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
            },
            user=self.users[0],
        )
        self._check_change_request(
            data,
            UserEvent(
                user=self.users[0],
                action=UserEvent.ACTION_CHOICES.user_merge,
                action_type=UserEvent.USER_MERGE_ACTION_TYPES.requested,
            ),
            UserOTP(
                user=self.users[0],
                otp_type=UserOTP.OTP_TYPES.mobile,
                otp_usage=UserOTP.OTP_Usage.user_merge,
                otp_status=UserOTP.OTP_STATUS.new,
            ),
        )
        self._check_user_sms(
            self.users[0],
            UserSms(
                user=self.users[0],
                tp=UserSms.TYPES.user_merge,
                to='09121111111',
                template=UserSms.TEMPLATES.user_merge_otp,
            ),
        )

    @patch('exchange.accounts.signals.schedule_send_sms_task_and_save_task_id', new_callable=MagicMock)
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_check_sms_style(self, _, mock_send_sms):
        def send_sms_mock(sms):
            task_send_user_sms(sms.id)

        mock_send_sms.side_effect = send_sms_mock

        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.level0, 'mobile': None})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com', 'mobile': '09121111111'},
        )
        response = self._post_request(data={'mobile': '09121111111'})
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        otp = UserSms.objects.filter(user=self.users[0]).last().text.split('\n')[1]
        message = Notification.objects.filter(user=self.users[0]).order_by('-created_at').first().message
        message = message.split('شبیه‌سازی ارسال پیامک: ')[1]
        assert message == (
            'هشدار نوبیتکس!'
            '\n'
            'کد امنیتی برای تایید ادغام شماره تماس شما با حساب زیر:'
            '\n'
            '0912***1111'
            '\n'
            'کد تایید ادغام:'
            '\n' + otp
        )

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_user_reaches_max_merge_requests(self, send_email, _):
        for i in range(3):
            user = User.objects.create_user(
                username=f'testalikafytest{i}',
                email=f'test{i}@nobitex.net',
                user_type=User.USER_TYPES.level0,
            )
            UserMergeRequest.objects.create(
                main_user=self.users[0],
                second_user=user,
                status=UserMergeRequest.STATUS.accepted,
                merge_by=UserMergeRequest.MERGE_BY.email,
                merged_at=ir_now() - datetime.timedelta(days=i),
            )

        # default max number of merge request is 3
        User.objects.create_user(username='testalikafytest', email='test@ali.kafy')
        response = self._post_request(data={'email': 'test@ali.kafy'})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == {
            'code': 'MaxMergeRequestExceededError',
            'message': 'User has exceeded the maximum allowed merge requests.',
            'status': 'failed',
        }

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_user_reaches_daily_max_merge_requests(self, send_email, _):
        UserMergeRequest.objects.create(
            main_user=self.users[0],
            second_user=self.users[1],
            status=UserMergeRequest.STATUS.accepted,
            merge_by=UserMergeRequest.MERGE_BY.email,
            merged_at=get_earliest_time(ir_now()),
        )

        # default daily max number of merge request is 1
        User.objects.create_user(username='testalikafytest', email='test@ali.kafy')
        response = self._post_request(data={'email': 'test@ali.kafy'})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == {
            'code': 'MaxMergeRequestExceededError',
            'message': 'User has exceeded the maximum allowed merge requests.',
            'status': 'failed',
        }


class VerifyMergeRequestTests(MergeTests):
    URL = '/users/verify-merge-request'

    def test_parameter_api(self):
        response = self._post_request()
        self._check_response(
            response,
            status.HTTP_400_BAD_REQUEST,
            'failed',
            'ParseError',
            'Missing string value',
        )

    def test_for_email_main_account_user_level_failed(self):
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.verified, 'email': None})
        self._change_parameters_in_object(self.users[1], {'email': '202@gmail.com'})
        UserMergeRequest.objects.create(
            status=UserMergeRequest.STATUS.email_otp_sent,
            merge_by=UserMergeRequest.MERGE_BY.email,
            main_user=self.users[0],
            second_user=self.users[1],
        )
        response = self._post_request(data={'otp': '123'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'IncompatibleUserLevelError',
            'User has not allowed request: Main Account level is too high',
        )

    def test_for_email_second_account_user_level(self):
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.level1, 'email': None})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level1, 'email': '202@gmail.com'},
        )
        UserMergeRequest.objects.create(
            status=UserMergeRequest.STATUS.email_otp_sent,
            merge_by=UserMergeRequest.MERGE_BY.email,
            main_user=self.users[0],
            second_user=self.users[1],
        )
        response = self._post_request(data={'otp': '123'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'IncompatibleUserLevelError',
            'User has not allowed request: Second Account level is too high',
        )

    def test_for_email_low_level_user_to_high_level_user(self):
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.blocked, 'email': None})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com'},
        )
        UserMergeRequest.objects.create(
            status=UserMergeRequest.STATUS.email_otp_sent,
            merge_by=UserMergeRequest.MERGE_BY.email,
            main_user=self.users[0],
            second_user=self.users[1],
        )
        response = self._post_request(data={'otp': '123'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'IncompatibleUserLevelError',
            'User has not allowed request: Main account level is too low',
        )

    def test_for_email_user_has_transactions(self):
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.level1, 'email': None})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com'},
        )
        self._charge_wallet(self.users[1], Currencies.rls)
        UserMergeRequest.objects.create(
            status=UserMergeRequest.STATUS.email_otp_sent,
            merge_by=UserMergeRequest.MERGE_BY.email,
            main_user=self.users[0],
            second_user=self.users[1],
        )
        response = self._post_request(data={'otp': '123'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'HasTransactionError',
            'User has transaction.',
        )

    def test_for_email_user_has_referral(self):
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.level1, 'email': None})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com'},
        )
        self._create_referral_program(self.users[1])
        UserMergeRequest.objects.create(
            status=UserMergeRequest.STATUS.email_otp_sent,
            merge_by=UserMergeRequest.MERGE_BY.email,
            main_user=self.users[0],
            second_user=self.users[1],
        )
        response = self._post_request(data={'otp': '123'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'HasReferralProgramError',
            'User has referral program.',
        )

    def test_for_email_check_need_approval_merge_request(self):
        UserMergeRequest.objects.create(
            status=UserMergeRequest.STATUS.need_approval,
            merge_by=UserMergeRequest.MERGE_BY.email,
            main_user=self.users[0],
            second_user=self.users[1],
        )
        UserMergeRequest.objects.create(
            status=UserMergeRequest.STATUS.email_otp_sent,
            merge_by=UserMergeRequest.MERGE_BY.email,
            main_user=self.users[0],
            second_user=self.users[1],
        )
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.level1, 'email': None})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com'},
        )
        response = self._post_request(data={'otp': '123'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'HasActiveMergeRequestError',
            'User has active merge request.',
        )

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_for_email_otp_not_verified(self, _):
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.level1, 'email': None})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com'},
        )
        # initiate request
        response = self._post_request(CreateMergeRequestTests.URL, data={'email': '202@gmail.com'})
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        # verify otp
        response = self._post_request(data={'otp': 'XXX'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'OTPVerificationError',
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.requested: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
            },
            user=self.users[0],
        )
        self._check_change_request(
            None,
            None,
            UserOTP(
                user=self.users[0],
                otp_type=UserOTP.OTP_TYPES.email,
                otp_usage=UserOTP.OTP_Usage.user_merge,
                otp_status=UserOTP.OTP_STATUS.new,
            ),
        )

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_for_email_otp_verified(self, send_email, _):
        MockEmail.flush()
        send_email.side_effect = MockEmail.get_mock_send_email()

        self._change_parameters_in_object(
            self.users[0], {'user_type': User.USER_TYPES.level1, 'email': None, 'mobile': '09120000000'}
        )
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com'},
        )
        # initiate request
        response = self._post_request(CreateMergeRequestTests.URL, data={'email': '202@gmail.com'})
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        # verify otp
        otp = MockEmail.all_mock_emails[-1].data['otp']
        response = self._post_request(data={'otp': otp})
        data = self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.requested: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 1,
            },
            user=self.users[0],
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 1,
            },
            user=self.users[1],
        )
        self._check_change_request(
            data,
            UserEvent(
                user=self.users[0],
                action=UserEvent.ACTION_CHOICES.user_merge,
                action_type=UserEvent.USER_MERGE_ACTION_TYPES.accepted,
            ),
            UserOTP(
                user=self.users[0],
                otp_type=UserOTP.OTP_TYPES.email,
                otp_usage=UserOTP.OTP_Usage.user_merge,
                otp_status=UserOTP.OTP_STATUS.used,
            ),
        )

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_for_email_otp_retry_verified(self, send_email, _):
        MockEmail.flush()
        send_email.side_effect = MockEmail.get_mock_send_email()

        self._change_parameters_in_object(
            self.users[0], {'user_type': User.USER_TYPES.level1, 'email': None, 'mobile': '09120000000'}
        )
        self._change_parameters_in_object(
            self.users[0].get_verification_profile(),
            {'mobile_confirmed': True, 'mobile_identity_confirmed': True, 'email_confirmed': False},
        )
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com'},
        )
        # initiate request
        response = self._post_request(CreateMergeRequestTests.URL, data={'email': '202@gmail.com'})
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        # verify with wrong otp
        otp = MockEmail.all_mock_emails[-1].data['otp']
        response = self._post_request(data={'otp': 'XXX'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.requested: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
            },
            user=self.users[0],
        )
        response = self._post_request(url='/otp/request', data={'type': 'email', 'usage': 'merge'})
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        assert MockEmail.all_mock_emails[-1].data['otp'] != otp
        assert UserOTP.objects.filter(user=self.users[0], code=otp).last().otp_status == UserOTP.OTP_STATUS.disabled

        # verify new otp
        otp = MockEmail.all_mock_emails[-1].data['otp']
        response = self._post_request(data={'otp': otp})
        data = self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.requested: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 1,
            },
            user=self.users[0],
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 1,
            },
            user=self.users[1],
        )
        self._check_change_request(
            data,
            UserEvent(
                user=self.users[0],
                action=UserEvent.ACTION_CHOICES.user_merge,
                action_type=UserEvent.USER_MERGE_ACTION_TYPES.accepted,
            ),
            UserOTP(
                user=self.users[0],
                otp_type=UserOTP.OTP_TYPES.email,
                otp_usage=UserOTP.OTP_Usage.user_merge,
                otp_status=UserOTP.OTP_STATUS.used,
            ),
        )

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_for_mobile_otp_not_verified_level0_with_level0_without_mobile_number(self, _):
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.level0, 'mobile': None})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com', 'mobile': '09121111111'},
        )
        # initiate request
        response = self._post_request(CreateMergeRequestTests.URL, data={'mobile': '09121111111'})
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        # verify otp
        response = self._post_request(data={'otp': 'XXX'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
            'OTPVerificationError',
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.requested: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
            },
            user=self.users[0],
        )
        self._check_change_request(
            None,
            None,
            UserOTP(
                user=self.users[0],
                otp_type=UserOTP.OTP_TYPES.mobile,
                otp_usage=UserOTP.OTP_Usage.user_merge,
                otp_status=UserOTP.OTP_STATUS.new,
            ),
        )

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_for_mobile_otp_verified_level0_with_level0_without_mobile_number(self, _):
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.level0, 'mobile': None})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com', 'mobile': '09121111111'},
        )
        # initiate request
        response = self._post_request(CreateMergeRequestTests.URL, data={'mobile': '09121111111'})
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        # verify otp
        otp = UserSms.objects.filter(user=self.users[0]).last().text.split('\n')[1]
        response = self._post_request(data={'otp': otp})
        data = self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.requested: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 1,
            },
            user=self.users[0],
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 1,
            },
            user=self.users[1],
        )
        self._check_change_request(
            data,
            UserEvent(
                user=self.users[0],
                action=UserEvent.ACTION_CHOICES.user_merge,
                action_type=UserEvent.USER_MERGE_ACTION_TYPES.accepted,
            ),
            UserOTP(
                user=self.users[0],
                otp_type=UserOTP.OTP_TYPES.mobile,
                otp_usage=UserOTP.OTP_Usage.user_merge,
                otp_status=UserOTP.OTP_STATUS.used,
            ),
        )

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_for_mobile_otp_retry_verified_level0_with_level0_without_mobile_number(self, _):
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.level0, 'mobile': None})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com', 'mobile': '09121111111'},
        )
        # initiate request
        response = self._post_request(CreateMergeRequestTests.URL, data={'mobile': '09121111111'})
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        # verify with wrong otp
        otp = UserSms.objects.filter(user=self.users[0]).last().text.split('\n')[1]
        response = self._post_request(data={'otp': 'XXX'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.requested: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
            },
            user=self.users[0],
        )
        response = self._post_request(url='/otp/request', data={'type': 'mobile', 'usage': 'merge'})
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        new_otp = UserSms.objects.filter(user=self.users[0]).last().text.split('\n')[1]
        assert new_otp != otp
        assert UserOTP.objects.filter(user=self.users[0], code=otp).last().otp_status == UserOTP.OTP_STATUS.disabled

        # verify new otp
        response = self._post_request(data={'otp': new_otp})
        data = self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.requested: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 1,
            },
            user=self.users[0],
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 1,
            },
            user=self.users[1],
        )
        self._check_change_request(
            data,
            UserEvent(
                user=self.users[0],
                action=UserEvent.ACTION_CHOICES.user_merge,
                action_type=UserEvent.USER_MERGE_ACTION_TYPES.accepted,
            ),
            UserOTP(
                user=self.users[0],
                otp_type=UserOTP.OTP_TYPES.mobile,
                otp_usage=UserOTP.OTP_Usage.user_merge,
                otp_status=UserOTP.OTP_STATUS.used,
            ),
        )

    @responses.activate
    @override_settings(IS_PROD=True)
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_for_mobile_otp_verified_level1_with_mobile_identity_confirmed(self, send_email, _):
        send_email.side_effect = MockEmail.get_mock_send_email()
        national_code = '0010000000'
        mobile = '09121111111'
        Settings.set('finnotech_verification_api_token', 'XXX')
        responses.get(
            url=f'https://apibeta.finnotech.ir/mpg/v2/clients/nobitex/shahkar/verify?'
            f'nationalCode={national_code}&mobile={mobile}',
            json={
                'trackId': 'b14bade6-77a3-4d62-9f5a-9a46af700dce',
                'result': {
                    'isValid': True,
                },
                'status': 'DONE',
            },
            status=200,
        )

        self._change_parameters_in_object(
            self.users[0],
            {
                'user_type': User.USER_TYPES.level1,
                'email': None,
                'mobile': '09121111112',
                'national_code': national_code,
            },
        )
        self._change_parameters_in_object(
            self.users[0].get_verification_profile(),
            {'mobile_confirmed': True, 'mobile_identity_confirmed': True},
        )
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com', 'mobile': mobile},
        )
        # initiate request
        response = self._post_request(CreateMergeRequestTests.URL, data={'mobile': '09121111111'})
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.requested: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
            },
            user=self.users[0],
        )
        # verify otp new mobile
        sms = UserSms.objects.filter(user=self.users[0]).last()
        otp = sms.text.split('\n')[1]
        assert sms.to == self.users[1].mobile
        response = self._post_request(data={'otp': otp})
        data = self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.requested: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
            },
            user=self.users[0],
        )
        self._check_change_request(
            data,
            UserEvent(
                user=self.users[0],
                action=UserEvent.ACTION_CHOICES.user_merge,
                action_type=UserEvent.USER_MERGE_ACTION_TYPES.requested,
            ),
            UserOTP(
                user=self.users[0],
                otp_type=UserOTP.OTP_TYPES.mobile,
                otp_usage=UserOTP.OTP_Usage.user_merge,
                otp_status=UserOTP.OTP_STATUS.new,
            ),
        )
        # verify otp old mobile
        sms = UserSms.objects.filter(user=self.users[0]).last()
        otp = sms.text.split('\n')[1]
        assert sms.to == self.users[0].mobile
        response = self._post_request(data={'otp': otp})
        data = self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.requested: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 1,
            },
            user=self.users[0],
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 1,
            },
            user=self.users[1],
        )
        self._check_change_request(
            data,
            UserEvent(
                user=self.users[0],
                action=UserEvent.ACTION_CHOICES.user_merge,
                action_type=UserEvent.USER_MERGE_ACTION_TYPES.accepted,
            ),
            UserOTP(
                user=self.users[0],
                otp_type=UserOTP.OTP_TYPES.mobile,
                otp_usage=UserOTP.OTP_Usage.user_merge,
                otp_status=UserOTP.OTP_STATUS.used,
            ),
        )

    @responses.activate
    @override_settings(IS_PROD=True)
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_for_mobile_retry_otp_verified_level1_with_mobile_identity_confirmed(self, send_email, _):
        send_email.side_effect = MockEmail.get_mock_send_email()
        national_code = '0010000000'
        mobile = '09121111111'
        Settings.set('finnotech_verification_api_token', 'XXX')
        responses.get(
            url=f'https://apibeta.finnotech.ir/mpg/v2/clients/nobitex/shahkar/verify?'
            f'nationalCode={national_code}&mobile={mobile}',
            json={
                'trackId': 'b14bade6-77a3-4d62-9f5a-9a46af700dce',
                'result': {
                    'isValid': True,
                },
                'status': 'DONE',
            },
            status=200,
        )

        self._change_parameters_in_object(
            self.users[0],
            {
                'user_type': User.USER_TYPES.level1,
                'email': None,
                'mobile': '09121111112',
                'national_code': national_code,
            },
        )
        self._change_parameters_in_object(
            self.users[0].get_verification_profile(),
            {'mobile_confirmed': True, 'mobile_identity_confirmed': True},
        )
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com', 'mobile': mobile},
        )
        # initiate request
        response = self._post_request(CreateMergeRequestTests.URL, data={'mobile': '09121111111'})
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.requested: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
            },
            user=self.users[0],
        )
        # verify otp new mobile
        sms = UserSms.objects.filter(user=self.users[0]).last()
        otp = sms.text
        assert sms.to == self.users[1].mobile
        # verify with wrong otp
        response = self._post_request(data={'otp': 'XXX'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.requested: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
            },
            user=self.users[0],
        )
        response = self._post_request(url='/otp/request', data={'type': 'mobile', 'usage': 'merge'})
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        sms = UserSms.objects.filter(user=self.users[0]).last()
        otp = sms.text.split('\n')[1]
        assert sms.to == self.users[1].mobile
        # verify otp
        response = self._post_request(data={'otp': otp})
        data = self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.requested: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
            },
            user=self.users[0],
        )
        self._check_change_request(
            data,
            UserEvent(
                user=self.users[0],
                action=UserEvent.ACTION_CHOICES.user_merge,
                action_type=UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp,
            ),
            UserOTP(
                user=self.users[0],
                otp_type=UserOTP.OTP_TYPES.mobile,
                otp_usage=UserOTP.OTP_Usage.user_merge,
                otp_status=UserOTP.OTP_STATUS.new,
            ),
        )
        # verify otp old mobile
        sms = UserSms.objects.filter(user=self.users[0]).last()
        otp = sms.text
        assert sms.to == self.users[0].mobile
        # verify with wrong otp
        response = self._post_request(data={'otp': 'XXX'})
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            'failed',
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.requested: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
            },
            user=self.users[0],
        )
        response = self._post_request(url='/otp/request', data={'type': 'mobile', 'usage': 'merge'})
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        sms = UserSms.objects.filter(user=self.users[0]).last()
        otp = sms.text.split('\n')[1]
        assert sms.to == self.users[0].mobile
        # verify otp old mobile
        response = self._post_request(data={'otp': otp})
        data = self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.requested: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 1,
            },
            user=self.users[0],
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 1,
            },
            user=self.users[1],
        )
        self._check_change_request(
            data,
            UserEvent(
                user=self.users[0],
                action=UserEvent.ACTION_CHOICES.user_merge,
                action_type=UserEvent.USER_MERGE_ACTION_TYPES.accepted,
            ),
            UserOTP(
                user=self.users[0],
                otp_type=UserOTP.OTP_TYPES.mobile,
                otp_usage=UserOTP.OTP_Usage.user_merge,
                otp_status=UserOTP.OTP_STATUS.used,
            ),
        )

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'critical': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_send_email_on_retry_otp(self):
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.level1, 'email': None})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com'},
        )
        Settings.set_dict('email_whitelist', [self.users[1].email])
        call_command('update_email_templates')
        UserMergeRequest.objects.create(
            status=UserMergeRequest.STATUS.email_otp_sent,
            merge_by=UserMergeRequest.MERGE_BY.email,
            main_user=self.users[0],
            second_user=self.users[1],
        )
        response = self._post_request(url='/otp/request', data={'type': 'email', 'usage': 'merge'})
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        with patch('django.db.connection.close'):
            call_command('send_queued_mail')

    @patch('exchange.accounts.merge.MergeManager._check_merge_request_limit')
    def test_allow_multiple_merge_requests_by_same_email(self, mock_check_merge_request_limit):
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.level0, 'mobile': None})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com', 'mobile': '09121111111'},
        )
        # initiate request
        response = self._post_request(CreateMergeRequestTests.URL, data={'mobile': '09121111111'})
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        # verify otp
        otp = UserSms.objects.filter(user=self.users[0]).last().text.split('\n')[1]
        response = self._post_request(data={'otp': otp})
        assert response.status_code == status.HTTP_200_OK
        test_user = User.objects.create_user(
            'testalikafytest', email='202@gmail.com', mobile='09121111111', user_type=User.USER_TYPES.level0
        )
        self.users[0].auth_token = Token.objects.create(user=self.users[0], key='124536755')
        self.users[0].save()
        self._set_client_credentials(self.users[0].auth_token.key)
        response = self._post_request(CreateMergeRequestTests.URL, data={'mobile': '09121111111'})
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        otp = UserSms.objects.filter(user=self.users[0]).last().text.split('\n')[1]
        response = self._post_request(data={'otp': otp})
        self._check_response(
            response,
            status.HTTP_200_OK,
            'ok',
        )
        test_user.refresh_from_db()
        assert test_user.username


class MergeTaskTests(MergeTests):
    def _create_merge_request(
        self,
        merge_status: int = UserMergeRequest.STATUS.need_approval,
        merge_by: int = UserMergeRequest.MERGE_BY.email,
        main_user: Optional[User] = None,
        second_user: Optional[User] = None,
    ):
        return UserMergeRequest.objects.create(
            status=merge_status,
            merge_by=merge_by,
            main_user=main_user or self.users[0],
            second_user=second_user or self.users[1],
        )

    def _check_task_result(self, request: UserMergeRequest, merge_request: UserMergeRequest):
        assert request.description == merge_request.description
        assert request.merged_at == merge_request.merged_at
        assert request.status == merge_request.status

    def _check_verification_profile(self, main_user: User, attrs: Dict[str, bool]):
        verification_profile = main_user.get_verification_profile()
        for key, value in attrs.items():
            assert getattr(verification_profile, key) == value

    def _check_users_data_after_merge(
        self,
        user: User,
        user_data: User,
        verification_profile_data: Optional[Dict[str, bool]] = None,
    ):
        assert user.username == user_data.username
        assert user.email == user_data.email
        assert user.is_active == user.is_active
        assert user.mobile == user_data.mobile
        if verification_profile_data:
            self._check_verification_profile(user, verification_profile_data)

    def _check_merge_tag(self):
        merge_tag = Tag.get_builtin_tag('حساب ادغام شده')
        assert not UserTag.objects.filter(user=self.users[0], tag=merge_tag).exists()
        assert UserTag.objects.filter(user=self.users[1], tag=merge_tag).exists()

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_task_user_level_error(self, _):
        request = self._create_merge_request()
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.verified, 'email': None})
        self._change_parameters_in_object(self.users[1], {'email': '202@gmail.com'})
        task_user_merge(request.id)
        request.refresh_from_db()
        self._check_task_result(
            request,
            UserMergeRequest(
                status=UserMergeRequest.STATUS.rejected,
                merged_at=None,
                description=(
                    'سطح حساب‌های کاربری انتخاب شده، مناسب عملیات ادغام نیست: '
                    'حساب مرج کننده سطحی بالاتر از انتظار دارد.'
                ),
            ),
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.rejected: 1,
            },
            user=self.users[0],
        )

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_task_transaction_error(self, _):
        request = self._create_merge_request()
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.level1, 'email': None})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com'},
        )
        self._charge_wallet(self.users[1], Currencies.rls)
        task_user_merge(request.id)
        request.refresh_from_db()
        self._check_task_result(
            request,
            UserMergeRequest(
                status=UserMergeRequest.STATUS.rejected,
                merged_at=None,
                description='حساب مرج شونده دارای تراکنش است.',
            ),
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.rejected: 1,
            },
            user=self.users[0],
        )

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_task_referral_error(self, _):
        request = self._create_merge_request()
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.level1, 'email': None})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com'},
        )
        self._create_referral_program(self.users[1])
        task_user_merge(request.id)
        request.refresh_from_db()
        self._check_task_result(
            request,
            UserMergeRequest(
                status=UserMergeRequest.STATUS.rejected,
                merged_at=None,
                description='حساب مرج شونده کد ریفرال ساخته است.',
            ),
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.rejected: 1,
            },
            user=self.users[0],
        )

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_active_merge_request_error(self, _):
        self._create_merge_request(main_user=self.users[1], second_user=self.users[0])
        request = self._create_merge_request()
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.level1, 'email': None})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com'},
        )
        task_user_merge(request.id)
        request.refresh_from_db()
        self._check_task_result(
            request,
            UserMergeRequest(
                status=UserMergeRequest.STATUS.rejected,
                merged_at=None,
                description='حساب مرج شونده، درخواست فعالی برای ادغام حسابش دارد.',
            ),
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.rejected: 1,
            },
            user=self.users[0],
        )

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_check_mobile_identity_error(self, _):
        request = self._create_merge_request(merge_by=UserMergeRequest.MERGE_BY.mobile)
        self._change_parameters_in_object(
            self.users[0],
            {'user_type': User.USER_TYPES.level1, 'email': None, 'mobile': '09121111112'},
        )
        self._change_parameters_in_object(
            self.users[0].get_verification_profile(),
            {'mobile_confirmed': True, 'mobile_identity_confirmed': True},
        )
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com', 'mobile': '09121111111'},
        )
        task_user_merge(request.id)
        request.refresh_from_db()
        self._check_task_result(
            request,
            UserMergeRequest(
                status=UserMergeRequest.STATUS.rejected,
                merged_at=None,
                description='بررسی به نام بودن شماره‌ی تماس کاربر با خطا مواجه شده است:InadequateInformation',
            ),
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.fail_identity: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.rejected: 1,
            },
            user=self.users[0],
        )

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_check_email_error(self, _):
        request = self._create_merge_request()
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.level1, 'email': '2@gmail.com'})
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com'},
        )
        task_user_merge(request.id)
        request.refresh_from_db()
        self._check_task_result(
            request,
            UserMergeRequest(
                status=UserMergeRequest.STATUS.rejected,
                merged_at=None,
                description='حساب مرج کننده دارای ایمیل است.',
            ),
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.rejected: 1,
            },
            user=self.users[0],
        )

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_same_user_error(self, _):
        request = self._create_merge_request(main_user=self.users[0], second_user=self.users[0])
        self._change_parameters_in_object(self.users[0], {'user_type': User.USER_TYPES.level0, 'email': '2@gmail.com'})
        task_user_merge(request.id)
        request.refresh_from_db()
        self._check_task_result(
            request,
            UserMergeRequest(
                status=UserMergeRequest.STATUS.rejected,
                merged_at=None,
                description='حساب مرج کننده و مرج شونده نباید یکسان باشد.',
            ),
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.rejected: 1,
            },
            user=self.users[0],
        )

    @patch('exchange.accounts.merge.merge_manager.random.randint', return_value=98)
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.accounts.models.now')
    def test_accepted_merge_by_email(self, mock_timezone, _, send_email, moke_rand):
        dt = datetime.datetime(2023, 7, 18, 9, 47, 11, 453217, tzinfo=datetime.timezone.utc)
        mock_timezone.return_value = dt
        request = self._create_merge_request()
        self._change_parameters_in_object(
            self.users[0],
            {'user_type': User.USER_TYPES.level1, 'email': None, 'mobile': '09121111111', 'username': '09121111111'},
        )
        self._change_parameters_in_object(
            self.users[0].get_verification_profile(),
            {'email_confirmed': False},
        )
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com', 'username': '202@gmail.com'},
        )
        self._change_parameters_in_object(
            self.users[1].get_verification_profile(),
            {'email_confirmed': True},
        )
        description = MergeRequestStatusChangedContext.from_users(
            main_user=self.users[0],
            second_user=self.users[1],
        ).json

        task_user_merge(request.id)
        request.refresh_from_db()
        self._check_task_result(
            request,
            UserMergeRequest(
                status=UserMergeRequest.STATUS.accepted,
                merged_at=dt,
                description=description,
            ),
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.rejected: 0,
            },
            user=self.users[0],
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.need_approval: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 1,
            },
            user=self.users[1],
        )
        for user in self.users:
            user.refresh_from_db()

        self._check_users_data_after_merge(
            self.users[0],
            User(username='09121111111', mobile='09121111111', email='202@gmail.com', is_active=True),
            {'email_confirmed': True},
        )
        self._check_users_data_after_merge(
            self.users[1],
            User(username='202&gmail.com_98@merge.ntx.ir', email='202&gmail.com_98@merge.ntx.ir', is_active=False),
        )
        self._check_merge_tag()

    @patch('exchange.accounts.merge.merge_manager.random.randint', return_value=98)
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.accounts.models.now')
    @responses.activate
    @override_settings(IS_PROD=True)
    def test_accepted_merge_by_mobile_without_email(self, mock_timezone, _, send_email, mock_rand):
        dt = datetime.datetime(2023, 7, 18, 9, 47, 11, 453217, tzinfo=datetime.timezone.utc)
        mock_timezone.return_value = dt

        national_code = '0010000000'
        mobile = '09121111111'
        Settings.set('finnotech_verification_api_token', 'XXX')
        responses.get(
            url=f'https://apibeta.finnotech.ir/mpg/v2/clients/nobitex/shahkar/verify?'
            f'nationalCode={national_code}&mobile={mobile}',
            json={
                'trackId': 'b14bade6-77a3-4d62-9f5a-9a46af700dce',
                'result': {
                    'isValid': True,
                },
                'status': 'DONE',
            },
            status=200,
        )

        request = self._create_merge_request(merge_by=UserMergeRequest.MERGE_BY.mobile)
        self._change_parameters_in_object(
            self.users[0],
            {
                'user_type': User.USER_TYPES.level1,
                'email': None,
                'mobile': '09121111112',
                'national_code': national_code,
                'username': '09121111112',
            },
        )
        self._change_parameters_in_object(
            self.users[0].get_verification_profile(),
            {'mobile_confirmed': True, 'mobile_identity_confirmed': True},
        )
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com', 'mobile': mobile, 'username': mobile},
        )
        description = MergeRequestStatusChangedContext.from_users(
            main_user=self.users[0],
            second_user=self.users[1],
        ).json

        task_user_merge(request.id)
        request.refresh_from_db()
        self._check_task_result(
            request,
            UserMergeRequest(
                status=UserMergeRequest.STATUS.accepted,
                merged_at=dt,
                description=description,
            ),
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.rejected: 0,
            },
            user=self.users[0],
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 1,
            },
            user=self.users[1],
        )
        for user in self.users:
            user.refresh_from_db()

        self._check_users_data_after_merge(
            self.users[0],
            User(username=mobile, mobile=mobile, email=(mobile + '@mobile.ntx.ir'), is_active=True),
            {'mobile_confirmed': True, 'mobile_identity_confirmed': True},
        )
        self._check_users_data_after_merge(
            self.users[1],
            User(username=(mobile + '_98@merge.ntx.ir'), email=(mobile + '_98@merge.ntx.ir'), is_active=False),
        )
        self._check_merge_tag()

    @patch('exchange.accounts.merge.merge_manager.random.randint', return_value=98)
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.accounts.models.now')
    @responses.activate
    @override_settings(IS_PROD=True)
    def test_accepted_merge_by_mobile_with_email(self, mock_timezone, _, send_email, mock_rand):
        dt = datetime.datetime(2023, 7, 18, 9, 47, 11, 453217, tzinfo=datetime.timezone.utc)
        mock_timezone.return_value = dt

        national_code = '0010000000'
        mobile = '09121111111'
        Settings.set('finnotech_verification_api_token', 'XXX')
        responses.get(
            url=f'https://apibeta.finnotech.ir/mpg/v2/clients/nobitex/shahkar/verify?'
            f'nationalCode={national_code}&mobile={mobile}',
            json={
                'trackId': 'b14bade6-77a3-4d62-9f5a-9a46af700dce',
                'result': {
                    'isValid': True,
                },
                'status': 'DONE',
            },
            status=200,
        )

        request = self._create_merge_request(merge_by=UserMergeRequest.MERGE_BY.mobile)
        self._change_parameters_in_object(
            self.users[0],
            {
                'user_type': User.USER_TYPES.level1,
                'email': '201@gmail.com',
                'mobile': '09121111112',
                'national_code': national_code,
                'username': '09121111112',
            },
        )
        self._change_parameters_in_object(
            self.users[0].get_verification_profile(),
            {'mobile_confirmed': True, 'mobile_identity_confirmed': True, 'email_confirmed': False},
        )
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com', 'mobile': mobile, 'username': mobile},
        )
        description = MergeRequestStatusChangedContext.from_users(
            main_user=self.users[0],
            second_user=self.users[1],
        ).json

        task_user_merge(request.id)
        request.refresh_from_db()
        self._check_task_result(
            request,
            UserMergeRequest(
                status=UserMergeRequest.STATUS.accepted,
                merged_at=dt,
                description=description,
            ),
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.rejected: 0,
            },
            user=self.users[0],
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 1,
            },
            user=self.users[1],
        )
        for user in self.users:
            user.refresh_from_db()

        self._check_users_data_after_merge(
            self.users[0],
            User(username=mobile, mobile=mobile, email='201@gmail.com', is_active=True),
            {'mobile_confirmed': True, 'mobile_identity_confirmed': True},
        )
        self._check_users_data_after_merge(
            self.users[1],
            User(username=(mobile + '_98@merge.ntx.ir'), email=(mobile + '_98@merge.ntx.ir'), is_active=False),
        )
        self._check_merge_tag()

    @patch('exchange.accounts.merge.merge_manager.random.randint', return_value=98)
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.accounts.models.now')
    @override_settings(IS_PROD=True)
    def test_accepted_merge_by_mobile_level0(self, mock_timezone, _, send_email, mock_rand):
        dt = datetime.datetime(2023, 7, 18, 9, 47, 11, 453217, tzinfo=datetime.timezone.utc)
        mock_timezone.return_value = dt

        mobile = '09121111111'
        request = self._create_merge_request(merge_by=UserMergeRequest.MERGE_BY.mobile)
        self._change_parameters_in_object(
            self.users[0],
            {
                'user_type': User.USER_TYPES.level0,
                'email': '201@gmail.com',
                'username': '201@gmail.com',
            },
        )
        self._change_parameters_in_object(
            self.users[0].get_verification_profile(),
            {'mobile_confirmed': False, 'mobile_identity_confirmed': False, 'email_confirmed': True},
        )
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com', 'mobile': mobile, 'username': mobile},
        )
        self._change_parameters_in_object(
            self.users[1].get_verification_profile(),
            {'mobile_confirmed': True, 'email_confirmed': True},
        )
        description = MergeRequestStatusChangedContext.from_users(
            main_user=self.users[0],
            second_user=self.users[1],
        ).json

        task_user_merge(request.id)
        request.refresh_from_db()
        self._check_task_result(
            request,
            UserMergeRequest(
                status=UserMergeRequest.STATUS.accepted,
                merged_at=dt,
                description=description,
            ),
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.rejected: 0,
            },
            user=self.users[0],
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 1,
            },
            user=self.users[1],
        )
        for user in self.users:
            user.refresh_from_db()

        self._check_users_data_after_merge(
            self.users[0],
            User(username='201@gmail.com', mobile=mobile, email='201@gmail.com', is_active=True),
            {'mobile_confirmed': True, 'mobile_identity_confirmed': False},
        )
        self._check_users_data_after_merge(
            self.users[1],
            User(username=(mobile + '_98@merge.ntx.ir'), email=(mobile + '_98@merge.ntx.ir'), is_active=False),
        )
        self._check_merge_tag()

    @patch('exchange.base.emailmanager.EmailManager.send_email')
    @patch('exchange.accounts.signals.schedule_send_sms_task_and_save_task_id', new_callable=MagicMock)
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_check_sms_style(self, _, mock_send_sms, __):
        def send_sms_mock(sms):
            task_send_user_sms(sms.id)

        mock_send_sms.side_effect = send_sms_mock
        request = self._create_merge_request(merge_by=UserMergeRequest.MERGE_BY.mobile)
        self._change_parameters_in_object(
            self.users[0],
            {
                'user_type': User.USER_TYPES.level0,
                'email': None,
                'mobile': '09121111112',
                'national_code': '0010000000',
            },
        )
        self._change_parameters_in_object(
            self.users[0].get_verification_profile(),
            {'mobile_confirmed': True, 'mobile_identity_confirmed': True},
        )
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com', 'mobile': '09121111111'},
        )
        self._change_parameters_in_object(
            self.users[1].get_verification_profile(),
            {'mobile_confirmed': True},
        )
        task_user_merge(request.id)
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 1,
                UserEvent.USER_MERGE_ACTION_TYPES.rejected: 0,
            },
            user=self.users[0],
        )
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 1,
            },
            user=self.users[1],
        )
        request.refresh_from_db()
        message = Notification.objects.filter(user=self.users[0]).order_by('-created_at').first().message
        message = message.split('شبیه‌سازی ارسال پیامک: ')[1]
        assert message == (
            'نوبیتکس!'
            '\n'
            'کاربر گرامی ادغام 0912***1111 در حساب 0912***1112 با موفقیت انجام شد.'
            '\n'
            'به منظور افزایش امنیت، برداشت رمزارز در حساب شما ۲۴ساعت محدود می‌شود.'
            '\n'
            'در صورت هرگونه مغایرت با پشتیبانی موضوع را مطرح‌ نمایید.'
        )
        message = Notification.objects.filter(user=self.users[1]).order_by('-created_at').first().message
        message = message.split('شبیه‌سازی ارسال پیامک: ')[1]
        assert message == (
            'نوبیتکس!'
            '\n'
            'کاربر گرامی ادغام 0912***1111 در حساب 0912***1112 با موفقیت انجام شد.'
            '\n'
            'به منظور افزایش امنیت، برداشت رمزارز در حساب شما ۲۴ساعت محدود می‌شود.'
            '\n'
            'در صورت هرگونه مغایرت با پشتیبانی موضوع را مطرح‌ نمایید.'
        )
        assert UserSms.objects.filter(to='09121111112').last().template == UserSms.TEMPLATES.user_merge_successful
        assert UserSms.objects.filter(to='09121111111').last().template == UserSms.TEMPLATES.user_merge_successful
        self._check_verification_profile(self.users[0], {'mobile_confirmed': True, 'mobile_identity_confirmed': True})

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'critical': 'django.core.mail.backends.smtp.EmailBackend'}})
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_send_email_task(self, _):
        self._change_parameters_in_object(
            self.users[0],
            {'user_type': User.USER_TYPES.level1, 'email': None, 'mobile': '09121111111'},
        )
        self._change_parameters_in_object(
            self.users[1],
            {'user_type': User.USER_TYPES.level0, 'email': '202@gmail.com'},
        )
        Settings.set_dict('email_whitelist', [self.users[1].email])
        call_command('update_email_templates')
        request = self._create_merge_request()
        task_user_merge(request.id)
        with patch('django.db.connection.close'):
            call_command('send_queued_mail')


class MergeRejectionTaskTests(MergeTests):
    def _create_merge_request(self):
        return UserMergeRequest.objects.create(
            status=UserMergeRequest.STATUS.need_approval,
            merge_by=UserMergeRequest.MERGE_BY.email,
            main_user=self.users[0],
            second_user=self.users[1],
        )

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_reject_task(self, _):
        request = self._create_merge_request()
        task_reject_merge_request(merge_request_id=request.id, description='رد شده‌است.')
        self._check_user_events(
            items={
                UserEvent.USER_MERGE_ACTION_TYPES.accepted: 0,
                UserEvent.USER_MERGE_ACTION_TYPES.rejected: 1,
            },
            user=self.users[0],
        )
        request.refresh_from_db()
        assert request.description == 'رد شده‌است.'
        assert request.status == UserMergeRequest.STATUS.rejected


class MergeCronTests(MergeTests):
    def _create_merge_request(self):
        return UserMergeRequest.objects.create(
            status=UserMergeRequest.STATUS.email_otp_sent,
            merge_by=UserMergeRequest.MERGE_BY.email,
            main_user=self.users[0],
            second_user=self.users[1],
        )

    def test_cron_uncompleted_request(self):
        request1 = self._create_merge_request()
        request2 = self._create_merge_request()
        request3 = self._create_merge_request()
        request4 = self._create_merge_request()
        request5 = self._create_merge_request()
        requests = [request1, request2, request3, request4]
        UserMergeRequest.objects.filter(pk__in=[req.id for req in requests]).update(
            created_at=ir_now() - datetime.timedelta(minutes=30)
        )

        DeleteUncompletedMergeRequest().run()

        for request in requests:
            request.refresh_from_db()
            assert request.description == 'کدیکبار مصرف منقضی شده است.'
            assert request.status == UserMergeRequest.STATUS.failed

        request5.refresh_from_db()
        assert request5.description == ''
        assert request5.status == UserMergeRequest.STATUS.email_otp_sent
