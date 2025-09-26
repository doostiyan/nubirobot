import contextlib
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.calendar import get_earliest_time, get_latest_time, ir_now
from exchange.base.models import RIAL, Currencies
from exchange.xchange import exceptions
from exchange.xchange.crons import XchangeBatchConvertSmallAssetsCron
from exchange.xchange.models import ExchangeTrade, MarketStatus, SmallAssetConvert
from exchange.xchange.small_asset_batch_convertor import SmallAssetBatchConvertor
from exchange.xchange.types import RequiredCurrenciesInConvert


class TestSmallAssetBatchConvertor(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create(
            username='xchange_small_asset_convertor_test',
            user_type=User.USER_TYPE_LEVEL1,
        )

        self.xchange_currency = Currencies.ygg

        self.market_status = MarketStatus.objects.create(
            base_currency=self.xchange_currency,
            quote_currency=RIAL,
            base_to_quote_price_buy=2.2,
            quote_to_base_price_buy=3.2,
            base_to_quote_price_sell=1.2,
            quote_to_base_price_sell=1.2,
            min_base_amount=10,
            max_base_amount=100,
            min_quote_amount=5,
            max_quote_amount=500,
            base_precision=Decimal('1e-4'),
            quote_precision=Decimal('1e-1'),
            status=MarketStatus.STATUS_CHOICES.available,
        )

        self.small_asset_convert = SmallAssetConvert.objects.create(
            user=self.user,
            src_currency=self.xchange_currency,
            dst_currency=RIAL,
            src_amount=20,
            dst_amount=10,
            status=SmallAssetConvert.STATUS.created,
        )

        self.mock_trade = ExchangeTrade.objects.create(
            user=self.user,
            is_sell=True,
            src_currency=self.xchange_currency,
            dst_currency=RIAL,
            src_amount=0.22,
            dst_amount=455454.2542,
            quote_id='test_quote',
            client_order_id='some_client_order_id',
        )

    @patch('exchange.xchange.small_asset_batch_convertor.UPDATE_SMALL_ASSET_CONVERT_STATUS_COUNTDOWN', 10)
    @patch('exchange.xchange.small_asset_batch_convertor.update_small_asset_convert_status.apply_async')
    @patch('exchange.xchange.small_asset_batch_convertor.logstash_logger.error')
    @patch('exchange.xchange.small_asset_batch_convertor.SmallAssetBatchConvertor._batch_convert_by_market_maker')
    def test_batch_convert_not_enough_records(
        self,
        mock_convert: MagicMock,
        mock_logstash: MagicMock,
        mock_update_task: MagicMock,
    ):
        """Scenario 1: Not enough records for batch convert"""
        self.small_asset_convert.src_amount = 5  # Less than min_base_amount
        self.small_asset_convert.save()

        assert self.small_asset_convert.status == SmallAssetConvert.STATUS.created

        SmallAssetBatchConvertor.batch_convert()

        mock_convert.assert_not_called()
        mock_logstash.assert_not_called()
        mock_update_task.assert_called_once_with(countdown=10)
        assert self.small_asset_convert.status == SmallAssetConvert.STATUS.created

    @patch('exchange.xchange.small_asset_batch_convertor.UPDATE_SMALL_ASSET_CONVERT_STATUS_COUNTDOWN', 10)
    @patch('exchange.xchange.small_asset_batch_convertor.update_small_asset_convert_status.apply_async')
    @patch('exchange.xchange.small_asset_batch_convertor.logstash_logger.error')
    @patch('exchange.xchange.small_asset_batch_convertor.SmallAssetBatchConvertor._batch_convert_by_market_maker')
    def test_batch_convert_no_market(
        self,
        mock_convert: MagicMock,
        mock_logstash: MagicMock,
        mock_update_task: MagicMock,
    ):
        """Scenario 2: No market available"""
        self.small_asset_convert.src_currency = Currencies.btc
        self.small_asset_convert.save()

        assert self.small_asset_convert.status == SmallAssetConvert.STATUS.created

        SmallAssetBatchConvertor.batch_convert()

        mock_convert.assert_not_called()
        mock_logstash.assert_not_called()
        mock_update_task.assert_called_once_with(countdown=10)
        assert self.small_asset_convert.status == SmallAssetConvert.STATUS.created

    @patch('exchange.xchange.small_asset_batch_convertor.UPDATE_SMALL_ASSET_CONVERT_STATUS_COUNTDOWN', 10)
    @patch('exchange.xchange.small_asset_batch_convertor.update_small_asset_convert_status.apply_async')
    @patch('exchange.xchange.small_asset_batch_convertor.logstash_logger.error')
    @patch('exchange.xchange.small_asset_batch_convertor.SmallAssetBatchConvertor._batch_convert_by_market_maker')
    def test_batch_convert_exception_reporting(
        self,
        mock_convert: MagicMock,
        mock_logstash: MagicMock,
        mock_update_task: MagicMock,
    ):
        """Scenario 3: Exception handling and reporting"""
        mock_convert.side_effect = Exception('Test error')

        assert self.small_asset_convert.status == SmallAssetConvert.STATUS.created
        SmallAssetBatchConvertor.batch_convert()

        mock_convert.assert_called_once_with(self.market_status)
        mock_logstash.assert_called_once()
        mock_update_task.assert_called_once_with(countdown=10)
        assert self.small_asset_convert.status == SmallAssetConvert.STATUS.created

    @patch('exchange.xchange.small_asset_batch_convertor.UPDATE_SMALL_ASSET_CONVERT_STATUS_COUNTDOWN', 10)
    @patch('exchange.xchange.small_asset_batch_convertor.update_small_asset_convert_status.apply_async')
    @patch('exchange.xchange.small_asset_batch_convertor.logstash_logger.error')
    @patch('exchange.xchange.small_asset_batch_convertor.XchangeTrader.create_trade')
    @patch('exchange.xchange.small_asset_batch_convertor.XchangeTrader.get_quote')
    def test_batch_convert_successful_update(
        self,
        mock_get_quote,
        mock_create_trade,
        mock_logstash: MagicMock,
        mock_update_task: MagicMock,
    ):
        """Scenario 4: Successful batch convert and record updates"""
        mock_get_quote.return_value = MagicMock(quote_id='test_quote')
        mock_create_trade.return_value = self.mock_trade

        SmallAssetBatchConvertor.batch_convert()

        self.small_asset_convert.refresh_from_db()
        assert self.small_asset_convert.status == SmallAssetConvert.STATUS.in_progress
        assert self.small_asset_convert.related_batch_trade == self.mock_trade
        mock_logstash.assert_not_called()
        mock_update_task.assert_called_once_with(countdown=10)

    @patch('exchange.xchange.small_asset_batch_convertor.get_small_assets_convert_system_user')
    @patch('exchange.xchange.small_asset_batch_convertor.XchangeTrader.create_trade')
    @patch('exchange.xchange.small_asset_batch_convertor.XchangeTrader.get_quote')
    def test_batch_convert_by_market_maker_success(self, mock_get_quote, mock_create_trade, mock_get_system_user):
        """Scenario 5: Successful _batch_convert_by_market_maker"""
        mock_system_user = MagicMock(id=999)
        mock_get_system_user.return_value = mock_system_user
        mock_get_quote.return_value = MagicMock(quote_id='test_quote')
        mock_create_trade.return_value = self.mock_trade

        SmallAssetBatchConvertor._batch_convert_by_market_maker(self.market_status)

        # Assert get_quote inputs
        mock_get_quote.assert_called_once_with(
            currencies=RequiredCurrenciesInConvert(base=self.xchange_currency, quote=RIAL, ref=self.xchange_currency),
            is_sell=True,
            amount=20,  # src_amount from the record
            user=mock_system_user,
            market_status=self.market_status,
        )

        # Assert create_trade inputs
        mock_create_trade.assert_called_once_with(
            user_id=mock_system_user.id,
            quote_id='test_quote',
            user_agent=ExchangeTrade.USER_AGENT.system,
            bypass_market_limit_validation=True,
            allow_user_wallet_negative_balance=True,
        )

        # Assert record updates
        self.small_asset_convert.refresh_from_db()
        assert self.small_asset_convert.status == SmallAssetConvert.STATUS.in_progress
        assert self.small_asset_convert.related_batch_trade == self.mock_trade

    @patch('exchange.xchange.small_asset_batch_convertor.XchangeTrader.get_quote')
    def test_batch_convert_by_market_maker_get_quote_exception(self, mock_get_quote):
        """Scenario 6: Exception in get_quote"""
        mock_get_quote.side_effect = requests.HTTPError('HTTP error occurred')

        with pytest.raises(requests.HTTPError, match='HTTP error occurred'):
            SmallAssetBatchConvertor._batch_convert_by_market_maker(self.market_status)

    @patch('exchange.xchange.small_asset_batch_convertor.XchangeTrader.create_trade')
    @patch('exchange.xchange.small_asset_batch_convertor.XchangeTrader.get_quote')
    def test_batch_convert_by_market_maker_create_trade_exception(self, mock_get_quote, mock_create_trade):
        """Scenario 7: Exception in create_trade"""
        mock_get_quote.return_value = MagicMock(quote_id='test_quote')
        mock_create_trade.side_effect = exceptions.MarketUnavailable('Market is not available.')

        with pytest.raises(exceptions.MarketUnavailable, match='Market is not available.'):
            SmallAssetBatchConvertor._batch_convert_by_market_maker(self.market_status)

    @patch('exchange.xchange.small_asset_batch_convertor.XchangeTrader.create_trade')
    @patch('exchange.xchange.small_asset_batch_convertor.XchangeTrader.get_quote')
    def test_batch_convert_by_market_maker_atomicity(self, mock_get_quote, mock_create_trade):
        """Scenario 8: Transaction atomicity"""
        mock_get_quote.return_value = MagicMock(quote_id='test_quote')
        mock_create_trade.side_effect = Exception('Simulated error')

        assert self.small_asset_convert.status == SmallAssetConvert.STATUS.created
        assert self.small_asset_convert.related_batch_trade is None

        with contextlib.suppress(Exception):
            SmallAssetBatchConvertor._batch_convert_by_market_maker(self.market_status)

        self.small_asset_convert.refresh_from_db()
        # Due to transaction.atomic, record should remain unchanged
        assert self.small_asset_convert.status == SmallAssetConvert.STATUS.created
        assert self.small_asset_convert.related_batch_trade is None

    @patch('exchange.xchange.small_asset_batch_convertor.update_small_asset_convert_status.apply_async', MagicMock())
    @patch('exchange.xchange.small_asset_batch_convertor.XchangeTrader.create_trade')
    @patch('exchange.xchange.small_asset_batch_convertor.XchangeTrader.get_quote')
    def test_batch_convert_checks_both_statuses(self, mock_get_quote, mock_create_trade):
        """Scenario 9: Check if both failed and created statuses are considered"""
        SmallAssetConvert.objects.all().delete()

        record1 = SmallAssetConvert.objects.create(
            user=self.user,
            src_currency=self.xchange_currency,
            dst_currency=RIAL,
            src_amount=8,  # Less than min_base_amount
            dst_amount=10,
            status=SmallAssetConvert.STATUS.failed,
        )

        record2 = SmallAssetConvert.objects.create(
            user=self.user,
            src_currency=self.xchange_currency,
            dst_currency=RIAL,
            src_amount=8,  # Less than min_base_amount
            dst_amount=10,
            status=SmallAssetConvert.STATUS.failed,
        )

        mock_get_quote.return_value = MagicMock(quote_id='test_quote')
        mock_create_trade.return_value = self.mock_trade

        SmallAssetBatchConvertor.batch_convert()

        record1.refresh_from_db()
        record2.refresh_from_db()

        assert record1.status == SmallAssetConvert.STATUS.in_progress
        assert record1.related_batch_trade == self.mock_trade
        assert record2.status == SmallAssetConvert.STATUS.in_progress
        assert record2.related_batch_trade == self.mock_trade

    @patch('exchange.xchange.small_asset_batch_convertor.update_small_asset_convert_status.apply_async', MagicMock())
    @patch('exchange.xchange.small_asset_batch_convertor.logstash_logger.error')
    @patch('exchange.xchange.small_asset_batch_convertor.SmallAssetBatchConvertor._batch_convert_by_market_maker')
    def test_batch_convert_multiple_market_records(self, mock_convert: MagicMock, mock_logstash: MagicMock):
        eth_market_status = MarketStatus.objects.create(
            base_currency=Currencies.eth,
            quote_currency=RIAL,
            base_to_quote_price_buy=2.2,
            quote_to_base_price_buy=3.2,
            base_to_quote_price_sell=1.2,
            quote_to_base_price_sell=1.2,
            min_base_amount=10,
            max_base_amount=100,
            min_quote_amount=5,
            max_quote_amount=500,
            base_precision=Decimal('1e-4'),
            quote_precision=Decimal('1e-1'),
            status=MarketStatus.STATUS_CHOICES.available,
        )

        SmallAssetConvert.objects.create(
            user=self.user,
            src_currency=Currencies.eth,
            dst_currency=RIAL,
            src_amount=20,
            dst_amount=10,
            status=SmallAssetConvert.STATUS.created,
        )

        dai_market_status = MarketStatus.objects.create(
            base_currency=Currencies.dai,
            quote_currency=RIAL,
            base_to_quote_price_buy=2.2,
            quote_to_base_price_buy=3.2,
            base_to_quote_price_sell=1.2,
            quote_to_base_price_sell=1.2,
            min_base_amount=10,
            max_base_amount=100,
            min_quote_amount=5,
            max_quote_amount=500,
            base_precision=Decimal('1e-4'),
            quote_precision=Decimal('1e-1'),
            status=MarketStatus.STATUS_CHOICES.available,
        )

        SmallAssetConvert.objects.create(
            user=self.user,
            src_currency=Currencies.dai,
            dst_currency=RIAL,
            src_amount=8,
            dst_amount=5,
            status=SmallAssetConvert.STATUS.created,
        )

        SmallAssetBatchConvertor.batch_convert()

        assert mock_convert.call_count == 2
        # Get all calls and their arguments
        calls_args = [call.args[0] for call in mock_convert.call_args_list]
        # Check both market statuses were called, regardless of order
        assert self.market_status in calls_args
        assert eth_market_status in calls_args
        assert dai_market_status not in calls_args

        mock_logstash.assert_not_called()

    @patch(
        'exchange.xchange.small_asset_batch_convertor.SMALL_ASSET_BATCH_CONVERT_MAX_AMOUNT_THRESHOLD_RATIO',
        Decimal('0.8'),
    )
    @patch('exchange.xchange.small_asset_batch_convertor.logstash_logger.info')
    @patch('exchange.xchange.small_asset_batch_convertor.get_small_assets_convert_system_user')
    @patch('exchange.xchange.small_asset_batch_convertor.XchangeTrader.create_trade')
    @patch('exchange.xchange.small_asset_batch_convertor.XchangeTrader.get_quote')
    def test_batch_convert_by_market_maker_limit_to_max_base_amount(
        self,
        mock_get_quote: MagicMock,
        mock_create_trade: MagicMock,
        mock_get_system_user: MagicMock,
        mock_logstash_logger: MagicMock,
    ):
        mock_system_user = MagicMock(id=999)
        mock_get_system_user.return_value = mock_system_user
        mock_get_quote.return_value = MagicMock(quote_id='test_quote')
        mock_create_trade.return_value = self.mock_trade

        SmallAssetConvert.objects.all().delete()

        now = ir_now()

        small_asset_convert1 = SmallAssetConvert.objects.create(
            user=self.user,
            src_currency=self.xchange_currency,
            dst_currency=RIAL,
            src_amount=35,
            dst_amount=10,
            status=SmallAssetConvert.STATUS.created,
            created_at=get_earliest_time(now),
        )

        small_asset_convert2 = SmallAssetConvert.objects.create(
            user=self.user,
            src_currency=self.xchange_currency,
            dst_currency=RIAL,
            src_amount=35,
            dst_amount=10,
            status=SmallAssetConvert.STATUS.created,
            created_at=get_earliest_time(now) + timedelta(hours=12),
        )

        small_asset_convert3 = SmallAssetConvert.objects.create(
            user=self.user,
            src_currency=self.xchange_currency,
            dst_currency=RIAL,
            src_amount=35,
            dst_amount=10,
            status=SmallAssetConvert.STATUS.created,
            created_at=get_latest_time(now),
        )

        SmallAssetBatchConvertor._batch_convert_by_market_maker(self.market_status)

        # Assert get_quote inputs
        mock_get_quote.assert_called_once_with(
            currencies=RequiredCurrenciesInConvert(base=self.xchange_currency, quote=RIAL, ref=self.xchange_currency),
            is_sell=True,
            amount=70,  # src_amount from the records
            user=mock_system_user,
            market_status=self.market_status,
        )

        # Assert create_trade inputs
        mock_create_trade.assert_called_once_with(
            user_id=mock_system_user.id,
            quote_id='test_quote',
            user_agent=ExchangeTrade.USER_AGENT.system,
            bypass_market_limit_validation=True,
            allow_user_wallet_negative_balance=True,
        )

        # Assert record updates
        small_asset_convert1.refresh_from_db()
        small_asset_convert2.refresh_from_db()
        small_asset_convert3.refresh_from_db()

        assert small_asset_convert1.status == SmallAssetConvert.STATUS.in_progress
        assert small_asset_convert1.related_batch_trade == self.mock_trade

        assert small_asset_convert2.status == SmallAssetConvert.STATUS.in_progress
        assert small_asset_convert2.related_batch_trade == self.mock_trade

        assert small_asset_convert3.status == SmallAssetConvert.STATUS.created
        assert small_asset_convert3.related_batch_trade is None

        mock_logstash_logger.assert_called_once()


class TestXchangeBatchConvertSmallAssetsCron(TestCase):
    @patch('exchange.xchange.crons.SmallAssetBatchConvertor.batch_convert')
    def test_batch_convert_small_assets(self, mock_convert):
        XchangeBatchConvertSmallAssetsCron().run()

        mock_convert.assert_called_once()
