from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import responses
from django.test import TestCase, override_settings

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import RIAL, Currencies
from exchange.wallet.models import Wallet
from exchange.xchange.helpers import get_small_assets_convert_system_user
from exchange.xchange.marketmaker.client import Client
from exchange.xchange.models import ExchangeTrade, MarketLimitation, MarketStatus, SmallAssetConvert
from exchange.xchange.small_asset_batch_convertor import SmallAssetBatchConvertor


@patch('exchange.xchange.small_asset_batch_convertor.update_small_asset_convert_status.apply_async', MagicMock())
@patch(
    'exchange.xchange.small_asset_batch_convertor.SMALL_ASSET_BATCH_CONVERT_MAX_AMOUNT_THRESHOLD_RATIO',
    Decimal('1'),
)
class TestSmallAssetBatchConvertorFunctional(TestCase):
    def setUp(self):
        self.xchange_currency = Currencies.ygg
        self.dst_currency = RIAL

        self.system_user = get_small_assets_convert_system_user()
        self.system_user_xchange_wallet = Wallet.get_user_wallet(self.system_user, self.xchange_currency)
        self.system_user_xchange_wallet.balance = Decimal('27')
        self.system_user_xchange_wallet.save()

        self.quote_result = {
            'result': {
                'quoteId': 'yggrls-sell-a7db70bd22424eb68ce2dc0e688ffeb5',
                'baseCurrency': 'ygg',
                'quoteCurrency': 'rls',
                'clientId': '3cfbc941-c4e3-4fa8-a6e0-8d08e8f62efc',
                'creationTime': int(ir_now().timestamp()) * 1000,  # Milliseconds
                'validationTTL': 60000,  # Milliseconds
                'side': 'sell',
                'referenceCurrency': 'ygg',
                'referenceCurrencyOriginalAmount': 18,
                'referenceCurrencyRealAmount': 18,
                'destinationCurrencyAmount': 10,
            },
            'message': 'Estimate quote created successfully',
            'error': None,
            'hasError': False,
        }

        self.market_status = MarketStatus.objects.create(
            base_currency=self.xchange_currency,
            quote_currency=self.dst_currency,
            base_to_quote_price_buy=2.2,
            quote_to_base_price_buy=3.2,
            base_to_quote_price_sell=1.2,
            quote_to_base_price_sell=1.2,
            min_base_amount=10,
            max_base_amount=20,
            min_quote_amount=5,
            max_quote_amount=500,
            base_precision=Decimal('1e-4'),
            quote_precision=Decimal('1e-1'),
            status=MarketStatus.STATUS_CHOICES.available,
        )

        user = User.objects.create(
            username='xchange_small_asset_convertor_test',
            user_type=User.USER_TYPE_LEVEL1,
        )

        self.small_asset_convert1 = SmallAssetConvert.objects.create(
            user=user,
            src_currency=self.xchange_currency,
            dst_currency=self.dst_currency,
            src_amount=9,
            dst_amount=10,
            status=SmallAssetConvert.STATUS.created,
            created_at=ir_now(),
        )

        self.small_asset_convert2 = SmallAssetConvert.objects.create(
            user=user,
            src_currency=self.xchange_currency,
            dst_currency=self.dst_currency,
            src_amount=9,
            dst_amount=10,
            status=SmallAssetConvert.STATUS.created,
            created_at=self.small_asset_convert1.created_at + timedelta(minutes=30),
        )

        self.small_asset_convert3 = SmallAssetConvert.objects.create(
            user=user,
            src_currency=self.xchange_currency,
            dst_currency=self.dst_currency,
            src_amount=9,
            dst_amount=10,
            status=SmallAssetConvert.STATUS.created,
            created_at=self.small_asset_convert2.created_at + timedelta(minutes=30),
        )

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_batch_convert_successfully_with_available_both_side_market(self):
        self.market_status.status = MarketStatus.STATUS_CHOICES.available
        self.market_status.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.both_side
        self.market_status.save()

        self._mock_market_maker_response()

        SmallAssetBatchConvertor.batch_convert()

        self._assert_convert_success()

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_batch_convert_not_run_with_available_buy_only_market(self):
        self.market_status.status = MarketStatus.STATUS_CHOICES.available
        self.market_status.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.buy_only
        self.market_status.save()

        self._mock_market_maker_response()

        SmallAssetBatchConvertor.batch_convert()

        self._assert_not_convert()

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_batch_convert_successfully_with_available_sell_only_market(self):
        self.market_status.status = MarketStatus.STATUS_CHOICES.available
        self.market_status.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.sell_only
        self.market_status.save()

        self._mock_market_maker_response()

        SmallAssetBatchConvertor.batch_convert()

        self._assert_convert_success()

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_batch_convert_not_run_with_available_closed_market(self):
        self.market_status.status = MarketStatus.STATUS_CHOICES.available
        self.market_status.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.closed
        self.market_status.save()

        self._mock_market_maker_response()

        SmallAssetBatchConvertor.batch_convert()

        self._assert_not_convert()

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_batch_convert_not_run_with_unavailable_both_side_market(self):
        self.market_status.status = MarketStatus.STATUS_CHOICES.unavailable
        self.market_status.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.both_side
        self.market_status.save()

        self._mock_market_maker_response()

        SmallAssetBatchConvertor.batch_convert()

        self._assert_not_convert()

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_batch_convert_not_run_with_delisted_both_side_market(self):
        self.market_status.status = MarketStatus.STATUS_CHOICES.delisted
        self.market_status.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.both_side
        self.market_status.save()

        self._mock_market_maker_response()

        SmallAssetBatchConvertor.batch_convert()

        self._assert_not_convert()

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_batch_convert_not_run_with_expired_both_side_market(self):
        self.market_status.status = MarketStatus.STATUS_CHOICES.available
        self.market_status.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.both_side
        self.market_status.updated_at = (
            ir_now() - timedelta(minutes=MarketStatus.EXPIRATION_TIME_IN_MINUTES) - timedelta(minutes=1)
        )  # Simulate an expired market

        MarketStatus.objects.bulk_update(
            (self.market_status,),
            ['updated_at', 'status', 'exchange_side'],
        )  # Bulk save to ignore overridden save

        self._mock_market_maker_response()

        SmallAssetBatchConvertor.batch_convert()

        self._assert_not_convert()

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_batch_convert_successfully_with_market_sell_limitation(self):
        self.market_status.status = MarketStatus.STATUS_CHOICES.available
        self.market_status.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.both_side
        self.market_status.save()

        MarketLimitation.objects.create(
            interval=1,
            max_amount=Decimal('5.0'),
            market=self.market_status,
            is_active=True,
            is_sell=True,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )

        self._mock_market_maker_response()

        SmallAssetBatchConvertor.batch_convert()

        self._assert_convert_success()

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_batch_convert_successfully_with_market_buy_limitation(self):
        self.market_status.status = MarketStatus.STATUS_CHOICES.available
        self.market_status.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.both_side
        self.market_status.save()

        MarketLimitation.objects.create(
            interval=1,
            max_amount=Decimal('5.0'),
            market=self.market_status,
            is_active=True,
            is_sell=False,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )

        self._mock_market_maker_response()

        SmallAssetBatchConvertor.batch_convert()

        self._assert_convert_success()

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_batch_convert_successfully_with_user_sell_limitation(self):
        self.market_status.status = MarketStatus.STATUS_CHOICES.available
        self.market_status.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.both_side
        self.market_status.save()

        MarketLimitation.objects.create(
            interval=1,
            max_amount=Decimal('5.0'),
            market=self.market_status,
            is_active=True,
            is_sell=True,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.USER,
        )

        self._mock_market_maker_response()

        SmallAssetBatchConvertor.batch_convert()

        self._assert_convert_success()

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_batch_convert_successfully_with_user_buy_limitation(self):
        self.market_status.status = MarketStatus.STATUS_CHOICES.available
        self.market_status.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.both_side
        self.market_status.save()

        MarketLimitation.objects.create(
            interval=1,
            max_amount=Decimal('5.0'),
            market=self.market_status,
            is_active=True,
            is_sell=False,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.USER,
        )

        self._mock_market_maker_response()

        SmallAssetBatchConvertor.batch_convert()

        self._assert_convert_success()

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_batch_convert_successfully_with_negative_dst_wallet(self):
        self.market_status.status = MarketStatus.STATUS_CHOICES.available
        self.market_status.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.both_side
        self.market_status.save()

        system_user_dst_wallet = Wallet.get_user_wallet(self.system_user, self.dst_currency)
        system_user_dst_wallet.balance = Decimal('-1000')
        system_user_dst_wallet.save()

        self._mock_market_maker_response()

        SmallAssetBatchConvertor.batch_convert()

        self._assert_convert_success()

    def _mock_market_maker_response(self):
        responses.post(
            url=Client.get_base_url()[1] + '/xconvert/estimate',
            json=self.quote_result,
            status=200,
        )

        responses.post(
            url=Client.get_base_url()[1] + '/xconvert/convert',
            json={
                'result': {
                    'convertId': 1,
                    'destinationCurrencyAmount': str(self.quote_result['result']['destinationCurrencyAmount']),
                    'quoteId': self.quote_result['result']['quoteId'],
                    'clientId': self.quote_result['result']['clientId'],
                    'baseCurrency': self.quote_result['result']['baseCurrency'],
                    'quoteCurrency': self.quote_result['result']['quoteCurrency'],
                    'status': 'Filled',
                    'side': 'sell',
                    'referenceCurrency': self.quote_result['result']['referenceCurrency'],
                    'referenceCurrencyAmount': str(self.quote_result['result']['referenceCurrencyRealAmount']),
                },
                'message': 'successful message',
                'error': 'success',
                'hasError': False,
            },
            status=200,
        )

    def _assert_convert_success(self):
        trade = ExchangeTrade.objects.filter(quote_id=self.quote_result['result']['quoteId']).first()
        assert trade is not None
        assert trade.user == get_small_assets_convert_system_user()
        assert trade.user_agent == ExchangeTrade.USER_AGENT.system

        self.small_asset_convert1.refresh_from_db()
        self.small_asset_convert2.refresh_from_db()
        self.small_asset_convert3.refresh_from_db()

        assert self.small_asset_convert1.status == SmallAssetConvert.STATUS.in_progress
        assert self.small_asset_convert1.related_batch_trade_id == trade.id

        assert self.small_asset_convert2.status == SmallAssetConvert.STATUS.in_progress
        assert self.small_asset_convert2.related_batch_trade_id == trade.id

        assert self.small_asset_convert3.status == SmallAssetConvert.STATUS.created
        assert self.small_asset_convert3.related_batch_trade is None

        self.system_user_xchange_wallet.refresh_from_db()
        assert self.system_user_xchange_wallet.balance == Decimal('9')

    def _assert_not_convert(self):
        trade = ExchangeTrade.objects.filter(quote_id=self.quote_result['result']['quoteId']).first()
        assert trade is None

        self.small_asset_convert1.refresh_from_db()
        self.small_asset_convert2.refresh_from_db()
        self.small_asset_convert3.refresh_from_db()

        assert self.small_asset_convert1.status == SmallAssetConvert.STATUS.created
        assert self.small_asset_convert1.related_batch_trade is None

        assert self.small_asset_convert2.status == SmallAssetConvert.STATUS.created
        assert self.small_asset_convert2.related_batch_trade is None

        assert self.small_asset_convert3.status == SmallAssetConvert.STATUS.created
        assert self.small_asset_convert3.related_batch_trade is None

        self.system_user_xchange_wallet.refresh_from_db()
        assert self.system_user_xchange_wallet.balance == Decimal('27')
