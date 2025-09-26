from decimal import Decimal
from unittest import mock

from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.models import Settings
from exchange.web_engage.events import OrderMatchedWebEngageEvent, ReferredUserUpgradedToLevel1WebEngageEvent
from exchange.web_engage.services.user import send_user_data_to_webengage


class WebEngageEventTest(APITestCase):
    def setUp(self) -> None:
        self.user1 = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)

    @mock.patch('exchange.web_engage.externals.web_engage.is_web_engage_active', return_value=True)
    @mock.patch('exchange.web_engage.events.base.is_webengage_user', return_value=True)
    @mock.patch('exchange.web_engage.events.base.task_send_event_data_to_web_engage.delay')
    def test_check_order_event_not_sent_when_in_black_list(
        self, task_send_event_data_to_web_engage: mock.MagicMock, mock2, mock3
    ):
        Settings.objects.update_or_create(key="webengage_stopped_events", defaults={"value": """["order_matched"]"""})

        OrderMatchedWebEngageEvent(
            user=self.user2, src_currency=1, dst_currency=2, order_type='b', amount=Decimal(1), trade_type='sth'
        ).send()
        assert not task_send_event_data_to_web_engage.called

    @mock.patch('exchange.web_engage.externals.web_engage.is_web_engage_active', return_value=True)
    @mock.patch('exchange.web_engage.events.base.is_webengage_user', return_value=True)
    @mock.patch('exchange.web_engage.events.base.task_send_event_data_to_web_engage.delay')
    def test_check_order_event_sent(self, task_send_event_data_to_web_engage: mock.MagicMock, mock2, mock3):
        Settings.objects.update_or_create(key="webengage_stopped_events", defaults={"value": "[]"})

        OrderMatchedWebEngageEvent(
            user=self.user2, src_currency=1, dst_currency=2, order_type='b', amount=Decimal(1), trade_type='sth'
        ).send()
        assert task_send_event_data_to_web_engage.called

    @mock.patch('exchange.web_engage.externals.web_engage.is_web_engage_active', return_value=False)
    @mock.patch('exchange.web_engage.events.base.is_webengage_user', return_value=True)
    @mock.patch('exchange.web_engage.events.base.task_send_event_data_to_web_engage.delay')
    def test_check_order_not_event_sent_when_webengage_inactive(
        self, task_send_event_data_to_web_engage: mock.MagicMock, mock2, mock3
    ):
        Settings.objects.update_or_create(key="webengage_stopped_events", defaults={"value": "[]"})

        OrderMatchedWebEngageEvent(
            user=self.user2, src_currency=1, dst_currency=2, order_type='b', amount=Decimal(1), trade_type='sth'
        ).send()
        assert not task_send_event_data_to_web_engage.called

    @mock.patch('exchange.web_engage.externals.web_engage.is_web_engage_active', return_value=True)
    @mock.patch('exchange.web_engage.events.base.is_webengage_user', return_value=True)
    @mock.patch('exchange.web_engage.events.base.task_send_event_data_to_web_engage.delay')
    def test_check_referred_user_event_called(self, task_send_event_data_to_web_engage: mock.MagicMock, mock2, mock3):
        Settings.objects.update_or_create(key="webengage_stopped_events", defaults={"value": "[]"})

        ReferredUserUpgradedToLevel1WebEngageEvent(user=self.user2).send()
        assert task_send_event_data_to_web_engage.called

    @mock.patch('exchange.web_engage.externals.web_engage.is_web_engage_active', return_value=True)
    @mock.patch('exchange.web_engage.events.base.is_webengage_user', return_value=True)
    @mock.patch('exchange.web_engage.events.base.task_send_event_data_to_web_engage.delay')
    def test_check_referred_user_event_not_called(
        self, task_send_event_data_to_web_engage: mock.MagicMock, mock2, mock3
    ):
        Settings.objects.update_or_create(
            key="webengage_stopped_events", defaults={"value": """["referred_user_upgraded_to_level_1"]"""}
        )

        ReferredUserUpgradedToLevel1WebEngageEvent(user=self.user2).send()
        assert not task_send_event_data_to_web_engage.called

    @mock.patch('exchange.web_engage.externals.web_engage.is_web_engage_active', return_value=True)
    @mock.patch('exchange.web_engage.events.base.is_webengage_user', return_value=True)
    @mock.patch('exchange.web_engage.tasks.task_send_user_data_to_web_engage.delay')
    def test_disabling_send_all_user_data(self, task_send_user_data_to_web_engage: mock.MagicMock, mock2, mock3):
        Settings.objects.update_or_create(key="webengage_stopped_events", defaults={"value": """['all_user_data"]"""})

        send_user_data_to_webengage(user=self.user2)
        assert not task_send_user_data_to_web_engage.called
