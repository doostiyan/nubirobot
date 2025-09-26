import datetime
from unittest.mock import Mock, patch

from rest_framework.test import APIClient, APITestCase

from exchange.accounts.models import Notification, User, UserSms


class TestAPIKeyAPIs(APITestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)

        self.user.requires_2fa = True

        self.client = APIClient(
            HTTP_USER_AGENT='Mozilla/5.0',
            HTTP_AUTHORIZATION='Token user201token',
            HTTP_X_TOTP='111111',
        )

        self.user.mobile = '09390909540'
        self.user.save()

        vp = self.user.get_verification_profile()
        vp.email_confirmed = True
        vp.mobile_confirmed = True
        vp.save()

        patcher = patch('exchange.apikey.views.check_user_otp', Mock(return_value=True))
        patcher.start()
        self.addCleanup(patcher.stop)

    def assert_sms_and_send(self, tp: int, count: int):
        uss = UserSms.objects.filter(
            user=self.user,
            tp=tp,
        )

        assert len(uss) == count

        for us in uss:
            us.send()

    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_api_creation_failed(self, send_email_mock):
        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'description': 'a just for testing',
                'permissions': 'READ,TRADE',
                'ipAddressesWhitelist': ['188.121.146.46.'],
            },
            format='json',
        ).json()

        assert response['status'] == 'failed', response
        assert response['code'] == 'ParseError', response
        assert response['message'] == ('ipAddressesWhitelist: value is not a valid IPv4 or IPv6 address')

        assert send_email_mock.call_count == 0

    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_api_creation(self, send_email_mock):
        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'permissions': 'READ,TRADE',
                'ipAddressesWhitelist': ['188.121.146.46'],
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response

        created_at = datetime.datetime.fromisoformat(response['key']['createdAt'][:-1] + '+00:00')

        send_email_mock.assert_called_with(
            email=self.user.email,
            template='apikey/creation',
            data={'email_title': 'ایجاد API Key جدید', 'created_at': created_at},
            priority='high',
        )
        assert send_email_mock.call_count == 1

        self.assert_sms_and_send(
            tp=UserSms.TYPES.api_key_create,
            count=1,
        )

        notification = Notification.objects.filter(user=self.user).order_by('created_at').all()

        assert len(notification) == 3
        assert notification[1].message == 'API Key جدید با موفقیت ایجاد شد. جزئیات را در بخش تنظیمات API مشاهده کنید.'
        assert notification[2].message == (
            'شبیه‌سازی ارسال پیامک: '
            'نوبیتکس: API Key جدید در حساب کاربری شما ایجاد '
            'شد. در صورت عدم تایید، سریعاً به حساب کاربری خود مراجعه نمایید.'
        )

    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_api_creation_and_update_ip(self, send_email_mock):
        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'permissions': 'READ,TRADE',
                'ipAddressesWhitelist': ['188.121.146.46'],
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response

        key = response['key']['key']
        created_at = datetime.datetime.fromisoformat(response['key']['createdAt'][:-1] + '+00:00')

        send_email_mock.assert_called_with(
            email=self.user.email,
            template='apikey/creation',
            data={'email_title': 'ایجاد API Key جدید', 'created_at': created_at},
            priority='high',
        )

        response = self.client.post(
            f'/apikeys/update/{key}',
            data={
                'ipAddressesWhitelist': ['188.121.146.46', '188.121.146.45'],
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response

        updated_at = datetime.datetime.fromisoformat(response['key']['updatedAt'][:-1] + '+00:00')

        send_email_mock.assert_called_with(
            email=self.user.email,
            template='apikey/update',
            data={'email_title': 'ویرایش API Key', 'updated_at': updated_at},
            priority='high',
        )

        self.assert_sms_and_send(
            tp=UserSms.TYPES.api_key_create,
            count=1,
        )

        self.assert_sms_and_send(
            tp=UserSms.TYPES.api_key_update,
            count=1,
        )

        assert send_email_mock.call_count == 2

        notification = Notification.objects.filter(user=self.user).order_by('created_at').all()

        assert len(notification) == 5
        assert notification[1].message == ('API Key جدید با موفقیت ایجاد شد. جزئیات را در بخش تنظیمات API مشاهده کنید.')
        assert notification[2].message == (
            'تغییراتی در یکی از API Keyهای شما اعمال شد. لطفاً صحت آن را ا مراجعه به حساب کاربری خود بررسی کنید.'
        )
        assert notification[3].message == (
            'شبیه‌سازی ارسال پیامک: '
            'نوبیتکس: API Key جدید در حساب کاربری شما ایجاد '
            'شد. در صورت عدم تایید، سریعاً به حساب کاربری خود مراجعه نمایید.'
        )
        assert notification[4].message == (
            'شبیه‌سازی ارسال پیامک: '
            'نوبیتکس: API Key شما ویرایش شد. در صورت مشاهده فعالیت مشکوک، '
            'سریعاً به حساب کاربری خود مراجعه نمایید.'
        )

    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_api_creation_and_update_name(self, send_email_mock):
        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'permissions': 'READ,TRADE',
                'ipAddressesWhitelist': ['188.121.146.46'],
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response

        key = response['key']['key']
        created_at = datetime.datetime.fromisoformat(response['key']['createdAt'][:-1] + '+00:00')

        send_email_mock.assert_called_with(
            email=self.user.email,
            template='apikey/creation',
            data={'email_title': 'ایجاد API Key جدید', 'created_at': created_at},
            priority='high',
        )

        response = self.client.post(
            f'/apikeys/update/{key}',
            data={
                'name': 'newtestkey',
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response

        assert send_email_mock.call_count == 1

        self.assert_sms_and_send(
            tp=UserSms.TYPES.api_key_create,
            count=1,
        )

        self.assert_sms_and_send(
            tp=UserSms.TYPES.api_key_update,
            count=0,
        )

        notification = Notification.objects.filter(user=self.user).order_by('created_at').all()

        assert len(notification) == 3
        assert notification[1].message == ('API Key جدید با موفقیت ایجاد شد. جزئیات را در بخش تنظیمات API مشاهده کنید.')
        assert notification[2].message == (
            'شبیه‌سازی ارسال پیامک: '
            'نوبیتکس: API Key جدید در حساب کاربری شما ایجاد '
            'شد. در صورت عدم تایید، سریعاً به حساب کاربری خود مراجعه نمایید.'
        )

    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_api_creation_with_no_verified_email(self, send_email_mock):
        vp = self.user.get_verification_profile()
        vp.email_confirmed = False
        vp.save()

        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'permissions': 'READ,TRADE',
                'ipAddressesWhitelist': ['188.121.146.46'],
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response

        assert send_email_mock.call_count == 0

    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_api_creation_and_delete(self, send_email_mock):
        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'permissions': 'READ,TRADE',
                'ipAddressesWhitelist': ['188.121.146.46'],
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response

        key = response['key']['key']
        created_at = datetime.datetime.fromisoformat(response['key']['createdAt'][:-1] + '+00:00')

        send_email_mock.assert_called_with(
            email=self.user.email,
            template='apikey/creation',
            data={'email_title': 'ایجاد API Key جدید', 'created_at': created_at},
            priority='high',
        )

        response = self.client.post(
            f'/apikeys/delete/{key}',
            format='json',
        ).json()

        assert response['status'] == 'ok', response

        now = send_email_mock.call_args.kwargs['data']['now']

        send_email_mock.assert_called_with(
            email=self.user.email,
            template='apikey/deletion',
            data={'email_title': 'حذف یک API Key', 'now': now},
            priority='high',
        )

        assert send_email_mock.call_count == 2

        self.assert_sms_and_send(
            tp=UserSms.TYPES.api_key_create,
            count=1,
        )

        self.assert_sms_and_send(
            tp=UserSms.TYPES.api_key_update,
            count=0,
        )

        self.assert_sms_and_send(
            tp=UserSms.TYPES.api_key_delete,
            count=1,
        )

        notification = Notification.objects.filter(user=self.user).order_by('created_at').all()

        assert len(notification) == 5
        assert notification[1].message == ('API Key جدید با موفقیت ایجاد شد. جزئیات را در بخش تنظیمات API مشاهده کنید.')
        assert notification[2].message == (
            'API Key حذف شد. در صورت عدم تایید، لطفاً صحت آن را با مراجعه به حساب کاربری خود بررسی کنید.'
        )
        assert notification[3].message == (
            'شبیه‌سازی ارسال پیامک: '
            'نوبیتکس: API Key جدید در حساب کاربری شما ایجاد '
            'شد. در صورت عدم تایید، سریعاً به حساب کاربری خود مراجعه نمایید.'
        )
        assert notification[4].message == (
            'شبیه‌سازی ارسال پیامک: '
            'نوبیتکس: یک API Key از حساب شما حذف شد. در صورت عدم تایید، '
            'سریعاً به حساب کاربری خود مراجعه نمایید.'
        )

    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_api_creation_and_delete_not_found(self, send_email_mock):
        key = 'bad-key'

        self.client.post(
            f'/apikeys/delete/{key}',
            format='json',
        ).json()

        assert send_email_mock.call_count == 0
