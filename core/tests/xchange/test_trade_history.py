import datetime
import random
import string
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import TestCase
from requests.exceptions import HTTPError

from exchange.accounts.models import User
from exchange.base.calendar import get_latest_time, ir_now, ir_today
from exchange.base.logstash_logging.loggers import logstash_logger
from exchange.base.models import Currencies, Settings, get_currency_codename
from exchange.xchange.crons import XchangeCollectTradesFromMarketMakerCron
from exchange.xchange.exceptions import ThereIsNoNewTradeError
from exchange.xchange.marketmaker.trade_history import GetTradeHistory
from exchange.xchange.models import ExchangeTrade, MarketMakerTrade
from exchange.xchange.trade_collector import TradeCollector
from exchange.xchange.types import MarketMakerTradeHistoryItem
from tests.xchange.mocks import trades_sample


class TestTradeHistory(TestCase):

    @patch('exchange.xchange.marketmaker.trade_history.Client.request', return_value=trades_sample)
    def test_get_trade_history_successfully(self, mock_request):
        from_date = datetime.datetime.now() - datetime.timedelta(days=60)
        to_date = datetime.datetime.now()
        has_next, trades = GetTradeHistory(from_date=from_date, to_date=to_date).get_trades_history()
        assert has_next == False
        assert len(trades) == len(trades_sample['result']['converts'])
        for i, trade in enumerate(trades):
            assert trade.baseCurrency == trades_sample['result']['converts'][i]['baseCurrency']
            assert trade.quoteCurrency == trades_sample['result']['converts'][i]['quoteCurrency']
            assert trade.quoteId == trades_sample['result']['converts'][i]['quoteId']
            assert trade.referenceCurrency == trades_sample['result']['converts'][i]['referenceCurrency']
            assert trade.createdAt == trades_sample['result']['converts'][i]['createdAt']
            assert trade.convertId == trades_sample['result']['converts'][i]['convertId']
            assert trade.referenceCurrencyAmount == Decimal(
                trades_sample['result']['converts'][i]['referenceCurrencyAmount']
            )
            assert trade.destinationCurrencyAmount == Decimal(
                trades_sample['result']['converts'][i]['destinationCurrencyAmount']
            )
            assert trade.status == trades_sample['result']['converts'][i]['status']
            assert trade.side == trades_sample['result']['converts'][i]['side']
            assert trade.response == trades_sample['result']['converts'][i]

    @patch('exchange.xchange.marketmaker.client.Client.request')
    def test_get_trade_history_expired_request(self, mock_request):
        mock_request.side_effect = HTTPError(
            '400 bad request',
            response={'result': None, 'message': 'bad_request', 'error': 'request is expired', 'hasError': True},
        )
        from_date = datetime.datetime.now() - datetime.timedelta(days=60)
        to_date = datetime.datetime.now()
        with self.assertRaises(HTTPError):
            GetTradeHistory(from_date=from_date, to_date=to_date).get_trades_history()

    @patch('exchange.xchange.marketmaker.trade_history.Client.request')
    def test_extra_field_is_ignored(self, mock_request):
        # add new field to response
        new_trades_sample = trades_sample.copy()
        new_trades_sample['result']['converts'][0]['new_field'] = 10
        mock_request.return_value = new_trades_sample

        from_date = datetime.datetime.now() - datetime.timedelta(days=60)
        to_date = datetime.datetime.now()

        has_next, trades = GetTradeHistory(from_date, to_date).get_trades_history()

        assert not has_next
        assert len(trades) == len(trades_sample['result']['converts'])

        for trade, raw in zip(trades, trades_sample['result']['converts']):
            for field in (
                'baseCurrency',
                'quoteCurrency',
                'quoteId',
                'referenceCurrency',
                'createdAt',
                'convertId',
                'status',
                'side',
            ):
                assert getattr(trade, field) == raw[field]

            assert trade.referenceCurrencyAmount == Decimal(raw['referenceCurrencyAmount'])
            assert trade.destinationCurrencyAmount == Decimal(raw['destinationCurrencyAmount'])
            assert trade.response == raw


