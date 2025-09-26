import decimal
from datetime import timedelta

import responses
from django.test import TestCase, override_settings

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.wallet.models import Wallet
from exchange.xchange.helpers import get_exchange_trade_kwargs_from_quote
from exchange.xchange.marketmaker.client import Client
from exchange.xchange.marketmaker.quotes import Estimator, Quote
from exchange.xchange.models import ExchangeTrade, SmallAssetConvert
from exchange.xchange.tasks import get_missed_conversion_status_task, update_small_asset_convert_status


class GetMissedConversionStatusTask(TestCase):
    def setUp(self):
        self.quote_id = 'dc2566913fdb4148a1357141b11ea195'
        self.user = User.objects.get(pk=201)
        self.xchange_user = User.objects.get(username='system-convert')
        self.quote = Quote(
            quote_id=self.quote_id,
            base_currency=Currencies.btc,
            quote_currency=Currencies.usdt,
            reference_currency=Currencies.usdt,
            reference_amount=decimal.Decimal('12.22'),
            destination_amount=decimal.Decimal('12.22'),
            is_sell=True,
            client_order_id='cliOid',
            expires_at=ir_now() + timedelta(days=1),
            user_id=self.user.id,
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        wallet.balance = 13
        wallet.save()
        wallet = Wallet.get_user_wallet(self.xchange_user, Currencies.usdt)
        wallet.balance = 1000
        wallet.save()
        Estimator.set_quote(self.quote, self.user.id)
        self.exchange_trade = ExchangeTrade.objects.create(**{
            **get_exchange_trade_kwargs_from_quote(self.quote),
            'user_id': self.user.id,
            },
        )
        return super().setUp()

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_success(self):
        responses.get(
            url=Client.get_base_url()[1] + '/xconvert/convert',
            json={
                'result': {
                    'convertId': '1',
                    'destinationCurrencyAmount': str(self.quote.destination_amount),
                    'quoteId': self.quote_id,
                    'clientId': self.quote.client_order_id,
                    'baseCurrency': self.quote.base_currency_code_name,
                    'quoteCurrency': self.quote.quote_currency_code_name,
                    'status': 'Filled',
                    'side': 'sell',
                    'referenceCurrency': self.quote.reference_currency_code_name,
                    'referenceCurrencyAmount': str(self.quote.reference_amount),
                },
                'message': 'successful message',
                'error': 'success',
                'hasError': False,
            },
            status=200,
        )
        assert self.exchange_trade.status == ExchangeTrade.STATUS.unknown
        assert self.exchange_trade.convert_id is None
        get_missed_conversion_status_task(self.exchange_trade.id)
        self.exchange_trade.refresh_from_db()
        assert self.exchange_trade.status == ExchangeTrade.STATUS.succeeded
        assert self.exchange_trade.convert_id == '1'


class TestUpdateSmallAssetConvertStatusTask(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            username='xchange_small_asset_convert_signal',
            user_type=User.USER_TYPE_LEVEL1,
        )

        self.unknown_trade = ExchangeTrade.objects.create(
            user=self.user,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            src_amount=decimal.Decimal('0.1'),
            dst_amount=decimal.Decimal('1000000'),
            status=ExchangeTrade.STATUS.unknown,
            quote_id='test_quote',
            client_order_id='test_order',
        )

        self.failed_trade = ExchangeTrade.objects.create(
            user=self.user,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            src_amount=decimal.Decimal('0.1'),
            dst_amount=decimal.Decimal('1000000'),
            status=ExchangeTrade.STATUS.failed,
            quote_id='test_quote',
            client_order_id='test_order',
        )

        self.succeeded_trade = ExchangeTrade.objects.create(
            user=self.user,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            src_amount=decimal.Decimal('0.1'),
            dst_amount=decimal.Decimal('1000000'),
            status=ExchangeTrade.STATUS.succeeded,
            quote_id='test_quote',
            client_order_id='test_order',
        )

    def test_update_to_succeeded(self):
        """Should update in_progress records to succeeded when trade succeeded"""
        convert = SmallAssetConvert.objects.create(
            user=self.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            src_amount=decimal.Decimal('0.01'),
            dst_amount=decimal.Decimal('10000'),
            status=SmallAssetConvert.STATUS.in_progress,
            related_batch_trade=self.succeeded_trade,
        )

        update_small_asset_convert_status()

        convert.refresh_from_db()
        assert convert.status == SmallAssetConvert.STATUS.succeeded

    def test_update_to_failed(self):
        """Should update in_progress records to failed when trade failed"""
        convert = SmallAssetConvert.objects.create(
            user=self.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            src_amount=decimal.Decimal('0.01'),
            dst_amount=decimal.Decimal('10000'),
            status=SmallAssetConvert.STATUS.in_progress,
            related_batch_trade=self.failed_trade,
        )

        update_small_asset_convert_status()

        convert.refresh_from_db()
        assert convert.status == SmallAssetConvert.STATUS.failed

    def test_multiple_records_update(self):
        """Should update multiple records correctly"""
        converts_succeeded = [
            SmallAssetConvert.objects.create(
                user=self.user,
                src_currency=Currencies.btc,
                dst_currency=Currencies.rls,
                src_amount=decimal.Decimal('0.01'),
                dst_amount=decimal.Decimal('10000'),
                status=SmallAssetConvert.STATUS.in_progress,
                related_batch_trade=self.succeeded_trade,
            )
            for _ in range(3)
        ]

        converts_failed = [
            SmallAssetConvert.objects.create(
                user=self.user,
                src_currency=Currencies.btc,
                dst_currency=Currencies.rls,
                src_amount=decimal.Decimal('0.01'),
                dst_amount=decimal.Decimal('10000'),
                status=SmallAssetConvert.STATUS.in_progress,
                related_batch_trade=self.failed_trade,
            )
            for _ in range(3)
        ]

        update_small_asset_convert_status()

        for convert in converts_succeeded:
            convert.refresh_from_db()
            assert convert.status == SmallAssetConvert.STATUS.succeeded

        for convert in converts_failed:
            convert.refresh_from_db()
            assert convert.status == SmallAssetConvert.STATUS.failed

    def test_no_update_non_in_progress(self):
        """Should not update records that are not in_progress"""
        convert = SmallAssetConvert.objects.create(
            user=self.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            src_amount=decimal.Decimal('0.01'),
            dst_amount=decimal.Decimal('10000'),
            status=SmallAssetConvert.STATUS.created,
            related_batch_trade=self.succeeded_trade,
        )

        update_small_asset_convert_status()

        convert.refresh_from_db()
        assert convert.status == SmallAssetConvert.STATUS.created

    def test_no_update_without_related_trade(self):
        """Should not update records without related batch trade"""
        convert = SmallAssetConvert.objects.create(
            user=self.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            src_amount=decimal.Decimal('0.01'),
            dst_amount=decimal.Decimal('10000'),
            status=SmallAssetConvert.STATUS.in_progress,
            related_batch_trade=self.unknown_trade,
        )

        update_small_asset_convert_status()

        convert.refresh_from_db()
        assert convert.status == SmallAssetConvert.STATUS.in_progress
