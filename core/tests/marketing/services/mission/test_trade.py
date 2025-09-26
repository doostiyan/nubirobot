import random
import string
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies, Settings
from exchange.marketing.exceptions import InvalidUserIDException
from exchange.marketing.services.campaign.base import CAMPAIGNS_SETTINGS_KEY
from exchange.marketing.services.mission.trade import MissionProgressStatus, TradeMission
from exchange.marketing.types import UserInfo
from exchange.xchange.models import ExchangeTrade
from tests.base.utils import create_trade


class TradeMissionTest(TestCase):
    def setUp(self):
        current_time = ir_now()

        self.mission = TradeMission()
        self.user1 = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)

        self.user_info = UserInfo(
            user_id=self.user1.pk,
            mobile_number=self.user1.mobile,
            webengage_id=self.user1.get_webengage_id(),
            level=self.user1.user_type,
        )

        self.validity_duration = 10 * 24 * 60 * 60  # 10 days
        self.campaign_id = "pizza_campaign"
        self.campaign_settings = {
            'currency': Currencies.btc,
            'start_time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'end_time': (current_time + timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S'),
            'threshold_amount': 10000000,  # rials
            'reward_sms_template': 'sample_template',
        }

        Settings.set_dict(f'{CAMPAIGNS_SETTINGS_KEY}', {self.campaign_id: self.campaign_settings})

    def tearDown(self):
        cache.clear()
        Settings.set_dict(f'{CAMPAIGNS_SETTINGS_KEY}', {})

    def test_initiate_no_trade_success(self):
        # when ->
        result = self.mission.initiate(self.user_info, self.campaign_id)

        # then->
        assert result['status'] == MissionProgressStatus.IN_PROGRESS.value
        assert 'remained_amount' in result
        assert result['remained_amount'] == self.campaign_settings.get('threshold_amount')
        assert result['user_level'] == self.user1.user_type

        cache_key = self.mission._get_cache_key(self.campaign_id, self.user_info.user_id)
        cached_data = cache.get(cache_key)
        assert cached_data is not None
        assert 'timestamp' in cached_data

    def test_initiate_invalid_user(self):
        # given->
        invalid_user_info = UserInfo(user_id=None)

        # when->
        with self.assertRaises(InvalidUserIDException) as context:
            self.mission.initiate(invalid_user_info, self.campaign_id)

        # then->
        assert str(context.exception) == 'user must have user id'

    def test_initiate_existing_record_success(self):
        # given->
        first_result = self.mission.initiate(self.user_info, self.campaign_id)
        first_timestamp = cache.get(self.mission._get_cache_key(self.campaign_id, self.user_info.user_id))['timestamp']

        # when->
        second_result = self.mission.initiate(self.user_info, self.campaign_id)
        second_timestamp = cache.get(self.mission._get_cache_key(self.campaign_id, self.user_info.user_id))['timestamp']

        # then->
        assert second_result['status'] == MissionProgressStatus.IN_PROGRESS.value
        assert first_result['status'] == second_result['status']
        assert first_result['remained_amount'] == second_result['remained_amount']
        assert first_result['user_level'] == second_result['user_level']
        assert first_timestamp == second_timestamp

    def test_is_done_when_not_started(self):
        assert self.mission.is_done(self.user_info, self.campaign_id) == False

    def test_is_done_when_in_progress(self):
        self.mission.initiate(self.user_info, self.campaign_id)
        assert self.mission.is_done(self.user_info, self.campaign_id) == False

    def test_is_done_when_completed(self):
        # given->
        self.mission.initiate(self.user_info, self.campaign_id)
        join_timestamp = cache.get(self.mission._get_cache_key(self.campaign_id, self.user_info.user_id))['timestamp']
        trade_date = join_timestamp + timedelta(hours=1)
        _trade_1 = create_trade(
            seller=self.user2,
            buyer=self.user1,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            amount=0.05,
            price=1000000000,
            created_at=trade_date,
        )
        # when->
        is_done = self.mission.is_done(self.user_info, self.campaign_id)

        # then->
        assert is_done == True

    def test_is_done_when_trade_is_done_before_join_campaign(self):
        # given->
        self.mission.initiate(self.user_info, self.campaign_id)
        join_timestamp = cache.get(self.mission._get_cache_key(self.campaign_id, self.user_info.user_id))['timestamp']
        trade_date = join_timestamp - timedelta(hours=1)
        _trade_1 = create_trade(
            seller=self.user2,
            buyer=self.user1,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            amount=0.05,
            price=1000000000,
            created_at=trade_date,
        )
        # when->
        is_done = self.mission.is_done(self.user_info, self.campaign_id)

        # then->
        assert is_done == False

    def test_get_progress_details_not_started(self):
        # when->
        result = self.mission.get_progress_details(self.user_info, self.campaign_id)
        # then->
        assert result['status'] == MissionProgressStatus.NOT_STARTED.value

    def test_get_progress_details_in_progress_without_trade(self):
        # given->
        self.mission.initiate(self.user_info, self.campaign_id)
        # when->
        result = self.mission.get_progress_details(self.user_info, self.campaign_id)
        # then->
        assert result['status'] == MissionProgressStatus.IN_PROGRESS.value
        assert 'remained_amount' in result
        assert result['remained_amount'] == self.campaign_settings['threshold_amount']
        assert result['user_level'] == self.user1.user_type

    def test_get_progress_details_in_progress_with_trade_amount_less_than_threshold(self):
        # given->
        self.mission.initiate(self.user_info, self.campaign_id)
        trade_amount = 4000000
        join_timestamp = cache.get(self.mission._get_cache_key(self.campaign_id, self.user_info.user_id))['timestamp']
        trade_date = join_timestamp + timedelta(hours=1)
        _trade_1 = create_trade(
            seller=self.user2,
            buyer=self.user1,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            amount=1,
            price=trade_amount,
            created_at=trade_date,
        )
        # when->
        result = self.mission.get_progress_details(self.user_info, self.campaign_id)
        # then->
        assert result['status'] == MissionProgressStatus.IN_PROGRESS.value
        assert 'remained_amount' in result
        assert result['remained_amount'] == self.campaign_settings['threshold_amount'] - trade_amount
        assert result['user_level'] == self.user1.user_type

    def test_get_progress_details_done(self):
        # given->
        self.mission.initiate(self.user_info, self.campaign_id)
        join_timestamp = cache.get(self.mission._get_cache_key(self.campaign_id, self.user_info.user_id))['timestamp']
        trade_date = join_timestamp + timedelta(hours=1)
        _trade_1 = create_trade(
            seller=self.user2,
            buyer=self.user1,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            amount=1,
            price=self.campaign_settings['threshold_amount'],
            created_at=trade_date,
        )
        # when->
        result = self.mission.get_progress_details(self.user_info, self.campaign_id)
        # then->
        assert result['status'] == MissionProgressStatus.DONE.value
        assert result['remained_amount'] == 0
        assert result['user_level'] == self.user1.user_type

    @patch('exchange.marketing.services.mission.trade.UDFHistory.get_history')
    def test_get_total_trade_in_time(self, usdt_price_converter_mock):
        # given->
        current_time = ir_now()
        start_time = current_time - timedelta(hours=1)
        end_time = current_time + timedelta(hours=1)

        ##### Market Trades #####

        # Valid market trade within time range
        _trade_1 = create_trade(
            seller=self.user2,
            buyer=self.user1,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            amount=1,
            price=3000000,
            created_at=current_time + timedelta(minutes=10),
        )

        # Trade outside time range (should be ignored)
        _trade_2 = create_trade(
            seller=self.user2,
            buyer=self.user1,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            amount=1,
            price=4000000,
            created_at=current_time + timedelta(minutes=61),
        )

        ##### Exchange Trades #####

        # Valid exchange trade within time range (rls)
        ExchangeTrade.objects.create(
            created_at=current_time + timedelta(minutes=12),
            user=self.user1,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            src_amount=0.5,
            dst_amount=8000000,
            quote_id=''.join(random.choice(string.ascii_letters) for i in range(10)),
            client_order_id=''.join(random.choice(string.ascii_letters) for i in range(10)),
        )

        # Valid exchange trade within time range (usdt)
        last_trade = ExchangeTrade.objects.create(
            created_at=current_time + timedelta(minutes=15),
            user=self.user1,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=0.5,
            dst_amount=10,
            quote_id=''.join(random.choice(string.ascii_letters) for i in range(10)),
            client_order_id=''.join(random.choice(string.ascii_letters) for i in range(10)),
        )
        start_timestamp = int(last_trade.created_at.replace(second=0, microsecond=0).timestamp())
        end_timestamp = int(last_trade.created_at.replace(second=59, microsecond=999999).timestamp())
        usdt_price_converter_mock.return_value = {'h': [80000]}  # one usdt is 80,000 irt

        # when->
        result = self.mission._get_total_trade_in_time(self.user_info.user_id, Currencies.btc, start_time, end_time)
        usdt_price_converter_mock.assert_called_once_with('USDTIRT', '1', start_timestamp, end_timestamp)

        # then->
        assert result == Decimal(19000000)