class XchangeCollectTradesFromMarketMakerTest(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=202)
        converts = trades_sample['result']['converts']
        self.converts_obj = [MarketMakerTradeHistoryItem(**convert, response=convert) for convert in converts]
        self.trade = MarketMakerTrade.objects.create(
            convert_id='abc123',
            market_maker_created_at=datetime.datetime.now() - datetime.timedelta(hours=1, minutes=1),
        )
        yesterday = ir_today() - datetime.timedelta(days=1)
        self.to_date_used = get_latest_time(yesterday)

    @patch.object(TradeCollector, 'fetch_trades_with_retry')
    def test_run_no_existing_market_maker_trade(self, mock_get_trades_history):
        """
        Test the case when there are no MarketMakerTrade records initially.
        It should pick the 'from_date' from the first ExchangeTrade.
        """
        trade_time = ir_now() - datetime.timedelta(days=2)
        first_trade = ExchangeTrade.objects.create(
            created_at=trade_time,
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            src_amount=0.05,
            dst_amount=800000,
            quote_id=''.join(random.choice(string.ascii_letters) for i in range(10)),
            client_order_id=''.join(random.choice(string.ascii_letters) for i in range(10)),
        )
        ExchangeTrade.objects.create(
            created_at=ir_now() - datetime.timedelta(days=1),
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.eth,
            dst_currency=Currencies.rls,
            src_amount=0.5,
            dst_amount=800000,
            quote_id=''.join(random.choice(string.ascii_letters) for i in range(10)),
            client_order_id=''.join(random.choice(string.ascii_letters) for i in range(10)),
        )
        # Clear MarketMakerTrade in case there's leftover from other tests
        MarketMakerTrade.objects.all().delete()
        mock_get_trades_history.return_value = (False, self.converts_obj)

        TradeCollector().run()
        first_trade.refresh_from_db()
        from_date = first_trade.created_at - TradeCollector.guard

        mock_get_trades_history.assert_called_once_with(from_date=from_date, to_date=self.to_date_used)
        assert MarketMakerTrade.objects.count() == 2

    @patch.object(TradeCollector, 'fetch_trades_with_retry')
    def test_run_existing_market_maker_trade(self, mock_get_trades_history):
        """
        When there's an existing MarketMakerTrade, we should use that as our 'from_date' reference.
        """
        last_collected_trade_date = datetime.datetime.now() - datetime.timedelta(hours=1)
        last_collected_trade = MarketMakerTrade.objects.create(
            convert_id='abc123',
            market_maker_created_at=last_collected_trade_date,
        )

        mock_get_trades_history.return_value = (False, [])

        TradeCollector().run()

        # Check that we called GetTradeHistory with the from_date from 'existing_trade.market_maker_created_at - guard'
        last_collected_trade.refresh_from_db()
        from_date_used = last_collected_trade.market_maker_created_at - TradeCollector.guard

        mock_get_trades_history.assert_called_with(from_date=from_date_used, to_date=self.to_date_used)

    @patch.object(GetTradeHistory, 'get_trades_history')
    def test_run_with_new_trades(self, mock_get_trades_history):
        """
        Test scenario where new trades are fetched and stored in MarketMakerTrade.
        """

        mock_get_trades_history.return_value = (False, self.converts_obj)

        TradeCollector().run()

        assert MarketMakerTrade.objects.count() == 3
        collected_trade = self.converts_obj[1]
        saved_trade = MarketMakerTrade.objects.get(convert_id=collected_trade.convertId)
        assert collected_trade.baseCurrency == get_currency_codename(saved_trade.base_currency) == 'alpha'
        assert collected_trade.quoteCurrency == get_currency_codename(saved_trade.quote_currency) == 'rls'
        assert collected_trade.referenceCurrency == get_currency_codename(saved_trade.reference_currency) == 'alpha'
        assert (
            Decimal(collected_trade.referenceCurrencyAmount)
            == saved_trade.reference_currency_amount
            == Decimal('2499979.03')
        )
        assert (
            Decimal(collected_trade.destinationCurrencyAmount)
            == saved_trade.destination_currency_amount
            == Decimal('89.74')
        )
        assert collected_trade.createdAt == saved_trade.market_maker_created_at.timestamp() * 1000
        assert collected_trade.quoteId == saved_trade.quote_id == 'alpharls-buy-a127c1885a5f4bbbb8a018e6b1e6d992'
        assert collected_trade.clientId == saved_trade.client_id == 'efc045fa4340418fb6ff57bf1fa8cd4f'
        assert collected_trade.status == saved_trade.status == 'waiting'
        assert collected_trade.side == 'sell' if saved_trade.is_sell else 'buy' == 'buy'
        assert collected_trade.response == saved_trade.market_maker_response == trades_sample['result']['converts'][1]

    @patch.object(logstash_logger, 'error')
    @patch.object(GetTradeHistory, 'get_trades_history')
    def test_retry_on_exception(self, mock_get_trades_history, mock_logger_error):
        """
        Test that the fetch method retries upon an exception, up to max_retries.
        """
        # Simulate throwing exception first time, then success second time
        # The second call returns (False, []) meaning no trades and no next page
        mock_get_trades_history.side_effect = [Exception('First call fails'), (False, [])]

        TradeCollector().run()

        assert mock_get_trades_history.call_count == 2
        assert mock_logger_error.call_count == 1
        mock_logger_error.assert_called_with(
            'Error fetching trades',
            extra={
                'params': {
                    'attempt': 1,
                    'from_data': (self.trade.market_maker_created_at - TradeCollector.guard).timestamp(),
                    'to_data': self.to_date_used.timestamp(),
                    'error': 'First call fails',
                },
                'index_name': 'convert.fetch_marketmaker_trades',
            },
        )

    @patch.object(logstash_logger, 'error')
    @patch.object(GetTradeHistory, 'get_trades_history')
    def test_max_retries_exhausted(self, mock_get_trades_history, mock_logger_error):
        """
        Test that the job raises an exception after max_retries calls fail.
        """
        # All calls should fail
        mock_get_trades_history.side_effect = Exception('Always fails')

        with self.assertRaises(Exception) as context:
            TradeCollector().run()

        # Ensure get_trades_history was called `max_retries` times
        assert mock_get_trades_history.call_count == TradeCollector.max_retries
        assert 'Always fails' in str(context.exception)
        assert mock_logger_error.call_count == TradeCollector.max_retries + 1

    @patch.object(GetTradeHistory, 'get_trades_history')
    @patch.object(TradeCollector, 'page_size', new=2)
    def test_save_duplicate_trades(self, mock_get_trades_history):
        """
        We are sending the same object to store in the db, but it should only be updated and no new data should be stored.
        """
        mock_get_trades_history.return_value = (False, self.converts_obj)

        TradeCollector().run()

        assert MarketMakerTrade.objects.count() == 3
        collected_trade = self.converts_obj[0]
        saved_trade = MarketMakerTrade.objects.get(convert_id=collected_trade.convertId)
        assert collected_trade.baseCurrency == get_currency_codename(saved_trade.base_currency) == 'bnt'
        assert collected_trade.quoteCurrency == get_currency_codename(saved_trade.quote_currency) == 'rls'
        assert collected_trade.referenceCurrency == get_currency_codename(saved_trade.reference_currency) == 'bnt'
        assert (
            Decimal(collected_trade.referenceCurrencyAmount)
            == saved_trade.reference_currency_amount
            == Decimal('2499363.99')
        )
        assert (
            Decimal(collected_trade.destinationCurrencyAmount)
            == saved_trade.destination_currency_amount
            == Decimal('7.02')
        )
        assert collected_trade.createdAt == saved_trade.market_maker_created_at.timestamp() * 1000 == 1744105991663
        assert collected_trade.quoteId == saved_trade.quote_id == 'bntrls-buy-0157050a84ed40adb00624d92038b751'
        assert collected_trade.clientId == saved_trade.client_id == '0e3693f075644fd08c5d3c6255705489'
        assert collected_trade.status == saved_trade.status == 'waiting'
        assert collected_trade.side == 'sell' if saved_trade.is_sell else 'buy' == 'buy'
        assert collected_trade.response == saved_trade.market_maker_response == trades_sample['result']['converts'][0]
        updated_sample = trades_sample.copy()

        mock_get_trades_history.return_value = (False, self.converts_obj)
        # If there is no new data.
        with pytest.raises(ThereIsNoNewTradeError):
            TradeCollector().run()
        assert MarketMakerTrade.objects.count() == 3

        # The status changes from waiting to done and the updated object must be saved.
        updated_sample['result']['converts'][0]['status'] = 'done'
        updated_sample['result']['converts'][1]['convertId'] = '9c7eaab824ee48asdgfasfgba1078faa6'
        updated_convert_obj = [
            MarketMakerTradeHistoryItem(**convert, response=convert) for convert in updated_sample['result']['converts']
        ]
        mock_get_trades_history.return_value = (False, updated_convert_obj)

        TradeCollector().run()
        # New data should be added and status should be updated
        assert MarketMakerTrade.objects.count() == 4
        collected_trade = updated_convert_obj[0]
        saved_trade = MarketMakerTrade.objects.get(convert_id=collected_trade.convertId)
        assert collected_trade.baseCurrency == get_currency_codename(saved_trade.base_currency) == 'bnt'
        assert collected_trade.quoteCurrency == get_currency_codename(saved_trade.quote_currency) == 'rls'
        assert collected_trade.referenceCurrency == get_currency_codename(saved_trade.reference_currency) == 'bnt'
        assert (
            Decimal(collected_trade.referenceCurrencyAmount)
            == saved_trade.reference_currency_amount
            == Decimal('2499363.99')
        )
        assert (
            Decimal(collected_trade.destinationCurrencyAmount)
            == saved_trade.destination_currency_amount
            == Decimal('7.02')
        )
        assert collected_trade.createdAt == saved_trade.market_maker_created_at.timestamp() * 1000 == 1744105991663
        assert collected_trade.quoteId == saved_trade.quote_id == 'bntrls-buy-0157050a84ed40adb00624d92038b751'
        assert collected_trade.clientId == saved_trade.client_id == '0e3693f075644fd08c5d3c6255705489'
        assert collected_trade.status == saved_trade.status == 'done'  # this should be updated from waiting
        assert collected_trade.side == 'sell' if saved_trade.is_sell else 'buy' == 'buy'
        assert collected_trade.response == saved_trade.market_maker_response == updated_sample['result']['converts'][0]

    @patch.object(GetTradeHistory, 'get_trades_history')
    def test_add_new_data_by_cron(self, mock_get_trades_history):
        mock_get_trades_history.return_value = (False, self.converts_obj)
        Settings.set('is_active_collect_trades_from_market_maker_cron', 'yes')
        assert MarketMakerTrade.objects.count() == 1
        XchangeCollectTradesFromMarketMakerCron().run()
        assert MarketMakerTrade.objects.count() == 3

    @patch.object(GetTradeHistory, 'get_trades_history')
    def test_cron_can_not_run_without_flag(self, mock_get_trades_history):
        mock_get_trades_history.return_value = (False, self.converts_obj)
        assert not Settings.get_flag('is_active_collect_trades_from_market_maker_cron')
        XchangeCollectTradesFromMarketMakerCron().run()
        assert MarketMakerTrade.objects.count() == 1
        Settings.set('is_active_collect_trades_from_market_maker_cron', 'yes')
        XchangeCollectTradesFromMarketMakerCron().run()
        assert MarketMakerTrade.objects.count() == 3

    @patch.object(GetTradeHistory, 'get_trades_history')
    def test_active_cron_flag_after_script_ended(self, mock_get_trades_history):
        mock_get_trades_history.return_value = (False, self.converts_obj)
        assert not Settings.get_flag('is_active_collect_trades_from_market_maker_cron')
        assert MarketMakerTrade.objects.count() == 1
        call_command('xchange__collect_marketmaker_trades')
        assert MarketMakerTrade.objects.count() == 3
        assert Settings.get_flag('is_active_collect_trades_from_market_maker_cron')
