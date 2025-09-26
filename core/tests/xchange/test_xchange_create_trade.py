import decimal
import functools
from unittest import mock

import pytest
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.wallet.helpers import RefMod
from exchange.wallet.models import Transaction
from exchange.xchange import exceptions
from exchange.xchange.marketmaker.convertor import Conversion
from exchange.xchange.marketmaker.quotes import Quote
from exchange.xchange.models import ExchangeTrade, MarketStatus
from exchange.xchange.trader import XchangeTrader


def _patch(test):
    patch_prefix = 'exchange.xchange.trader'

    @functools.wraps(test)
    @mock.patch(patch_prefix + '.XchangeTrader._schedule_get_conversion_task')
    @mock.patch(patch_prefix + '.Estimator.get_quote')
    @mock.patch(patch_prefix + '.XchangeTrader._check_balances', lambda *args, **kwargs: None)
    @mock.patch(patch_prefix + '.report_event')
    @mock.patch(patch_prefix + '.Convertor.call_conversion_api')
    @mock.patch(patch_prefix + '.ExchangeTrade.objects.create')
    @mock.patch(patch_prefix + '.XchangeTrader.create_and_commit_wallet_transactions')
    @mock.patch(patch_prefix + '.Estimator.invalidate_quote')
    def decorated(*args, **kwargs):
        return test(*args, **kwargs)

    return decorated


