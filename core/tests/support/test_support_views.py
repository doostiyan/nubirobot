import base64

from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, Client

from exchange.accounts.models import User


class CreateNextCallReasonUrl(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.client = Client(
            HTTP_AUTHORIZATION='Token user201token',
        )
        content_type = ContentType.objects.get_or_create(app_label='accounts', model='callrecord')[0]
        Permission.objects.create(codename='access_to_call_reason_api',
                                  name='دسترسی به وب‌سرویس تماس‌ها',
                                  content_type=content_type)
        self.unique_id = 123
        self.caller_id = 456
        self.mobile = '09151234567'
        self.national_code = '0921234567'

        self.user.mobile = self.mobile
        self.user.national_code = self.national_code
        self.user.save()
        self.user.refresh_from_db()

    def test_call_reason_next_url(self):
        response = self.client.post('/users/call-reason/get-next-url').json()
        assert response['detail'] == "شما اجازه انجام این دستور را ندارید."

        self.user.user_permissions.add(Permission.objects.get(codename='access_to_call_reason_api'))

        response = self.client.post('/users/call-reason/get-next-url').json()
        assert response['status'] == 'failed'
        assert response['errors']['unique_id'] == ["این مقدار لازم است."]

        response = self.client.post('/users/call-reason/get-next-url', data={
            'unique_id': self.unique_id,
        }).json()
        assert response['status'] == 'failed'
        assert response['errors']['mobile'] == ["Both mobile and national_code should not be empty"]

        response = self.client.post('/users/call-reason/get-next-url', data={
            'unique_id': self.unique_id,
            'national_code': self.national_code,
        }).json()
        expected_response_url = f'{settings.ADMIN_URL}/accounts/callreason/create?&national_code={self.national_code}&user_id={self.user.id}&unique_id={self.unique_id}'
        expected_response = base64.b64encode(expected_response_url.encode(encoding='ascii', errors='ignore')).decode()
        assert response['status'] == 'ok'
        assert response['url'] == expected_response

        response = self.client.post('/users/call-reason/get-next-url', data={
            'unique_id': self.unique_id,
            'mobile': self.mobile,
        }).json()
        expected_response_url = f'{settings.ADMIN_URL}/accounts/callreason/create?&mobile={self.mobile}&user_id={self.user.id}&unique_id={self.unique_id}'
        expected_response = base64.b64encode(expected_response_url.encode(encoding='ascii', errors='ignore')).decode()
        assert response['status'] == 'ok'
        assert response['url'] == expected_response

        response = self.client.post('/users/call-reason/get-next-url', data={
            'unique_id': self.unique_id,
            'mobile': self.mobile,
            'national_code': self.national_code,
        }).json()
        expected_response_url = f'{settings.ADMIN_URL}/accounts/callreason/create?&mobile={self.mobile}&user_id={self.user.id}&unique_id={self.unique_id}'
        expected_response = base64.b64encode(expected_response_url.encode(encoding='ascii', errors='ignore')).decode()
        assert response['status'] == 'ok'
        assert response['url'] == expected_response

        response = self.client.post('/users/call-reason/get-next-url', data={
            'unique_id': self.unique_id,
            'mobile': self.mobile,
            'national_code': self.national_code,
            'caller_id': self.caller_id
        }).json()
        expected_response_url = f'{settings.ADMIN_URL}/accounts/callreason/create?&mobile={self.mobile}&user_id={self.user.id}&unique_id={self.unique_id}&caller_id={self.caller_id}'
        expected_response = base64.b64encode(expected_response_url.encode(encoding='ascii', errors='ignore')).decode()
        assert response['status'] == 'ok'
        assert response['url'] == expected_response
