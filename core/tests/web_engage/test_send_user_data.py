import datetime
from decimal import Decimal
from unittest import mock
from uuid import uuid4

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from exchange.accounts.models import User, VerificationProfile
from exchange.base.models import RIAL, TETHER, Settings
from exchange.marketing.services.mission.kyc_or_refer import KycOrReferMission, MissionTarget
from exchange.web_engage.crons import UpdateWebEngageUserData
from exchange.web_engage.services.user import send_user_base_data
from exchange.web_engage.utils import get_toman_amount_display
from tests.base.utils import create_trade


class TestSendUserData(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.webengage_cid = uuid4()
        cls.user = User.objects.create(
            username="test_user",
            email="test_user@gmail.com",
            first_name="first_name",
            birthday=datetime.datetime(year=1993, month=11, day=15),
            gender=User.GENDER.female,
            city="Tehran",
            requires_2fa=True,
            webengage_cuid=cls.webengage_cid,
            mobile="09980000000",
        )
        VerificationProfile.objects.update_or_create(
            user=cls.user, defaults={'mobile_confirmed': True, 'email_confirmed': True}
        )
        cls.other_user = User.objects.create(
            username="other",
            email="other@gmail.com",
            first_name="first_name",
            birthday=datetime.datetime(year=1993, month=11, day=15),
            gender=User.GENDER.female,
            city="Tehran",
            requires_2fa=True,
            mobile="09980000001",
        )
        VerificationProfile.objects.update_or_create(
            user=cls.other_user, defaults={'mobile_confirmed': True, 'email_confirmed': True}
        )

    @mock.patch('exchange.web_engage.externals.web_engage.WebEngageDataAPI.request')
    def test_user_event_only_tether_order(self, request_mock: mock.MagicMock):
        # given ->
        expected_data = {
            'userId': str(self.webengage_cid),
            'firstName': 'first_name',
            'hashedPhone': str(self.webengage_cid),
            'hashedEmail': str(self.webengage_cid),
            'birthDate': '1993-11-15T10:30:00+0430',
            'gender': 'Female',
            'city': 'Tehran',
            'country': 'Iran',
            'attributes': {
                '2step_verification': True,
                'user_level': 40,
                'total_order_value_code': 8,
                'total_orders': 3,
                'date_joined': self.user.date_joined.strftime("%Y-%m-%dT%H:%M:%S%z"),
            },
        }

        create_trade(self.user, self.other_user, dst_currency=TETHER, amount=Decimal('0.1'), price=Decimal('10500'))
        create_trade(self.user, self.other_user, dst_currency=TETHER, amount=Decimal('1'), price=Decimal('1000'))
        create_trade(self.user, self.other_user, dst_currency=TETHER, amount=Decimal('0.2'), price=Decimal('2000'))

        # when ->
        send_user_base_data(self.user.pk)

        # then ->
        self._assert_sent_user_data(expected_data, request_mock)

    @mock.patch('exchange.web_engage.externals.web_engage.WebEngageDataAPI.request')
    def test_user_event_rial_only_orders(self, request_mock: mock.MagicMock):
        # given ->
        expected_data = {
            'userId': str(self.webengage_cid),
            'firstName': 'first_name',
            'hashedPhone': str(self.webengage_cid),
            'hashedEmail': str(self.webengage_cid),
            'birthDate': '1993-11-15T10:30:00+0430',
            'gender': 'Female',
            'city': 'Tehran',
            'country': 'Iran',
            'attributes': {
                '2step_verification': True,
                'user_level': 40,
                'total_order_value_code': 6,
                'total_orders': 2,
                'date_joined': self.user.date_joined.strftime("%Y-%m-%dT%H:%M:%S%z"),
            },
        }

        create_trade(self.user, self.other_user, dst_currency=RIAL, amount=Decimal('2'), price=Decimal('10500000'))
        create_trade(self.user, self.other_user, dst_currency=RIAL, amount=Decimal('2'), price=Decimal('105000000'))

        # when->
        send_user_base_data(self.user.pk)

        # then->
        self._assert_sent_user_data(expected_data, request_mock)

    @mock.patch('exchange.web_engage.externals.web_engage.WebEngageDataAPI.request')
    def test_user_event_rial_and_tether_orders(self, request_mock: mock.MagicMock):
        # given ->
        expected_data = {
            'userId': str(self.webengage_cid),
            'firstName': 'first_name',
            'hashedPhone': str(self.webengage_cid),
            'hashedEmail': str(self.webengage_cid),
            'birthDate': '1993-11-15T10:30:00+0430',
            'gender': 'Female',
            'city': 'Tehran',
            'country': 'Iran',
            'attributes': {
                '2step_verification': True,
                'user_level': 40,
                'total_order_value_code': 5,
                'total_orders': 2,
                'date_joined': self.user.date_joined.strftime("%Y-%m-%dT%H:%M:%S%z"),
            },
        }

        create_trade(self.user, self.other_user, dst_currency=TETHER, amount=Decimal('0.1'), price=Decimal('2000'))
        create_trade(self.user, self.other_user, dst_currency=RIAL, amount=Decimal('2'), price=Decimal('2500000'))

        # when->
        send_user_base_data(self.user.pk)

        # then->
        self._assert_sent_user_data(expected_data, request_mock)

    @mock.patch('exchange.web_engage.externals.web_engage.WebEngageDataAPI.request')
    def test_user_event_no_orders(self, request_mock: mock.MagicMock):
        # given ->
        expected_data = {
            'userId': str(self.webengage_cid),
            'firstName': 'first_name',
            'hashedPhone': str(self.webengage_cid),
            'hashedEmail': str(self.webengage_cid),
            'birthDate': '1993-11-15T10:30:00+0430',
            'gender': 'Female',
            'city': 'Tehran',
            'country': 'Iran',
            'attributes': {
                '2step_verification': True,
                'total_order_value_code': 1,
                'total_orders': 0,
                'user_level': 40,
                'date_joined': self.user.date_joined.strftime("%Y-%m-%dT%H:%M:%S%z"),
            },
        }

        # when ->
        send_user_base_data(self.user.pk)

        # then->
        self._assert_sent_user_data(expected_data, request_mock)

    @mock.patch('exchange.web_engage.externals.web_engage.WebEngageDataAPI.request')
    def test_user_attributes_with_campaign_id_success(self, request_mock: mock.MagicMock):
        # given ->
        campaign_name = 'external_discount:kyc_or_refer:10M_snapp'
        Settings.set_dict('active_campaigns', [campaign_name])
        history = {'target': MissionTarget.KYC.value, 'user_level': User.USER_TYPES.level0, 'timestamp': timezone.now()}
        cache.set(KycOrReferMission._get_cache_key('10M_snapp', self.user.mobile), history, timeout=3600)

        expected_data = {
            'userId': str(self.webengage_cid),
            'firstName': 'first_name',
            'hashedPhone': str(self.webengage_cid),
            'hashedEmail': str(self.webengage_cid),
            'birthDate': '1993-11-15T10:30:00+0430',
            'gender': 'Female',
            'city': 'Tehran',
            'country': 'Iran',
            'attributes': {
                '2step_verification': True,
                'total_order_value_code': 1,
                'total_orders': 0,
                'user_level': 40,
                'date_joined': self.user.date_joined.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "marketing_campaign_id": '10M_snapp',
            },
        }

        # when ->
        send_user_base_data(self.user.pk)

        # then->
        self._assert_sent_user_data(expected_data, request_mock)
        Settings.set_dict('active_campaigns', [])

    @mock.patch('exchange.web_engage.externals.web_engage.WebEngageDataAPI.request')
    def test_user_attributes_with_campaign_id_when_an_error_raised_success(self, request_mock: mock.MagicMock):
        # given ->
        Settings.set_dict('active_campaigns', ['invalid-campaign-name-format'])

        expected_data = {
            'userId': str(self.webengage_cid),
            'firstName': 'first_name',
            'hashedPhone': str(self.webengage_cid),
            'hashedEmail': str(self.webengage_cid),
            'birthDate': '1993-11-15T10:30:00+0430',
            'gender': 'Female',
            'city': 'Tehran',
            'country': 'Iran',
            'attributes': {
                '2step_verification': True,
                'total_order_value_code': 1,
                'total_orders': 0,
                'user_level': 40,
                'date_joined': self.user.date_joined.strftime("%Y-%m-%dT%H:%M:%S%z"),
            },
        }

        # when ->
        send_user_base_data(self.user.pk)

        # then->
        self._assert_sent_user_data(expected_data, request_mock)
        Settings.set_dict('active_campaigns', [])

    @mock.patch('exchange.web_engage.externals.web_engage.WebEngageDataAPI.request')
    def test_user_event_no_mobile(self, request_mock: mock.MagicMock):
        # given ->
        expected_data = {
            'userId': str(self.webengage_cid),
            'firstName': 'first_name',
            'birthDate': '1993-11-15T10:30:00+0430',
            'gender': 'Female',
            'city': 'Tehran',
            'country': 'Iran',
            'attributes': {
                '2step_verification': True,
                'total_order_value_code': 1,
                'total_orders': 0,
                'user_level': 40,
                'date_joined': self.user.date_joined.strftime("%Y-%m-%dT%H:%M:%S%z"),
            },
        }

        self.user.verification_profile.mobile_confirmed = False
        self.user.verification_profile.email_confirmed = False
        self.user.verification_profile.save()

        # when ->
        send_user_base_data(self.user.pk)

        # then->
        self._assert_sent_user_data(expected_data, request_mock)

    def _assert_sent_user_data(self, expected_data, request_mock: mock.MagicMock):
        request_mock.assert_called_once()
        user_data = request_mock.call_args.args[1]

        if 'last_order_date' in user_data['attributes']:
            user_data['attributes'].pop('last_order_date')
        if 'first_order_date' in user_data['attributes']:
            user_data['attributes'].pop('first_order_date')

        self.assertDictEqual(expected_data, user_data)
        self.assertEqual(request_mock.call_args.args[0], "/v1/accounts/{license_code}/users")
        self.assertEqual(request_mock.call_args.args[2], 'all_user_data')

    def test_toman_display(self):
        assert get_toman_amount_display(Decimal(10000)) == 1
        assert get_toman_amount_display(Decimal(400000)) == 2
        assert get_toman_amount_display((Decimal(800000))) == 3
        assert get_toman_amount_display((Decimal(4000000))) == 4
        assert get_toman_amount_display((Decimal(8000000))) == 5
        assert get_toman_amount_display((Decimal(23000000))) == 6
        assert get_toman_amount_display((Decimal(34000000))) == 7
        assert get_toman_amount_display((Decimal(55000000))) == 8
        assert get_toman_amount_display((Decimal(112000000))) == 9
        assert get_toman_amount_display((Decimal(300000000))) == 10
        assert get_toman_amount_display((Decimal(658000000))) == 11


class TestSendUserDataCron(TestCase):

    @mock.patch('exchange.web_engage.externals.web_engage.is_web_engage_active', return_value=True)
    @mock.patch('exchange.web_engage.services.user.is_webengage_user', return_value=True)
    @mock.patch('exchange.web_engage.tasks.task_send_user_data_to_web_engage.delay')
    def test_correctness(self, send_user_data_to_web_engage_mock: mock.MagicMock, mock2, mock3):
        user0, user1, user2 = list(
            User.objects.order_by('id')[:3]
        )

        UpdateWebEngageUserData().run()
        send_user_data_to_web_engage_mock.assert_not_called()

        create_trade(user0, user1, TETHER, RIAL, '0.01', None)

        UpdateWebEngageUserData().run()
        send_user_data_to_web_engage_mock.assert_has_calls([
            mock.call(user1.id, ),
            mock.call(user0.id, ),
        ], any_order=False)

        with self.assertRaises(AssertionError):
            send_user_data_to_web_engage_mock.assert_called_with(user2.id)

    @mock.patch('exchange.web_engage.externals.web_engage.is_web_engage_active', return_value=False)
    @mock.patch('exchange.web_engage.services.user.is_webengage_user', return_value=True)
    @mock.patch('exchange.web_engage.tasks.task_send_user_data_to_web_engage.delay')
    def test_ignore_on_testnet(self, task_send_user_data_to_web_engage_mock: mock.MagicMock, mock2, mock3):
        user0, user1 = list(User.objects.order_by('id')[:2])

        create_trade(user0, user1, TETHER, RIAL, '0.01', None)

        UpdateWebEngageUserData().run()
        task_send_user_data_to_web_engage_mock.assert_not_called()
