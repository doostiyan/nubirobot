import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase
from django.utils.timezone import now
from freezegun import freeze_time

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import RIAL, TETHER, Currencies, Settings
from exchange.liquidator.models import LiquidationRequest
from exchange.market.conversion_trade_fees import TradeFeeConversion
from exchange.market.crons import SystemFeeWalletChargeCron
from exchange.market.models import OrderMatching
from exchange.wallet.models import Wallet
from tests.base.utils import create_trade

NOW = now().replace(hour=1)
DATETIME = ir_now().replace(hour=1)
PRICE = Decimal('1000000')
AMOUNT = Decimal('1')
FEE_RATE = Decimal('0.1')


@freeze_time(DATETIME)
class ConvertFeeCronTest(TestCase):
    def setUp(self):
        self.user1, _ = User.objects.get_or_create(pk=1001)
        self.user2 = User.objects.get(pk=201)

        self.system_fee = User.objects.get(pk=999)
        self.system_fee_tether_wallet = Wallet.get_user_wallet(self.system_fee, TETHER)
        cache.set(f'mark_price_{Currencies.btc}', Decimal('1000'))

    def tearDown(self):
        super().tearDown()
        cache.clear()

    def _create_trade(self, src_currency: int, dst_currency: int = RIAL, created_at=NOW):
        create_trade(
            buyer=self.user1,
            seller=self.user2,
            price=PRICE,
            amount=AMOUNT,
            src_currency=src_currency,
            dst_currency=dst_currency,
            fee_rate=FEE_RATE,
            created_at=created_at,
        )
        trade = OrderMatching.objects.last()
        assert trade
        assert trade.buy_fee_amount > 0

    def _collect_fee(self, src_currency: int, dst_currency: int = RIAL, now_time=DATETIME - datetime.timedelta(days=1)):
        self._create_trade(src_currency, dst_currency, created_at=now_time - datetime.timedelta(hours=1))
        with patch('django.utils.timezone.now', return_value=now_time):
            SystemFeeWalletChargeCron().run()

    def _set_active_liquidation_request_market(self, market_list: str):
        Settings.set(LiquidationRequest.CACHE_KEY, market_list)

    def test_settings_rate_keys_does_not_exist(self):
        self._collect_fee(src_currency=Currencies.btc, dst_currency=RIAL)
        self._set_active_liquidation_request_market(['all'])
        assert LiquidationRequest.objects.count() == 0
        TradeFeeConversion.run()
        assert LiquidationRequest.objects.count() == 0

    @patch('exchange.market.conversion_trade_fees.report_event')
    def test_invalid_start_time_settings_key(self, mock_report_event: MagicMock):
        Settings.set_cached_json(TradeFeeConversion.CONVERSION_CURRENCIES_STARTTIME_KEY, [])
        self._collect_fee(src_currency=Currencies.btc, dst_currency=RIAL)
        Settings.set_cached_json(
            TradeFeeConversion.CONVERSION_CURRENCIES_RATE_KEY,
            {'btc': '0.1'},
        )
        TradeFeeConversion.run()
        mock_report_event.assert_called_once()

    @patch('exchange.market.conversion_trade_fees.report_event')
    def test_settings_currency_name_error(self, mock_report_event: MagicMock):
        self._collect_fee(src_currency=Currencies.btc, dst_currency=RIAL)
        Settings.set_cached_json(
            TradeFeeConversion.CONVERSION_CURRENCIES_RATE_KEY,
            {'random_coin_does_not_exist': '0.1'},
        )
        self._set_active_liquidation_request_market('["all"]')
        TradeFeeConversion.run()
        assert LiquidationRequest.objects.count() == 0
        mock_report_event.assert_called_once()

    @patch('exchange.market.conversion_trade_fees.report_event')
    def test_invalid_market_settings_key(self, mock_report_event: MagicMock):
        Settings.set_cached_json(TradeFeeConversion.CONVERSION_CURRENCIES_RATE_KEY, [])
        TradeFeeConversion.run()
        assert LiquidationRequest.objects.count() == 0
        mock_report_event.assert_called_once()

    def test_settings_liquidation_request_key_does_not_exist(self):
        self._create_trade(Currencies.btc, RIAL)
        Settings.set_cached_json(
            TradeFeeConversion.CONVERSION_CURRENCIES_RATE_KEY,
            {'btc': '0.1'},
        )
        self._set_active_liquidation_request_market([])
        assert LiquidationRequest.objects.count() == 0
        TradeFeeConversion.run()
        assert LiquidationRequest.objects.count() == 0

    def test_inactive_value(self):
        Settings.set_cached_json(
            TradeFeeConversion.CONVERSION_CURRENCIES_RATE_KEY,
            {},
        )
        self._set_active_liquidation_request_market('["BTCUSDT"]')
        self._collect_fee(src_currency=Currencies.btc, dst_currency=RIAL)

        fee_start_times = Settings.get_dict(TradeFeeConversion.CONVERSION_CURRENCIES_STARTTIME_KEY)
        assert not fee_start_times

        assert LiquidationRequest.objects.count() == 0
        TradeFeeConversion.run()
        assert LiquidationRequest.objects.count() == 0
        fee_start_times = Settings.get_dict(TradeFeeConversion.CONVERSION_CURRENCIES_STARTTIME_KEY)
        assert not fee_start_times

        Settings.set_cached_json(
            TradeFeeConversion.CONVERSION_CURRENCIES_RATE_KEY,
            {'btc': '0.0'},
        )
        TradeFeeConversion.run()
        assert LiquidationRequest.objects.count() == 0
        fee_start_times = Settings.get_dict(TradeFeeConversion.CONVERSION_CURRENCIES_STARTTIME_KEY)
        currency_id = str(Currencies.btc)
        assert fee_start_times
        assert currency_id in fee_start_times
        assert fee_start_times[currency_id] == DATETIME.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    @patch('exchange.market.conversion_trade_fees.report_event')
    def test_balance_less_than_conversion_amount(self, mock_report_event: MagicMock):
        cache.set(f'mark_price_{Currencies.btc}', Decimal('10000'))
        rate = Decimal('0.1')
        Settings.set_cached_json(
            TradeFeeConversion.CONVERSION_CURRENCIES_RATE_KEY,
            {'btc': '0.1'},
        )
        self._set_active_liquidation_request_market('["BTCUSDT"]')

        self._collect_fee(src_currency=Currencies.btc, dst_currency=RIAL)

        btc_wallet_system_fee = Wallet.get_fee_collector_wallet(Currencies.btc)

        amount = -btc_wallet_system_fee.balance + (AMOUNT * FEE_RATE * rate) / 2
        Wallet.create_transaction(btc_wallet_system_fee, 'manual', amount).commit()
        btc_wallet_system_fee.refresh_from_db()
        assert btc_wallet_system_fee.balance == (AMOUNT * FEE_RATE * rate) / 2

        assert LiquidationRequest.objects.count() == 0
        TradeFeeConversion.run()
        assert LiquidationRequest.objects.count() == 1
        mock_report_event.assert_called_once()

        liquidation_request = LiquidationRequest.objects.last()
        assert liquidation_request.user == self.system_fee
        assert liquidation_request.amount == (AMOUNT * FEE_RATE * rate) / 2
        assert liquidation_request.is_sell
        assert liquidation_request.service == LiquidationRequest.SERVICE_TYPES.fee_collector

    def test_rerun_task(self):
        Settings.set_cached_json(
            TradeFeeConversion.CONVERSION_CURRENCIES_RATE_KEY,
            {'btc': '0.1'},
        )
        self._set_active_liquidation_request_market('["BTCUSDT"]')

        self._collect_fee(src_currency=Currencies.btc, dst_currency=RIAL)

        assert LiquidationRequest.objects.count() == 0
        TradeFeeConversion.run()
        assert LiquidationRequest.objects.count() == 1

        # if rerun task, check liquidation request
        TradeFeeConversion.run()
        assert LiquidationRequest.objects.count() == 1

    def test_create_liquidation_request(self):
        rate = Decimal('0.1')
        Settings.set_cached_json(
            TradeFeeConversion.CONVERSION_CURRENCIES_RATE_KEY,
            {'btc': '0.1'},
        )
        self._set_active_liquidation_request_market('["BTCUSDT"]')

        self._collect_fee(
            src_currency=Currencies.btc,
            dst_currency=RIAL,
            now_time=DATETIME - datetime.timedelta(days=2),
        )
        self._collect_fee(src_currency=Currencies.btc, dst_currency=RIAL)

        assert LiquidationRequest.objects.count() == 0
        TradeFeeConversion.run()
        assert LiquidationRequest.objects.count() == 1
        liquidation_request = LiquidationRequest.objects.last()
        assert liquidation_request.user == self.system_fee
        assert liquidation_request.amount == AMOUNT * FEE_RATE * rate
        assert liquidation_request.is_sell
        assert liquidation_request.service == LiquidationRequest.SERVICE_TYPES.fee_collector

    def test_under_ten_usdt_value(self):
        cache.set(f'mark_price_{Currencies.btc}', Decimal('1'))
        Settings.set_cached_json(
            TradeFeeConversion.CONVERSION_CURRENCIES_RATE_KEY,
            {'btc': '0.1'},
        )
        self._set_active_liquidation_request_market('["BTCUSDT"]')

        self._collect_fee(src_currency=Currencies.btc, dst_currency=RIAL)

        assert LiquidationRequest.objects.count() == 0
        TradeFeeConversion.run()
        assert LiquidationRequest.objects.count() == 0

        fee_start_times = Settings.get_dict(TradeFeeConversion.CONVERSION_CURRENCIES_STARTTIME_KEY)
        currency_id = str(Currencies.btc)
        assert fee_start_times
        assert currency_id in fee_start_times
        assert (
            fee_start_times[currency_id]
            == (DATETIME - datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        )

    def test_exist_start_time(self):
        rate = Decimal('0.1')
        fee_start_times = Settings.get_dict(TradeFeeConversion.CONVERSION_CURRENCIES_STARTTIME_KEY)
        currency_id = str(Currencies.btc)
        assert not fee_start_times
        fee_start_times[currency_id] = (
            (DATETIME - datetime.timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        )
        Settings.set_dict(TradeFeeConversion.CONVERSION_CURRENCIES_STARTTIME_KEY, fee_start_times)

        Settings.set_cached_json(
            TradeFeeConversion.CONVERSION_CURRENCIES_RATE_KEY,
            {'btc': '0.1'},
        )
        self._set_active_liquidation_request_market('["BTCUSDT"]')

        self._collect_fee(
            src_currency=Currencies.btc,
            dst_currency=RIAL,
            now_time=DATETIME - datetime.timedelta(days=2),
        )
        self._collect_fee(src_currency=Currencies.btc, dst_currency=RIAL)

        assert LiquidationRequest.objects.count() == 0
        TradeFeeConversion.run()
        assert LiquidationRequest.objects.count() == 1
        liquidation_request = LiquidationRequest.objects.last()
        assert liquidation_request.user == self.system_fee
        assert liquidation_request.amount == AMOUNT * 2 * FEE_RATE * rate
        assert liquidation_request.is_sell
        assert liquidation_request.service == LiquidationRequest.SERVICE_TYPES.fee_collector
