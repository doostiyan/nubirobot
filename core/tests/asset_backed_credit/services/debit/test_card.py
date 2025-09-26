from unittest import TestCase
from unittest.mock import patch

import responses
from requests import ConnectTimeout

from exchange.accounts.models import UserSms
from exchange.asset_backed_credit.externals.notification import NotificationProvider
from exchange.asset_backed_credit.externals.providers.parsian import ParsianAPI, ParsianGetRequest
from exchange.asset_backed_credit.models import Card, Service
from exchange.asset_backed_credit.services.debit.card import update_cards_info
from tests.asset_backed_credit.helper import ABCMixins, MockCacheValue


class TestUpdateCardsInfo(ABCMixins, TestCase):
    def setUp(self) -> None:
        self.service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

    @patch('exchange.asset_backed_credit.services.providers.dispatcher.api_dispatcher_v2')
    def test_no_cards(self, mock_dispatcher):
        assert Card.objects.filter(status=Card.STATUS.registered).count() == 0

        update_cards_info()

        mock_dispatcher.assert_not_called()

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.notification.notification_provider.send_notif')
    @patch('exchange.asset_backed_credit.externals.notification.notification_provider.send_sms')
    def test_success_card_registered_to_issued(self, mock_send_sms, mock_send_notif):
        provider_id = 'test_provider_id'
        user_service = self.create_user_service(service=self.service)
        card = self.create_card(
            pan='5041720011112222',
            user_service=user_service,
            status=Card.STATUS.registered,
            provider_info={'id': provider_id},
        )

        responses.post(
            url=ParsianGetRequest.url,
            json={
                'ErrorCode': None,
                'GetRequestDetail': {
                    'CardGroupId': 12924,
                    'CardGroupTitle': 'راهکار فناوری نویان-نوبیتکس',
                    'CardPatternId': 1222,
                    'CardPatternTitle': {
                        '_isNew': False,
                        'CardTypeID': 3,
                        'DiscreteData': '',
                        'ExpireDue': 1825,
                        'ID': 1222,
                        'IIN': '622106',
                        'ModifiedColumns': {},
                        'ProductCode': 48,
                        'ServiceCode': 116,
                        'StartSerialNo': 6142422,
                    },
                    'CardTypeId': 3,
                    'CardTypeTitle': {
                        '_isNew': False,
                        'Code': '102',
                        'FromServiceCode': 102,
                        'ID': 3,
                        'MaxDepositAllowed': 2000000.0,
                        'MinDepositAllowed': 0.0,
                        'ModifiedColumns': {},
                        'Nature': 4,
                        'Title': 'کارت چند منظوره',
                        'ToServiceCode': 999,
                    },
                    'Description': 'ParentChild_IssueChildCard',
                    'Indicator': '16101306002',
                    'statusId': 14,
                    'statusTitle': {
                        '_isNew': False,
                        'BasicTypeID': 99,
                        'ID': 70429,
                        'Identifier': 10,
                        'LargeIconPath': None,
                        'LatinTitle': 'ProcessingFile',
                        'ModifiedColumns': {},
                        'PersianTitle': 'خطا در پردازش فایل',
                        'ShortTitle': 'ProcessingFile',
                        'SmallIconPath': None,
                    },
                },
                'IsSuccess': True,
                'Message': '',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {'RequestId': provider_id, 'ParentCardNumber': ParsianAPI.PARENT_CARD_NUMBER},
                ),
            ],
        )

        update_cards_info()

        card.refresh_from_db()
        assert card.status == Card.STATUS.issued

        _, mock_notif_call_data = mock_send_notif.call_args
        assert mock_notif_call_data['user'] == card.user
        mock_send_notif.assert_called_once()
        _, mock_sms_call_data = mock_send_sms.call_args
        mock_send_sms.assert_called_once()
        assert mock_sms_call_data['user'] == card.user
        assert mock_sms_call_data['tp'] == NotificationProvider.MESSAGE_TYPES.abc_debit_card_issued
        assert mock_sms_call_data['template'] == UserSms.TEMPLATES.abc_debit_card_issued

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.notification.notification_provider.send_notif')
    @patch('exchange.asset_backed_credit.externals.notification.notification_provider.send_sms')
    def test_success_card_verified_to_activated(self, mock_send_sms, mock_send_notif):
        provider_id = 'test_provider_id'
        user_service = self.create_user_service(service=self.service)
        card = self.create_card(
            pan='5041720011113333',
            user_service=user_service,
            status=Card.STATUS.verified,
            provider_info={'id': provider_id},
        )

        responses.post(
            url=ParsianGetRequest.url,
            json={
                'ErrorCode': None,
                'GetRequestDetail': {
                    'statusId': 4,
                },
                'IsSuccess': True,
                'Message': '',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {'RequestId': provider_id, 'ParentCardNumber': ParsianAPI.PARENT_CARD_NUMBER},
                ),
            ],
        )

        update_cards_info()

        card.refresh_from_db()
        assert card.status == Card.STATUS.activated

        _, mock_notif_call_data = mock_send_notif.call_args
        assert mock_notif_call_data['user'] == card.user
        mock_send_notif.assert_called_once()
        _, mock_sms_call_data = mock_send_sms.call_args
        mock_send_sms.assert_called_once()
        assert mock_sms_call_data['user'] == card.user
        assert mock_sms_call_data['tp'] == NotificationProvider.MESSAGE_TYPES.abc_debit_card_activated
        assert mock_sms_call_data['template'] == UserSms.TEMPLATES.abc_debit_card_activated

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.notification.notification_provider.send_notif')
    @patch('exchange.asset_backed_credit.externals.notification.notification_provider.send_sms')
    def test_card_not_issued_status(self, mock_send_sms, mock_send_notif):
        provider_id = 'test_provider_id'
        user_service = self.create_user_service(service=self.service)
        card = self.create_card(
            pan='5041720011112222',
            user_service=user_service,
            status=Card.STATUS.registered,
            provider_info={'id': provider_id},
        )

        responses.post(
            url=ParsianGetRequest.url,
            json={
                'ErrorCode': None,
                'GetRequestDetail': {
                    'statusId': 1,
                },
                'IsSuccess': True,
                'Message': '',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {'RequestId': provider_id, 'ParentCardNumber': ParsianAPI.PARENT_CARD_NUMBER},
                ),
            ],
        )

        update_cards_info()

        card.refresh_from_db()
        assert card.status == Card.STATUS.registered

        mock_send_notif.assert_not_called()
        mock_send_sms.assert_not_called()

    @patch('exchange.asset_backed_credit.externals.notification.notification_provider.send_notif')
    @patch('exchange.asset_backed_credit.externals.notification.notification_provider.send_sms')
    @patch('exchange.asset_backed_credit.services.providers.dispatcher.api_dispatcher_v2')
    def test_card_already_issued(self, mock_dispatcher, mock_send_sms, mock_send_notif):
        provider_id = 'test_provider_id'
        user_service = self.create_user_service(service=self.service)
        card = self.create_card(
            pan='5041720011112222',
            user_service=user_service,
            status=Card.STATUS.issued,
            provider_info={'id': provider_id},
        )

        update_cards_info()

        card.refresh_from_db()
        assert card.status == Card.STATUS.issued

        mock_dispatcher.assert_not_called()
        mock_send_notif.assert_not_called()
        mock_send_sms.assert_not_called()

    @patch('exchange.asset_backed_credit.externals.notification.notification_provider.send_notif')
    @patch('exchange.asset_backed_credit.externals.notification.notification_provider.send_sms')
    @patch('exchange.asset_backed_credit.services.providers.dispatcher.api_dispatcher_v2')
    def test_card_already_activated(self, mock_dispatcher, mock_send_sms, mock_send_notif):
        provider_id = 'test_provider_id'
        user_service = self.create_user_service(service=self.service)
        card = self.create_card(
            pan='5041720011112222',
            user_service=user_service,
            status=Card.STATUS.activated,
            provider_info={'id': provider_id},
        )

        update_cards_info()

        card.refresh_from_db()
        assert card.status == Card.STATUS.activated

        mock_dispatcher.assert_not_called()
        mock_send_notif.assert_not_called()
        mock_send_sms.assert_not_called()

    @responses.activate
    def test_multiple_cards(self):
        provider_id_1 = 'test_provider_id_1'
        user_service_1 = self.create_user_service(service=self.service)
        card_1 = self.create_card(
            pan='5041720011112222',
            user_service=user_service_1,
            status=Card.STATUS.registered,
            provider_info={'id': provider_id_1},
        )

        provider_id_2 = 'test_provider_id_2'
        user_service_2 = self.create_user_service(service=self.service)
        card_2 = self.create_card(
            pan='5041720011113333',
            user_service=user_service_2,
            status=Card.STATUS.registered,
            provider_info={'id': provider_id_2},
        )

        provider_id_3 = 'test_provider_id_3'
        user_service_3 = self.create_user_service(service=self.service)
        card_3 = self.create_card(
            pan='5041720011114444',
            user_service=user_service_3,
            status=Card.STATUS.registered,
            provider_info={'id': provider_id_3},
        )
        provider_id_4 = 'test_provider_id_4'
        user_service_4 = self.create_user_service(service=self.service)
        card_4 = self.create_card(
            pan='5041720011115555',
            user_service=user_service_4,
            status=Card.STATUS.verified,
            provider_info={'id': provider_id_4},
        )

        responses.post(
            url=ParsianGetRequest.url,
            json={
                'ErrorCode': None,
                'GetRequestDetail': {
                    'statusId': 14,
                },
                'IsSuccess': True,
                'Message': '',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {'RequestId': provider_id_1, 'ParentCardNumber': ParsianAPI.PARENT_CARD_NUMBER},
                ),
            ],
        )
        responses.post(
            url=ParsianGetRequest.url,
            json={'ErrorCode': None, 'IsSuccess': False, 'Message': ''},
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {'RequestId': provider_id_2, 'ParentCardNumber': ParsianAPI.PARENT_CARD_NUMBER},
                ),
            ],
        )
        responses.post(
            url=ParsianGetRequest.url,
            body=ConnectTimeout(),
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {'RequestId': provider_id_3, 'ParentCardNumber': ParsianAPI.PARENT_CARD_NUMBER},
                ),
            ],
        )
        responses.post(
            url=ParsianGetRequest.url,
            json={
                'ErrorCode': None,
                'GetRequestDetail': {
                    'statusId': 4,
                },
                'IsSuccess': True,
                'Message': '',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {'RequestId': provider_id_4, 'ParentCardNumber': ParsianAPI.PARENT_CARD_NUMBER},
                ),
            ],
        )

        update_cards_info()

        card_1.refresh_from_db()
        assert card_1.status == Card.STATUS.issued
        card_2.refresh_from_db()
        assert card_2.status == Card.STATUS.registered
        card_3.refresh_from_db()
        assert card_3.status == Card.STATUS.registered
        card_4.refresh_from_db()
        assert card_4.status == Card.STATUS.activated
