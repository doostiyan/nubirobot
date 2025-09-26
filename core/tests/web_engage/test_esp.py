import json
import os
import re
import uuid
from unittest import mock
from unittest.mock import patch

import pytest
from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.utils import dateparse
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_405_METHOD_NOT_ALLOWED,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.cache import cache
from exchange.web_engage.api.views.esp import ESPMessageApi
from exchange.web_engage.externals.infobip import translate_infobip_error_codes
from exchange.web_engage.models.email_log import WebEngageEmailLog, WebEngageEmailRecipientLog
from exchange.web_engage.services.esp import (
    _process_email_delivery_logs,
    cleanup_email_logs,
    send_email_delivery_status_to_webengage,
)

EMAIL_BULK_ID = 'sample-bulk-id'

class MockedESP:
    def __init__(self, tp='success'):
        self.status_code = HTTP_200_OK
        if tp == 'success':
            self.json_data = {
                "bulkId": EMAIL_BULK_ID,
                "messages": [
                    {
                        "to": "user1@example.com",
                        "messageId": "tu5k6tdo7df1bpgk7ggs",
                        "status": {
                            "groupId": 1,
                            "groupName": "PENDING",
                            "id": 26,
                            "name": "PENDING_ACCEPTED",
                            "description": "Message accepted, pending for delivery."
                        }
                    },
                    {
                        "to": "user2@example.com",
                        "messageId": "e7zzb1v9yirml2se9zo4",
                        "status": {
                            "groupId": 2,
                            "groupName": "UNDELIVERABLE",
                            "id": 4,
                            "name": "UNDELIVERABLE_REJECTED_OPERATOR",
                            "description": "Message has been sent to the operator, whereas the request was rejected"
                        }
                    }
                ]
            }
            self.text = json.dumps(self.json_data)
        else:
            self.status_code = HTTP_400_BAD_REQUEST
            self.json_data = {
                "requestError": {
                    "serviceException": {
                        "messageId": "6010",
                        "text": "EC_STORAGE_LIMIT_EXCEEDED"
                    }
                }
            }
            self.text = json.dumps(self.json_data)

    def json(self):
        return self.json_data


class TestESP(TestCase):
    @override_settings(ESP_LOG={'max_size': 1, 'max_history': 30})
    def test_cleanup_email_logs(self):
        with mock.patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = dateparse.parse_datetime("2022-01-01T04:30:00Z")
            email_body_1 = WebEngageEmailLog.objects.create(
                subject="test",
                from_address="info@mail.nobitex.ir",
                from_name="Nobitex",
                message="test duplicate message_id",
                html_message="<p>test duplicate message_id</p>",
                track_id=EMAIL_BULK_ID,
                custom_data="{}",
            )
            WebEngageEmailRecipientLog.objects.create(
                to="siavash@nobitex.net",
                subject_type=WebEngageEmailRecipientLog.SUBJECT_TYPES.normal,
                email_body=email_body_1,
            )
            email_body_2 = WebEngageEmailLog.objects.create(
                subject="test",
                from_address="info@mail.nobitex.ir",
                from_name="Nobitex",
                message="test duplicate message_id",
                html_message="<p>test duplicate message_id</p>",
                track_id=100003,
                custom_data="{}",
            )
            WebEngageEmailRecipientLog.objects.create(
                to="siavash@nobitex.net",
                subject_type=WebEngageEmailRecipientLog.SUBJECT_TYPES.normal,
                email_body=email_body_2,
            )
        WebEngageEmailLog.objects.create(
            subject="test",
            from_address="info@mail.nobitex.ir",
            from_name="Nobitex",
            message="test duplicate message_id",
            html_message="<p>test duplicate message_id</p>",
            track_id=100004,
            custom_data="{}",
        )

        email_log_count = WebEngageEmailLog.objects.count()
        assert email_log_count == 3
        email_recipient_log_count = WebEngageEmailRecipientLog.objects.count()
        assert email_recipient_log_count == 2

        cleanup_email_logs()

        email_log_count = WebEngageEmailLog.objects.count()
        assert email_log_count == 2
        email_recipient_log_count = WebEngageEmailRecipientLog.objects.count()
        assert email_recipient_log_count == 1