class CreateTradeTest(TestCase):

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user_id = 10
        cls.quote_id = 'this_is_a_quote_id'
        cls.common_kwargs = {
            'quote_id': cls.quote_id,
            'base_currency': Currencies.btc,
            'quote_currency': Currencies.usdt,
            'reference_currency': Currencies.usdt,
            'reference_amount': decimal.Decimal('100.22'),
            'destination_amount': decimal.Decimal('0.022'),
            'is_sell': False,
            'client_order_id': 'some_client_order_id',
        }
        cls.conversion = Conversion(**{**cls.common_kwargs, 'convert_id': 'some_convert_id'})
        cls.quote = Quote(**{**cls.common_kwargs, 'user_id': cls.user_id, 'expires_at': ir_now()})
        cls.market = MarketStatus.objects.create(
            base_currency=Currencies.btc,
            quote_currency=Currencies.usdt,
            base_to_quote_price_buy=2.2,
            quote_to_base_price_buy=3.2,
            base_to_quote_price_sell=1.2,
            quote_to_base_price_sell=1.2,
            min_base_amount=0.001,
            max_base_amount=20,
            min_quote_amount=5,
            max_quote_amount=500,
            base_precision=decimal.Decimal('1e-4'),
            quote_precision=decimal.Decimal('1e-1'),
            status=MarketStatus.STATUS_CHOICES.available,
        )

    def setUp(self) -> None:
        self.exchange_trade = type('ExchangeTrade', (), {'convert_id': ''})

    @_patch
    def test_a_successful_call(
        self,
        estimator_invalidate_quote_mock: mock.MagicMock,
        xchange_trader_create_and_commit_wallet_transactions_mock: mock.MagicMock,
        exchange_trade_objects_create_mock: mock.MagicMock,
        convertor_call_conversion_api_mock: mock.MagicMock,
        report_event_mock: mock.MagicMock,
        estimator_get_quote_mock: mock.MagicMock,
        schedule_get_conversion_task_mock: mock.MagicMock,
    ):
        estimator_get_quote_mock.return_value = self.quote
        convertor_call_conversion_api_mock.return_value = self.conversion
        exchange_trade_objects_create_mock.return_value = self.exchange_trade
        created_trade = XchangeTrader.create_trade(self.user_id, self.quote_id, ExchangeTrade.USER_AGENT.unknown)
        assert self.exchange_trade == created_trade
        assert self.conversion.convert_id == created_trade.convert_id
        estimator_get_quote_mock.assert_called_once_with(self.quote_id, self.user_id)
        report_event_mock.assert_not_called()
        convertor_call_conversion_api_mock.assert_called_once_with(self.quote)
        exchange_trade_objects_create_mock.assert_called_once_with(
            is_sell=False,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=decimal.Decimal('0.022'),
            dst_amount=decimal.Decimal('100.22'),
            quote_id='this_is_a_quote_id',
            client_order_id='some_client_order_id',
            user_id=10,
            user_agent=ExchangeTrade.USER_AGENT.unknown,
        )
        xchange_trader_create_and_commit_wallet_transactions_mock.assert_called_once_with(
            self.exchange_trade,
            allow_user_wallet_negative_balance=False,
        )
        estimator_invalidate_quote_mock.assert_called_once_with(self.quote_id, self.user_id)
        schedule_get_conversion_task_mock.assert_not_called()

    @_patch
    def test_invalid_quote_id(
        self,
        estimator_invalidate_quote_mock: mock.MagicMock,
        xchange_trader_create_and_commit_wallet_transactions_mock: mock.MagicMock,
        exchange_trade_objects_create_mock: mock.MagicMock,
        convertor_call_conversion_api_mock: mock.MagicMock,
        report_event_mock: mock.MagicMock,
        estimator_get_quote_mock: mock.MagicMock,
        schedule_get_conversion_task_mock: mock.MagicMock,
    ):
        estimator_get_quote_mock.side_effect = exceptions.QuoteIsNotAvailable('')
        with pytest.raises(exceptions.QuoteIsNotAvailable):
            XchangeTrader.create_trade(self.user_id, self.quote_id, ExchangeTrade.USER_AGENT.unknown)
        report_event_mock.assert_not_called()
        xchange_trader_create_and_commit_wallet_transactions_mock.assert_not_called()
        exchange_trade_objects_create_mock.assert_not_called()
        schedule_get_conversion_task_mock.assert_not_called()

    @_patch
    def test_invalid_quote_user(
        self,
        estimator_invalidate_quote_mock: mock.MagicMock,
        xchange_trader_create_and_commit_wallet_transactions_mock: mock.MagicMock,
        exchange_trade_objects_create_mock: mock.MagicMock,
        convertor_call_conversion_api_mock: mock.MagicMock,
        report_event_mock: mock.MagicMock,
        estimator_get_quote_mock: mock.MagicMock,
        schedule_get_conversion_task_mock: mock.MagicMock,
    ):
        estimator_get_quote_mock.return_value = self.quote
        with pytest.raises(exceptions.QuoteIsNotAvailable):
            XchangeTrader.create_trade(self.user_id + 1, self.quote_id, ExchangeTrade.USER_AGENT.unknown)
        report_event_mock.assert_called_once_with('Convert.QuoteWontMatchUser', extras={'user_id': 11})
        xchange_trader_create_and_commit_wallet_transactions_mock.assert_not_called()
        exchange_trade_objects_create_mock.assert_not_called()
        schedule_get_conversion_task_mock.assert_not_called()

    @_patch
    def test_failed_third_party_api_call(
        self,
        estimator_invalidate_quote_mock: mock.MagicMock,
        xchange_trader_create_and_commit_wallet_transactions_mock: mock.MagicMock,
        exchange_trade_objects_create_mock: mock.MagicMock,
        convertor_call_conversion_api_mock: mock.MagicMock,
        report_event_mock: mock.MagicMock,
        estimator_get_quote_mock: mock.MagicMock,
        schedule_get_conversion_task_mock: mock.MagicMock,
    ):
        estimator_get_quote_mock.return_value = self.quote
        convertor_call_conversion_api_mock.side_effect = exceptions.FailedConversion('msg')
        exchange_trade_objects_create_mock.return_value = self.exchange_trade
        with pytest.raises(exceptions.FailedConversion):
            XchangeTrader.create_trade(self.user_id, self.quote_id, ExchangeTrade.USER_AGENT.unknown)
        xchange_trader_create_and_commit_wallet_transactions_mock.assert_not_called()
        exchange_trade_objects_create_mock.assert_called_once_with(
            is_sell=False,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=decimal.Decimal('0.022'),
            dst_amount=decimal.Decimal('100.22'),
            quote_id='this_is_a_quote_id',
            client_order_id='some_client_order_id',
            user_id=10,
            user_agent=ExchangeTrade.USER_AGENT.unknown,
        )
        assert self.exchange_trade.convert_id == ''
        schedule_get_conversion_task_mock.assert_not_called()

    @_patch
    def test_failed_third_party_api_call_timeout(
        self,
        estimator_invalidate_quote_mock: mock.MagicMock,
        xchange_trader_create_and_commit_wallet_transactions_mock: mock.MagicMock,
        exchange_trade_objects_create_mock: mock.MagicMock,
        convertor_call_conversion_api_mock: mock.MagicMock,
        report_event_mock: mock.MagicMock,
        estimator_get_quote_mock: mock.MagicMock,
        schedule_get_conversion_task_mock: mock.MagicMock,
    ):
        estimator_get_quote_mock.return_value = self.quote
        convertor_call_conversion_api_mock.side_effect = exceptions.ConversionTimeout('msg')
        class Trade:
            pass
        exchange_trade = Trade()
        exchange_trade.pk = object()
        exchange_trade.convert_id = ''
        exchange_trade_objects_create_mock.return_value = exchange_trade
        result_trade = XchangeTrader.create_trade(self.user_id, self.quote_id, ExchangeTrade.USER_AGENT.unknown)
        assert result_trade == exchange_trade
        assert result_trade.convert_id == ''
        xchange_trader_create_and_commit_wallet_transactions_mock.assert_not_called()
        exchange_trade_objects_create_mock.assert_called_once_with(
            is_sell=False,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=decimal.Decimal('0.022'),
            dst_amount=decimal.Decimal('100.22'),
            quote_id='this_is_a_quote_id',
            client_order_id='some_client_order_id',
            user_id=10,
            user_agent=ExchangeTrade.USER_AGENT.unknown,
        )
        schedule_get_conversion_task_mock.assert_called_once_with(exchange_trade.pk)

    @_patch
    def test_unsuccessful_user_transfer(
        self,
        estimator_invalidate_quote_mock: mock.MagicMock,
        xchange_trader_create_and_commit_wallet_transactions_mock: mock.MagicMock,
        exchange_trade_objects_create_mock: mock.MagicMock,
        convertor_call_conversion_api_mock: mock.MagicMock,
        report_event_mock: mock.MagicMock,
        estimator_get_quote_mock: mock.MagicMock,
        schedule_get_conversion_task_mock: mock.MagicMock,
    ):
        estimator_get_quote_mock.return_value = self.quote
        convertor_call_conversion_api_mock.return_value = self.conversion
        exchange_trade_objects_create_mock.return_value = self.exchange_trade
        xchange_trader_create_and_commit_wallet_transactions_mock.side_effect = exceptions.FailedAssetTransfer('failed')
        with pytest.raises(exceptions.FailedAssetTransfer):
            XchangeTrader.create_trade(self.user_id, self.quote_id, ExchangeTrade.USER_AGENT.unknown)
        assert self.exchange_trade.convert_id == self.conversion.convert_id
        schedule_get_conversion_task_mock.assert_not_called()

    @_patch
    def test_unsuccessful_system_transfer(
        self,
        estimator_invalidate_quote_mock: mock.MagicMock,
        xchange_trader_create_and_commit_wallet_transactions_mock: mock.MagicMock,
        exchange_trade_objects_create_mock: mock.MagicMock,
        convertor_call_conversion_api_mock: mock.MagicMock,
        report_event_mock: mock.MagicMock,
        estimator_get_quote_mock: mock.MagicMock,
        schedule_get_conversion_task_mock: mock.MagicMock,
    ):
        estimator_get_quote_mock.return_value = self.quote
        convertor_call_conversion_api_mock.return_value = self.conversion
        exchange_trade_objects_create_mock.return_value = self.exchange_trade
        xchange_trader_create_and_commit_wallet_transactions_mock.side_effect = exceptions.PairIsClosed('failed')
        with pytest.raises(exceptions.PairIsClosed):
            XchangeTrader.create_trade(self.user_id, self.quote_id, ExchangeTrade.USER_AGENT.unknown)
        assert self.exchange_trade.convert_id == self.conversion.convert_id
        schedule_get_conversion_task_mock.assert_not_called()

