import datetime
from decimal import Decimal

from django.test import TestCase, TransactionTestCase
from django.utils.timezone import now
from freezegun import freeze_time
from pytz import timezone

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.market.crons import SystemFeeWalletChargeCron
from exchange.market.models import FeeTransactionTradeList, Market
from exchange.wallet.models import Wallet

from ..base.utils import TransactionTestFastFlushMixin, create_trade


class SystemFeeWalletChargeCronTest(TransactionTestFastFlushMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.user1 = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)

        # Get markets
        self.btc_irt_market = Market.by_symbol('BTCIRT')
        self.btc_usdt_market = Market.by_symbol('BTCUSDT')
        self.usdt_irt_market = Market.by_symbol('USDTIRT')

        # Create wallets for users
        self.user1_btc_wallet = Wallet.get_user_wallet(self.user1, Currencies.btc)
        self.user1_irt_wallet = Wallet.get_user_wallet(self.user1, Currencies.rls)
        self.user1_usdt_wallet = Wallet.get_user_wallet(self.user1, Currencies.usdt)

        self.user2_btc_wallet = Wallet.get_user_wallet(self.user2, Currencies.btc)
        self.user2_irt_wallet = Wallet.get_user_wallet(self.user2, Currencies.rls)
        self.user2_usdt_wallet = Wallet.get_user_wallet(self.user2, Currencies.usdt)

        # Freeze time at 04:35 Tehran time
        tehran_tz = timezone('Asia/Tehran')
        self.frozen_time = datetime.datetime(2025, 1, 1, 4, 35, tzinfo=tehran_tz)
        self.freezer = freeze_time(self.frozen_time)
        self.freezer.start()

        self.cron = SystemFeeWalletChargeCron()
        # Set time window for the previous hour in Tehran time using ir_now()
        nw = ir_now()
        self.cron.to_datetime = nw.replace(minute=0, second=0, microsecond=0)
        self.cron.from_datetime = self.cron.to_datetime - datetime.timedelta(hours=1)

    def tearDown(self):
        self.freezer.stop()
        # Clean up any FeeTransactionTradeList objects created during the test
        FeeTransactionTradeList.objects.all().delete()
        super().tearDown()

    def test_cron_creates_fee_transaction_trades_for_irt_market(self):
        # Create trades in BTCIRT market with fees during the previous hour
        trade1 = create_trade(
            self.user1,
            self.user2,
            self.btc_irt_market.src_currency,
            self.btc_irt_market.dst_currency,
            Decimal('0.1'),
            Decimal('1000000000'),
            created_at=self.cron.from_datetime + datetime.timedelta(minutes=15),
        )
        trade1.sell_fee_amount = Decimal('100000')
        trade1.save()

        trade2 = create_trade(
            self.user2,
            self.user1,
            self.btc_irt_market.src_currency,
            self.btc_irt_market.dst_currency,
            Decimal('0.2'),
            Decimal('1000000000'),
            created_at=self.cron.from_datetime + datetime.timedelta(minutes=45),
        )
        trade2.sell_fee_amount = Decimal('200000')
        trade2.save()

        # Run the cron
        self.cron.run()

        # Check that fee transaction trades were created
        fee_transaction_trades = FeeTransactionTradeList.objects.filter(currency=Currencies.rls)
        self.assertEqual(fee_transaction_trades.count(), 1)

        # Verify the fee transaction trade details
        fee_trade = fee_transaction_trades.first()
        self.assertEqual(fee_trade.currency, Currencies.rls)
        self.assertEqual(set(fee_trade.trades), {trade1.id, trade2.id})
        self.assertEqual(fee_trade.transaction.amount, Decimal('300000'))  # 100000 + 200000

    def test_cron_creates_fee_transaction_trades_for_usdt_market(self):
        # Create trades in BTCUSDT market with fees during the previous hour
        trade1 = create_trade(
            self.user1,
            self.user2,
            self.btc_usdt_market.src_currency,
            self.btc_usdt_market.dst_currency,
            Decimal('0.1'),
            Decimal('20000'),
            created_at=self.cron.from_datetime + datetime.timedelta(minutes=15),
        )
        trade1.sell_fee_amount = Decimal('10')
        trade1.buy_fee_amount = Decimal('0.0001')
        trade1.save()

        trade2 = create_trade(
            self.user2,
            self.user1,
            self.btc_usdt_market.src_currency,
            self.btc_usdt_market.dst_currency,
            Decimal('0.2'),
            Decimal('20000'),
            created_at=self.cron.from_datetime + datetime.timedelta(minutes=35),
        )
        trade2.sell_fee_amount = Decimal('20')
        trade2.buy_fee_amount = Decimal('0.0002')
        trade2.save()

        # Run the cron
        self.cron.run()

        fee_transaction_trades = FeeTransactionTradeList.objects.all()
        self.assertEqual(fee_transaction_trades.count(), 2)

        fee_transaction_trades = fee_transaction_trades.filter(currency=Currencies.usdt)
        self.assertEqual(fee_transaction_trades.count(), 1)
        fee_trade = fee_transaction_trades.first()
        self.assertEqual(fee_trade.currency, Currencies.usdt)
        self.assertEqual(set(fee_trade.trades), {trade1.id, trade2.id})
        self.assertEqual(fee_trade.transaction.amount, Decimal('30'))

        # Check BTC fee transaction
        fee_transaction_trades = FeeTransactionTradeList.objects.filter(currency=Currencies.btc)
        self.assertEqual(fee_transaction_trades.count(), 1)
        fee_trade = fee_transaction_trades.first()
        self.assertEqual(fee_trade.currency, Currencies.btc)
        self.assertEqual(set(fee_trade.trades), {trade1.id, trade2.id})
        self.assertEqual(fee_trade.transaction.amount, Decimal('0.0003'))

    def test_cron_creates_fee_transaction_trades_for_multiple_markets(self):
        # Create trades in both markets during the previous hour
        trade1 = create_trade(
            self.user1,
            self.user2,
            self.btc_irt_market.src_currency,
            self.btc_irt_market.dst_currency,
            Decimal('0.1'),
            Decimal('1000000000'),
            created_at=self.cron.from_datetime + datetime.timedelta(minutes=15),
        )
        trade1.sell_fee_amount = Decimal('100000')
        trade1.buy_fee_amount = Decimal('0.0002')
        trade1.save()

        trade2 = create_trade(
            self.user1,
            self.user2,
            self.btc_usdt_market.src_currency,
            self.btc_usdt_market.dst_currency,
            Decimal('0.1'),
            Decimal('20000'),
            created_at=self.cron.from_datetime + datetime.timedelta(minutes=45),
        )
        trade2.sell_fee_amount = Decimal('10')
        trade2.buy_fee_amount = Decimal('0.0001')
        trade2.save()

        # Run the cron
        self.cron.run()

        # Check that fee transaction trades were created for both currencies
        fee_transaction_trades = FeeTransactionTradeList.objects.all()
        self.assertEqual(fee_transaction_trades.count(), 3)  # RLS, USDT, and BTC

        # Verify RLS fee transaction trade
        rls_fee_trade = fee_transaction_trades.get(currency=Currencies.rls)
        self.assertEqual(set(rls_fee_trade.trades), {trade1.id})
        self.assertEqual(rls_fee_trade.transaction.amount, Decimal('100000'))

        # Verify USDT fee transaction trade
        usdt_fee_trade = fee_transaction_trades.get(currency=Currencies.usdt)
        self.assertEqual(set(usdt_fee_trade.trades), {trade2.id})
        self.assertEqual(usdt_fee_trade.transaction.amount, Decimal('10'))

        # Verify BTC fee transaction trade
        btc_fee_trade = fee_transaction_trades.get(currency=Currencies.btc)
        self.assertEqual(set(btc_fee_trade.trades), {trade2.id, trade1.id})
        self.assertEqual(btc_fee_trade.transaction.amount, Decimal('0.0003'))

    def test_cron_ignores_trades_outside_time_window(self):
        # Create trades outside the time window
        trade1 = create_trade(
            self.user1,
            self.user2,
            self.btc_irt_market.src_currency,
            self.btc_irt_market.dst_currency,
            Decimal('0.1'),
            Decimal('1000000000'),
            created_at=self.cron.from_datetime - datetime.timedelta(minutes=1),  # Just before window
        )
        trade1.sell_fee_amount = Decimal('100000')
        trade1.save()

        trade2 = create_trade(
            self.user1,
            self.user2,
            self.btc_irt_market.src_currency,
            self.btc_irt_market.dst_currency,
            Decimal('0.1'),
            Decimal('1000000000'),
            created_at=self.cron.to_datetime,  # At the end of window
        )
        trade2.sell_fee_amount = Decimal('100000')
        trade2.save()

        # Create a trade inside the time window
        trade3 = create_trade(
            self.user1,
            self.user2,
            self.btc_irt_market.src_currency,
            self.btc_irt_market.dst_currency,
            Decimal('0.1'),
            Decimal('1000000000'),
            created_at=self.cron.from_datetime + datetime.timedelta(minutes=15),
        )
        trade3.sell_fee_amount = Decimal('100000')
        trade3.save()

        # Run the cron
        self.cron.run()

        # Check that only the trades inside the window are included
        fee_transaction_trades = FeeTransactionTradeList.objects.filter(currency=Currencies.rls)
        self.assertEqual(fee_transaction_trades.count(), 1)

        fee_trade = fee_transaction_trades.first()
        self.assertEqual(set(fee_trade.trades), {trade3.id})  # trade2 is not included because it's at the end of window
        self.assertEqual(fee_trade.transaction.amount, Decimal('100000'))

    def test_cron_handles_zero_fees(self):
        # Create trades with zero fees during the previous hour
        trade1 = create_trade(
            self.user1,
            self.user2,
            self.btc_irt_market.src_currency,
            self.btc_irt_market.dst_currency,
            Decimal('0.1'),
            Decimal('1000000000'),
            created_at=self.cron.from_datetime + datetime.timedelta(minutes=15),
        )
        trade1.sell_fee_amount = Decimal('0')
        trade1.save()

        trade2 = create_trade(
            self.user1,
            self.user2,
            self.btc_usdt_market.src_currency,
            self.btc_usdt_market.dst_currency,
            Decimal('0.1'),
            Decimal('20000'),
            created_at=self.cron.from_datetime + datetime.timedelta(minutes=45),
        )
        trade2.sell_fee_amount = Decimal('0')
        trade2.buy_fee_amount = Decimal('0')
        trade2.save()

        # Run the cron
        self.cron.run()

        # Check that no fee transaction trades were created
        fee_transaction_trades = FeeTransactionTradeList.objects.all()
        self.assertEqual(fee_transaction_trades.count(), 0)

    def test_usdtirt_market_usdt_fee_in_buy_side(self):
        """Test USDTIRT market where USDT fee is only in buy side"""
        # Create trades in USDTIRT market with fees during the previous hour
        trade1 = create_trade(
            self.user1,
            self.user2,
            self.usdt_irt_market.src_currency,
            self.usdt_irt_market.dst_currency,
            Decimal('100'),
            Decimal('100000'),
            created_at=self.cron.from_datetime + datetime.timedelta(minutes=15),
        )
        trade1.sell_fee_amount = Decimal('100000')  # RLS fee
        trade1.buy_fee_amount = Decimal('0.1')  # USDT fee
        trade1.save()

        trade2 = create_trade(
            self.user2,
            self.user1,
            self.usdt_irt_market.src_currency,
            self.usdt_irt_market.dst_currency,
            Decimal('200'),
            Decimal('100000'),
            created_at=self.cron.from_datetime + datetime.timedelta(minutes=45),
        )
        trade2.sell_fee_amount = Decimal('200000')  # RLS fee
        trade2.buy_fee_amount = Decimal('0.2')  # USDT fee
        trade2.save()

        # Run the cron
        self.cron.run()

        # Check RLS fee transaction
        rls_fee_trades = FeeTransactionTradeList.objects.filter(currency=Currencies.rls)
        self.assertEqual(rls_fee_trades.count(), 1)
        rls_fee_trade = rls_fee_trades.first()
        self.assertEqual(set(rls_fee_trade.trades), {trade1.id, trade2.id})
        self.assertEqual(rls_fee_trade.transaction.amount, Decimal('300000'))  # 100000 + 200000

        # Check USDT fee transaction
        usdt_fee_trades = FeeTransactionTradeList.objects.filter(currency=Currencies.usdt)
        self.assertEqual(usdt_fee_trades.count(), 1)
        usdt_fee_trade = usdt_fee_trades.first()
        self.assertEqual(set(usdt_fee_trade.trades), {trade1.id, trade2.id})
        self.assertEqual(usdt_fee_trade.transaction.amount, Decimal('0.3'))  # 0.1 + 0.2

    def test_usdtirt_market_usdt_fee_in_both_sides(self):
        """Test USDTIRT market where USDT fee is in both buy and sell sides"""
        # Create trades in USDTIRT market with fees during the previous hour
        trade1 = create_trade(
            self.user1,
            self.user2,
            self.usdt_irt_market.src_currency,
            self.usdt_irt_market.dst_currency,
            Decimal('100'),
            Decimal('100000'),
            created_at=self.cron.from_datetime + datetime.timedelta(minutes=15),
        )
        trade1.sell_fee_amount = Decimal('100000')  # RLS fee
        trade1.buy_fee_amount = Decimal('0.1')  # USDT fee
        trade1.save()

        # Create a trade in BTCUSDT market to test USDT fee in sell side
        trade2 = create_trade(
            self.user2,
            self.user1,
            self.btc_usdt_market.src_currency,
            self.btc_usdt_market.dst_currency,
            Decimal('0.1'),
            Decimal('20000'),
            created_at=self.cron.from_datetime + datetime.timedelta(minutes=35),
        )
        trade2.sell_fee_amount = Decimal('10')  # USDT fee
        trade2.buy_fee_amount = Decimal('0.0001')  # BTC fee
        trade2.save()

        # Run the cron
        self.cron.run()

        # Check RLS fee transaction
        rls_fee_trades = FeeTransactionTradeList.objects.filter(currency=Currencies.rls)
        self.assertEqual(rls_fee_trades.count(), 1)
        rls_fee_trade = rls_fee_trades.first()
        self.assertEqual(set(rls_fee_trade.trades), {trade1.id})
        self.assertEqual(rls_fee_trade.transaction.amount, Decimal('100000'))

        # Check USDT fee transaction
        usdt_fee_trades = FeeTransactionTradeList.objects.filter(currency=Currencies.usdt)
        self.assertEqual(usdt_fee_trades.count(), 1)
        usdt_fee_trade = usdt_fee_trades.first()
        self.assertEqual(set(usdt_fee_trade.trades), {trade1.id, trade2.id})
        self.assertEqual(usdt_fee_trade.transaction.amount, Decimal('10.1'))  # 0.1 + 10

        # Check BTC fee transaction
        btc_fee_trades = FeeTransactionTradeList.objects.filter(currency=Currencies.btc)
        self.assertEqual(btc_fee_trades.count(), 1)
        btc_fee_trade = btc_fee_trades.first()
        self.assertEqual(set(btc_fee_trade.trades), {trade2.id})
        self.assertEqual(btc_fee_trade.transaction.amount, Decimal('0.0001'))