@override_settings(IS_PROD=True)
class TestESPAPI(APITestCase):
    def setUp(self):
        self.user1 = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)
        self.client = Client(REMOTE_ADDR="54.82.121.36", HTTP_AUTHORIZATION=f'Token {self.user1.auth_token.key}')
        self.user1.webengage_cuid = '677f3958-350e-46f9-8d57-be03735cd98e'
        self.user1.email = "user1@example.com"
        self.user1.save()
        self.user2.webengage_cuid = '00d46010-f33f-42e3-a71f-a380d85d1e37'
        self.user2.email = "user2@example.com"
        self.user2.save()

        self.url = "/integrations/webengage/private_esp"
        self.payload = {
            "email": {
                "from": "info@n1.nobitex.net",
                "fromName": "Nobitex",
                "replyTo": [
                    "replyone@email.xyz",
                    "replytwo@email.xyz"
                ],
                "subject": "Test Email",
                "text": "this is a test email",
                "html": "<p>this is a test email</p>",
                "recipients": {
                    "to": [{
                        "name": "کاربر اول",
                        "email": self.user1.webengage_cuid
                    }, {
                        "name": "کاربر دوم",
                        "email": self.user2.webengage_cuid
                    }],
                    "cc": [
                        "recipient_cc1@email.xyz",
                        "recipient_cc2@email.xyz"
                    ],
                    "bcc": [
                        "recipient_bcc1@email.xyz",
                        "recipient_bcc2@email.xyz"
                    ]
                },
                "attachments": [{
                    "name": "Attachment1",
                    "url": "http://link/to/attachment/1"
                }, {
                    "name": "Attachment2",
                    "url": "http://link/to/attachment/2"
                }]
            },
            "metadata": {
                "campaignType": "PROMOTIONAL",
                "custom": {
                    "key1": "val1",
                    "key2": "val2"
                },
                "timestamp": 1521012814,
                "messageId": EMAIL_BULK_ID,
            },
            "version": "1.0"
        }
        self.delivery_response = {
            "results": [
                {
                    "bulkId": EMAIL_BULK_ID,
                    "price": {
                        "pricePerMessage": 0,
                        "currency": "UNKNOWN"
                    },
                    "status": {
                        "id": 5,
                        "groupId": 3,
                        "groupName": "DELIVERED",
                        "name": "DELIVERED_TO_HANDSET",
                        "description": "Message delivered to handset"
                    },
                    "error": {
                        "id": 0,
                        "name": "NO_ERROR",
                        "description": "No Error",
                        "groupId": 0,
                        "groupName": "OK",
                        "permanent": False
                    },
                    "messageId": "hgtesn8bcmc71pujp92d",
                    "doneAt": "2020-09-08T05:27:59.256+0000",
                    "smsCount": 1,
                    "sentAt": "2020-09-08T05:27:57.628+0000",
                    "browserLink": "http://tracking.domain.com/render/content?id=9A31C6F61DBAE9664D74C7A5A5A01F92283F581D11EA80A28C12E83BC83D449BC4A9F32F1AE3C3E",
                    "callbackData": "something you want back",
                    "to": self.user1.email
                },
                {
                    "bulkId": EMAIL_BULK_ID,
                    "price": {
                        "pricePerMessage": 0,
                        "currency": "UNKNOWN"
                    },
                    "status": {
                        "id": 4,
                        "groupId": 2,
                        "groupName": "UNDELIVERABLE",
                        "name": "UNDELIVERABLE_REJECTED_OPERATOR",
                        "description": "Message delivered to handset"
                    },
                    "error": {
                        "id": 0,
                        "name": "NO_ERROR",
                        "description": "No Error",
                        "groupId": 0,
                        "groupName": "OK",
                        "permanent": False
                    },
                    "messageId": "hgtesn7bcmc71pujp00d",
                    "doneAt": "2020-09-08T05:28:59.256+0000",
                    "smsCount": 1,
                    "sentAt": "2020-09-08T05:27:57.628+0000",
                    "browserLink": "http://tracking.domain.com/render/content?id=9A31C6F61DBAE9664D74C7A5A5A01F92283F581D11EA80A28C12E83BC83D449BC4A9F32F1AE3C3E",
                    "callbackData": "something you want back",
                    "to": self.user2.email
                }
            ]
        }

        cache.set('settings_webengage_esp_api_key', self.user1.auth_token.key)

    def test_esp_api_bad_method(self):
        response = self.client.get(self.url, self.payload, content_type='application/json')
        self.assertEqual(response.status_code, HTTP_405_METHOD_NOT_ALLOWED)

    def test_esp_api_backed_remote_ip(self):
        not_white_ip = "54.82.121.30"
        response = self.client.post(self.url, self.payload,
                                    content_type="application/json",
                                    REMOTE_ADDR=not_white_ip)
        self.assertEqual(response.status_code, HTTP_403_FORBIDDEN)

    def test_esp_api_bad_token(self):
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token bad_token_12345'
        response = self.client.post(self.url, self.payload, content_type='application/json')
        expected_result = {'status': 'AuthenticationError', 'statusCode': 9003, 'message': 'Wrong Token.'}
        self.assertEqual(response.status_code, HTTP_401_UNAUTHORIZED)
        self.assertDictEqual(response.json(), expected_result)

        self.client.defaults['HTTP_AUTHORIZATION'] = f'Tooken {self.user1.auth_token.key}'
        response = self.client.post(self.url, self.payload, content_type='application/json')
        expected_result = {
            "status": "AuthenticationError",
            "statusCode": 9003,
            "message": "Malformed authentication header.",
        }
        self.assertEqual(response.status_code, HTTP_401_UNAUTHORIZED)
        self.assertDictEqual(response.json(), expected_result)

    def test_esp_api_unsupported_version(self):
        self.payload['version'] = '2.0'
        response = self.client.post(self.url, self.payload, content_type='application/json')
        expected_result = {'status': 'ERROR',
                           'statusCode': 9022,
                           'message': 'Unsupported version',
                           'supportedVersion': '1.0'}
        self.assertEqual(response.status_code, HTTP_400_BAD_REQUEST)
        self.assertDictEqual(response.json(), expected_result)

    @patch('requests.post')
    def test_esp_api_email_server_error(self, mock):
        mock.return_value = MockedESP('fail')
        expected_result = {
            "status": "ERROR",
            "statusCode": 9002,
            "message": "MESSAGE_SENDING_QUOTA_EXCEEDED"
        }
        payload = json.dumps(self.payload)
        response = self.client.post(self.url, payload, content_type='application/json')
        self.assertEqual(response.status_code, HTTP_400_BAD_REQUEST)
        self.assertDictEqual(response.json(), expected_result)
        with pytest.raises(WebEngageEmailLog.DoesNotExist):
            WebEngageEmailLog.objects.get(subject=self.payload.get('email').get('subject'),
                                          track_id=self.payload.get('metadata', dict()).get('messageId'))
        with pytest.raises(WebEngageEmailRecipientLog.DoesNotExist):
            WebEngageEmailRecipientLog.objects.get(to=self.user1.email)

    def test_esp_api_email_validation_error(self):
        expected_result = {
            "status": "ERROR",
            "statusCode": 9020,
            "message": "ERROR_PROCESSING_EMAIL_AT_ESP"
        }
        self.payload["email"]["from"] = "info@nobitex.ir"
        payload = json.dumps(self.payload)
        response = self.client.post(self.url, payload, content_type='application/json')
        self.assertEqual(response.status_code, HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertDictEqual(response.json(), expected_result)
        with pytest.raises(WebEngageEmailLog.DoesNotExist):
            WebEngageEmailLog.objects.get(subject=self.payload.get('email').get('subject'),
                                          track_id=self.payload.get('metadata', dict()).get('messageId'))
        with pytest.raises(WebEngageEmailRecipientLog.DoesNotExist):
            WebEngageEmailRecipientLog.objects.get(to=self.user1.email)

    def test_esp_api_email_duplicate_message_id_error(self):
        expected_result = {
            "status": "ERROR",
            "statusCode": 9020,
            "message": "ERROR_PROCESSING_EMAIL_AT_ESP"
        }
        WebEngageEmailLog.objects.create(
            subject="test",
            from_address="info@mail.nobitex.ir",
            from_name="Nobitex",
            message="test duplicate message_id",
            html_message="<p>test duplicate message_id</p>",
            track_id=EMAIL_BULK_ID,
            custom_data="{}"
        )
        payload = json.dumps(self.payload)
        response = self.client.post(self.url, payload, content_type='application/json')
        self.assertEqual(response.status_code, HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertDictEqual(response.json(), expected_result)

    @patch('requests.post')
    def test_esp_api_success(self, mock):
        mock.return_value = MockedESP()
        expected_result = {
            "status": "SUCCESS",
            "statusCode": 1000,
            "message": "NA"
        }
        payload = json.dumps(self.payload)
        response = self.client.post(self.url, payload, content_type='application/json')
        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertDictEqual(response.json(), expected_result)
        log = WebEngageEmailLog.objects.filter(subject=self.payload.get('email').get('subject'),
                                               track_id=self.payload.get('metadata', dict()).get('messageId')).first()
        self.assertIsNotNone(log)

        log_user1: WebEngageEmailRecipientLog = WebEngageEmailRecipientLog.objects.get(
            to=self.user1.email, email_body__track_id=EMAIL_BULK_ID
        )
        assert log_user1.message_id == "tu5k6tdo7df1bpgk7ggs"
        assert log_user1.status == "PENDING_ACCEPTED"
        assert log_user1.to == self.user1.email
        assert log_user1.subject_type == WebEngageEmailRecipientLog.SUBJECT_TYPES.normal
        assert log_user1.created_at is not None
        assert log_user1.email_body is not None

        log_user2: WebEngageEmailRecipientLog = WebEngageEmailRecipientLog.objects.get(
            to=self.user2.email, email_body__track_id=EMAIL_BULK_ID
        )
        assert log_user2.message_id == "e7zzb1v9yirml2se9zo4"
        assert log_user2.status == "UNDELIVERABLE_REJECTED_OPERATOR"
        assert log_user2.to == self.user2.email
        assert log_user2.subject_type == WebEngageEmailRecipientLog.SUBJECT_TYPES.normal
        assert log_user2.created_at is not None
        assert log_user2.email_body is not None



    def test_decode_email_addresses_success(self):
        # given ->
        user_count = 63
        users, to_list = self._generate_bulk_users(user_count)

        User.objects.bulk_create(users)
        self.payload.get('email', {}).get('recipients', {}).update({"to": to_list})

        # when ->
        result = ESPMessageApi._decode_email_addresses(self.payload)

        # then->
        to_list = result.get('email', {}).get('recipients', {}).get('to')
        assert len(to_list) == user_count
        for recipient in to_list:
            assert recipient['email']
            assert re.match(r'^\S+@\S+\.\S+$', recipient['email'])

        User.objects.filter(id__in=list(map(lambda u: u.id, users))).delete()

    def test_decode_email_addresses_with_noisy_data_success(self):
        # given ->
        total_user_count = 23
        invalid_user_count = 3
        users, to_list = self._generate_bulk_users(total_user_count - invalid_user_count)

        inactive_user = User.objects.create(
            username='inactive-user',
            email=f'inactive-user@gmail.com',
            first_name=f'name_inactive-user',
            webengage_cuid=uuid.uuid4(),
            user_type=User.USER_TYPES.inactive,
        )
        blocked_user = User.objects.create(
            username='blocked-user',
            email=f'blocked-user@gmail.com',
            first_name=f'name_blocked-user',
            webengage_cuid=uuid.uuid4(),
            user_type=User.USER_TYPES.blocked,
        )
        suspicious_user = User.objects.create(
            username='suspicious-user',
            email=f'suspicious-user@gmail.com',
            first_name=f'name_suspicious-user',
            webengage_cuid=uuid.uuid4(),
            user_type=User.USER_TYPES.suspicious,
        )

        to_list.append({'name': 'inactive-user', 'email': str(inactive_user.webengage_cuid)})
        to_list.append({'name': 'blocked-user', 'email': str(blocked_user.webengage_cuid)})
        to_list.append({'name': 'suspicious-user', 'email': str(suspicious_user.webengage_cuid)})
        to_list.append({'name': 'unknown_user', 'email': str(uuid.uuid4())})
        to_list.append({'name': 'unknown_user_2', 'email': '   '})

        User.objects.bulk_create(users)
        self.payload.get('email', {}).get('recipients', {}).update({"to": to_list})

        # when ->
        result = ESPMessageApi._decode_email_addresses(self.payload)

        # then->
        to_list = result.get('email', {}).get('recipients', {}).get('to')
        assert len(to_list) == total_user_count - invalid_user_count
        for recipient in to_list:
            assert recipient['email']
            assert re.match(r'^\S+@\S+\.\S+$', recipient['email'])

        User.objects.filter(id__in=list(map(lambda u: u.id, users))).delete()
        inactive_user.delete()
        suspicious_user.delete()
        blocked_user.delete()

    @staticmethod
    def _generate_bulk_users(count):
        users = []
        to_list = []

        for i in range(count):
            username = f'user_{str(i-500)}'
            user = User(
                username=username,
                email=f'{username}@gmail.com',
                first_name=f'name_{username}',
                webengage_cuid=uuid.uuid4(),
            )
            users.append(user)
            to_list.append({'name': user.first_name, 'email': str(user.get_webengage_id())})

        return users, to_list

    def test_esp_info_bip_translate_error_code(self):
        from exchange.web_engage.types import ESPDeliveryStatusCode as EspCodes

        self.assertEqual(translate_infobip_error_codes(0), (EspCodes.SUCCESS.value, EspCodes.SUCCESS.name))
        self.assertEqual(
            translate_infobip_error_codes(6001),
            (EspCodes.EMAIL_IN_SUPPRESSION_LIST.value, EspCodes.EMAIL_IN_SUPPRESSION_LIST.name),
        )
        self.assertEqual(
            translate_infobip_error_codes(6002),
            (EspCodes.EMAIL_REPORTED_AS_SPAM.value, EspCodes.EMAIL_REPORTED_AS_SPAM.name),
        )
        self.assertEqual(
            translate_infobip_error_codes(6003), (EspCodes.EMAIL_UNSUBSCRIBED.value, EspCodes.EMAIL_UNSUBSCRIBED.name)
        )
        self.assertEqual(translate_infobip_error_codes(6004), (EspCodes.SOFT_BOUNCE.value, EspCodes.SOFT_BOUNCE.name))
        self.assertEqual(translate_infobip_error_codes(6005), (EspCodes.SOFT_BOUNCE.value, EspCodes.SOFT_BOUNCE.name))
        self.assertEqual(
            translate_infobip_error_codes(6006),
            (EspCodes.INVALID_EMAIL_ADDRESS.value, EspCodes.INVALID_EMAIL_ADDRESS.name),
        )
        self.assertEqual(
            translate_infobip_error_codes(6008),
            (EspCodes.RECIPIENTS_MAIL_BOX_IS_FULL.value, EspCodes.RECIPIENTS_MAIL_BOX_IS_FULL.name),
        )
        self.assertEqual(
            translate_infobip_error_codes(6007),
            (EspCodes.MAILBOX_WAS_NOT_FOUND_ON_MAIL_SERVER.value, EspCodes.MAILBOX_WAS_NOT_FOUND_ON_MAIL_SERVER.name),
        )
        self.assertEqual(
            translate_infobip_error_codes(6009),
            (EspCodes.MAILBOX_WAS_NOT_FOUND_ON_MAIL_SERVER.value, EspCodes.MAILBOX_WAS_NOT_FOUND_ON_MAIL_SERVER.name),
        )
        self.assertEqual(
            translate_infobip_error_codes(6010),
            (EspCodes.MESSAGE_SENDING_QUOTA_EXCEEDED.value, EspCodes.MESSAGE_SENDING_QUOTA_EXCEEDED.name),
        )
        self.assertEqual(
            translate_infobip_error_codes(6013), (EspCodes.THROTTLING_ERROR.value, EspCodes.THROTTLING_ERROR.name)
        )
        self.assertEqual(
            translate_infobip_error_codes(6014), (EspCodes.THROTTLING_ERROR.value, EspCodes.THROTTLING_ERROR.name)
        )
        self.assertEqual(
            translate_infobip_error_codes(6015), (EspCodes.THROTTLING_ERROR.value, EspCodes.THROTTLING_ERROR.name)
        )

        # unknown
        self.assertEqual(
            translate_infobip_error_codes(6012), (EspCodes.UNKNOWN_REASON.value, EspCodes.UNKNOWN_REASON.name)
        )
        self.assertEqual(
            translate_infobip_error_codes(6016), (EspCodes.UNKNOWN_REASON.value, EspCodes.UNKNOWN_REASON.name)
        )
        self.assertEqual(
            translate_infobip_error_codes(6017), (EspCodes.UNKNOWN_REASON.value, EspCodes.UNKNOWN_REASON.name)
        )
        self.assertEqual(
            translate_infobip_error_codes(6018), (EspCodes.UNKNOWN_REASON.value, EspCodes.UNKNOWN_REASON.name)
        )
        self.assertEqual(
            translate_infobip_error_codes(6021), (EspCodes.UNKNOWN_REASON.value, EspCodes.UNKNOWN_REASON.name)
        )
        self.assertEqual(
            translate_infobip_error_codes(255), (EspCodes.UNKNOWN_REASON.value, EspCodes.UNKNOWN_REASON.name)
        )

    def test_esp_info_bip_to_delivery_data_success(self):
        events = _process_email_delivery_logs(self.delivery_response)
        event_2 = events.pop()
        event_1 = events.pop()

        assert event_1.message_id == EMAIL_BULK_ID
        assert event_1.event == "DELIVERED"
        assert event_1.timestamp == 1599542879
        assert event_1.email == "user1@example.com"
        assert event_1.status_code == 1000
        assert event_1.message == "SUCCESS"

        assert event_2.message_id == EMAIL_BULK_ID
        assert event_2.event == "BOUNCE"
        assert event_2.timestamp == 1599542939
        assert event_2.email == "user2@example.com"
        assert event_2.status_code == 9007
        assert event_2.message == "HARD_BOUNCE"

    @patch('exchange.web_engage.externals.web_engage.is_web_engage_active', return_value=True)
    @patch('requests.post')
    def test_send_email_delivery_report_success(self, mock, mock2):
        # given->
        events = _process_email_delivery_logs(self.delivery_response)
        event = events.pop()

        # when->
        send_email_delivery_status_to_webengage(event)

        # then->
        mock.assert_called_once_with(
            headers={'Content-Type': 'application/json'},
            url=settings.WEB_ENGAGE_PRIVATE_ESP_WEBHOOK,
            json={
                'version': '1.0',
                'messageId': EMAIL_BULK_ID,
                'event': "BOUNCE",
                'timestamp': 1599542939,
                'email': '00d46010-f33f-42e3-a71f-a380d85d1e37',
                'hashedEmail': '00d46010-f33f-42e3-a71f-a380d85d1e37',
                'statusCode': 9007,
                'message': "HARD_BOUNCE",
            },
        )

    def test_email_delivery_webhook_api_success(self):
        # given->
        bulk_id = EMAIL_BULK_ID
        message_id = 'hgtesn8bcmc71pujp92d'

        email = WebEngageEmailLog.objects.create(
            subject="test",
            from_address="info@mail.nobitex.ir",
            from_name="Nobitex",
            message="test duplicate message_id",
            html_message="<p>test duplicate message_id</p>",
            track_id=bulk_id,
            custom_data="{}",
        )
        WebEngageEmailRecipientLog.objects.create(
            to='john.doe@gmail.com',
            subject_type=WebEngageEmailRecipientLog.SUBJECT_TYPES.normal,
            email_body=email,
            message_id=message_id,
        )

        # when->
        with open(os.path.join(os.path.dirname(__file__), 'test_data', 'email_delivery_response.json'), 'r') as f:

            self.client.post(
                f'/webhooks/webengage/esp_delivery_status_webhook/{bulk_id}',
                data=json.load(f),
                content_type='application/json',
            )

        # then ->
        updated_record = WebEngageEmailRecipientLog.objects.filter(
            message_id=message_id, email_body__track_id=bulk_id
        ).first()
        assert updated_record.done_at is not None
        assert updated_record.status == "DELIVERED_TO_HANDSET"