def _patch_create_and_commit_wallet_transactions(test):
    patch_prefix = 'exchange.xchange.trader'

    @functools.wraps(test)
    @mock.patch(patch_prefix + '.get_market_maker_system_user', lambda: User(id=14124124))
    @mock.patch(patch_prefix + '.create_and_commit_system_user_transaction')
    @mock.patch(patch_prefix + '.create_and_commit_transaction')
    @mock.patch(patch_prefix + '.ExchangeTrade.save')
    def decorated(*args, **kwargs):
        return test(*args, **kwargs)

    return decorated


class CreateAndCommitWalletTransactionsTest(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.exchange_trade = ExchangeTrade(
            id=123275923587,
            user_id=602039680236,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=decimal.Decimal('0.22'),
            dst_amount=decimal.Decimal('455454.2542'),
            quote_id='this_is_a_quote_id',
            client_order_id='some_client_order_id',
        )

    @_patch_create_and_commit_wallet_transactions
    def test_a_successful_call(
        self,
        exchange_trade_save_mock: mock.MagicMock,
        create_and_commit_transaction_mock: mock.MagicMock,
        create_and_commit_system_user_transaction: mock.MagicMock,
    ):
        transactions = [Transaction(balance=1) for _ in range(4)]
        create_and_commit_transaction_mock.side_effect = transactions[:2]
        create_and_commit_system_user_transaction.side_effect = transactions[2:]
        XchangeTrader.create_and_commit_wallet_transactions(self.exchange_trade)
        create_and_commit_transaction_mock.assert_has_calls(
            any_order=False,
            calls=[
                mock.call(
                    user_id=602039680236,
                    currency=10,
                    amount=decimal.Decimal('-0.22'),
                    ref_module=RefMod.convert_user_src,
                    ref_id=123275923587,
                    description='تبدیل بیت\u200cکوین به تتر',
                    allow_negative_balance=False,
                ),
                mock.call(
                    user_id=602039680236,
                    currency=13,
                    amount=decimal.Decimal('455454.2542'),
                    ref_module=RefMod.convert_user_dst,
                    ref_id=123275923587,
                    description='تبدیل بیت\u200cکوین به تتر',
                    allow_negative_balance=False,
                ),
            ],
        )
        create_and_commit_system_user_transaction.assert_has_calls(
            any_order=False,
            calls=[
                mock.call(
                    user_id=14124124,
                    currency=10,
                    amount=decimal.Decimal('0.22'),
                    ref_module=RefMod.convert_system_src,
                    ref_id=123275923587,
                    description='تبدیل بیت\u200cکوین به تتر',
                ),
                mock.call(
                    user_id=14124124,
                    currency=13,
                    amount=decimal.Decimal('-455454.2542'),
                    ref_module=RefMod.convert_system_dst,
                    ref_id=123275923587,
                    description='تبدیل بیت\u200cکوین به تتر',
                ),
            ],
        )
        exchange_trade_save_mock.assert_called_once_with()
        assert self.exchange_trade.src_transaction == transactions[0]
        assert self.exchange_trade.dst_transaction == transactions[1]
        assert self.exchange_trade.system_src_transaction == transactions[2]
        assert self.exchange_trade.system_dst_transaction == transactions[3]

    @_patch_create_and_commit_wallet_transactions
    def test_a_failed_user_transfer(
        self,
        exchange_trade_save_mock: mock.MagicMock,
        create_and_commit_transaction_mock: mock.MagicMock,
        create_and_commit_system_user_transaction: mock.MagicMock,
    ):
        create_and_commit_transaction_mock.side_effect = [Transaction(),  ValueError]
        with pytest.raises(exceptions.FailedAssetTransfer):
            XchangeTrader.create_and_commit_wallet_transactions(self.exchange_trade)
        exchange_trade_save_mock.assert_not_called()

    @_patch_create_and_commit_wallet_transactions
    def test_a_failed_system_transfer(
        self,
        exchange_trade_save_mock: mock.MagicMock,
        create_and_commit_transaction_mock: mock.MagicMock,
        create_and_commit_system_user_transaction: mock.MagicMock,
    ):
        create_and_commit_transaction_mock.side_effect = [Transaction(), Transaction(), ValueError]
        with pytest.raises(exceptions.PairIsClosed):
            XchangeTrader.create_and_commit_wallet_transactions(self.exchange_trade)
        exchange_trade_save_mock.assert_not_called()

    @_patch_create_and_commit_wallet_transactions
    def test_negative_system_balance(
        self,
        exchange_trade_save_mock: mock.MagicMock,
        create_and_commit_transaction_mock: mock.MagicMock,
        create_and_commit_system_user_transaction: mock.MagicMock,
    ):
        create_and_commit_transaction_mock.side_effect = [Transaction(), Transaction()]
        create_and_commit_system_user_transaction.side_effect = [Transaction(balance=decimal.Decimal(-1)), Transaction(balance=22)]
        XchangeTrader.create_and_commit_wallet_transactions(self.exchange_trade)
        exchange_trade_save_mock.assert_called_once_with()
