import uuid
from datetime import timedelta
from unittest import mock
from uuid import UUID

import responses
from django.conf import settings
from django.test import TestCase, override_settings

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.web_engage.models import WebEngageSMSLog
from exchange.web_engage.models.sms_log import WebEngageSMSBatch
from exchange.web_engage.services.ssp import batch_and_send_sms_messages, inquire_sent_batch_sms
from exchange.web_engage.tasks import task_send_batch_sms_to_ssp


class TestSSPAgent(TestCase):

    def setUp(self) -> None:
        counter = 1
        for user in User.objects.all()[:10]:
            if not user.mobile:
                user.mobile = f'099800000{counter}'
                user.save()
            for i in range(counter):
                WebEngageSMSLog.objects.create(user=user, phone_number=user.mobile, message_id=str(uuid.uuid4()),
                                               text='salam')
            counter += 1

    def tearDown(self) -> None:
        WebEngageSMSLog.objects.all().delete()
        WebEngageSMSBatch.objects.all().delete()

    @override_settings(IS_PROD=True)
    @responses.activate
    @mock.patch('exchange.integrations.finnotext.uuid4', return_value=UUID('f63b6ac4-fd88-4373-b9be-e8626e8ef939'))
    def test_batch_sms(self, mocked_uuid):
        batch_and_send_sms_messages()
        batches = WebEngageSMSBatch.objects.order_by('pk').all()
        assert batches.count() == 12
        batch = batches[0]
        assert batch.sms_logs.all().count() == 7
        assert len([log.phone_number for log in batch.sms_logs.all()]) == len(
            set([log.phone_number for log in batch.sms_logs.all()]))
        assert batch.status == WebEngageSMSBatch.STATUS.new
        responses.post(
            f'https://apibeta.finnotech.ir/facility/v2/clients/{settings.MARKETING_FINNOTEXT_CLIENT_ID}/finnotext',
            json={'status': 'DONE'},
        )
        task_send_batch_sms_to_ssp(batch_id=batch.id)
        batch.refresh_from_db()
        assert batch.status == WebEngageSMSBatch.STATUS.sent_to_ssp

        batch2 = batches[2]
        assert batch2.sms_logs.all().count() == 7
        assert batch2.status == WebEngageSMSBatch.STATUS.new
        responses.post(
            f'https://apibeta.finnotech.ir/facility/v2/clients/{settings.MARKETING_FINNOTEXT_CLIENT_ID}/finnotext',
            json={'status': 'DONE'},
        )
        task_send_batch_sms_to_ssp(batch_id=batch2.id)
        batch2.refresh_from_db()
        assert batch.status == WebEngageSMSBatch.STATUS.sent_to_ssp

        responses.get(
            f'https://apibeta.finnotech.ir/facility/v2/clients/{settings.MARKETING_FINNOTEXT_CLIENT_ID}/finnotextInquiry',
            match=[
                responses.matchers.query_param_matcher(
                    {'trackId': 'f63b6ac4-fd88-4373-b9be-e8626e8ef939', 'inquiryTrackId': str(batch.track_id)}
                )
            ],
            json={
                'status': 'DONE',
                'result': {
                    'messages_status': [{'to_number': log.phone_number, 'status': 1} for log in batch.sms_logs.all()]
                },
            },
        )
        responses.get(
            f'https://apibeta.finnotech.ir/facility/v2/clients/{settings.MARKETING_FINNOTEXT_CLIENT_ID}/finnotextInquiry',
            match=[
                responses.matchers.query_param_matcher(
                    {'trackId': 'f63b6ac4-fd88-4373-b9be-e8626e8ef939', 'inquiryTrackId': str(batch2.track_id)}
                )
            ],
            json={
                'status': 'DONE',
                'result': {
                    'messages_status': [
                        {'to_number': '+98' + log.phone_number[1:], 'status': 1} for log in batch2.sms_logs.all()
                    ]
                },
            },
        )

        responses.post(settings.WEB_ENGAGE_PRIVATE_SSP_WEBHOOK)
        with mock.patch('exchange.web_engage.services.ssp.ir_now', return_value=ir_now() + timedelta(minutes=20)):
            inquire_sent_batch_sms()
        batch.refresh_from_db()
        batch2.refresh_from_db()
        assert batch.status == WebEngageSMSBatch.STATUS.inquired
        assert batch2.status == WebEngageSMSBatch.STATUS.inquired

        for log in batch.sms_logs.all():
            assert log.status == WebEngageSMSLog.STATUS.succeeded

        for log in batch2.sms_logs.all():
            assert log.status == WebEngageSMSLog.STATUS.succeeded

        batch_and_send_sms_messages()
        assert WebEngageSMSBatch.objects.all().count() == 12

        assert not WebEngageSMSLog.objects.filter(status=WebEngageSMSLog.STATUS.new, batch=None).exists()
