from unittest.mock import patch

from django.test import TestCase

from exchange.accounts.models import User
from exchange.features.models import QueueItem
from exchange.features.tasks import send_feature_web_engage


@patch.object(send_feature_web_engage, 'delay', send_feature_web_engage)
class QueueItemWebEngageEventTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.get(pk=201)
        self.queue_item = QueueItem.objects.create(
            user=self.user1,
            status=QueueItem.STATUS.waiting,
            feature=QueueItem.FEATURES.jibit_pip,
        )

    @patch('exchange.web_engage.events.features_events.FeatureEnabledWebEngageEvent.send')
    def test_send_feature_web_engage_event_on_edit(self, verify_mock):
        assert self.queue_item.status == QueueItem.STATUS.waiting
        self.queue_item.status = QueueItem.STATUS.done
        self.queue_item.save(update_fields=['status'])
        self.queue_item.refresh_from_db()
        assert self.queue_item.status == QueueItem.STATUS.done

        self.queue_item.feature = QueueItem.FEATURES.ticketing
        self.queue_item.save(update_fields=['feature'])

        assert verify_mock.call_count == 1

    @patch('exchange.web_engage.events.features_events.FeatureEnabledWebEngageEvent.send')
    def test_feature_failed_event(self, verify_mock):
        assert self.queue_item.status == QueueItem.STATUS.waiting
        self.queue_item.status = QueueItem.STATUS.failed
        self.queue_item.save(update_fields=['status'])
        self.queue_item.refresh_from_db()
        assert self.queue_item.status == QueueItem.STATUS.failed
        assert not verify_mock.called

    @patch('exchange.web_engage.events.features_events.FeatureEnabledWebEngageEvent.send')
    def test_send_feature_web_engage_event_on_create(self, verify_mock):
        QueueItem.objects.create(
            user=self.user1,
            status=QueueItem.STATUS.done,
            feature=QueueItem.FEATURES.new_coins,
        )
        QueueItem.objects.create(
            user=self.user1,
            status=QueueItem.STATUS.waiting,
            feature=QueueItem.FEATURES.staking,
        )
        assert verify_mock.call_count == 1
