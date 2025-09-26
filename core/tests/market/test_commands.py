import datetime
import json
from decimal import Decimal
from unittest import mock
from unittest.mock import ANY, MagicMock, call, patch

from django.core.management import call_command
from django.test import TestCase
from django.utils.timezone import now

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.charts.models import Chart, StudyTemplate
from exchange.market.management.commands.market_rename_side_changes import copy_cache_data
from exchange.market.models import Market, OrderMatching, UserMarketsPreferences, UserTradeStatus
from exchange.wallet.models import Transaction, Wallet
from tests.base.utils import create_order, create_trade, do_matching_round


class CommandsTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)
        self.user3 = User.objects.get(pk=203)

    def test_create_verification_profile_command(self):
        UserTradeStatus.objects.all().delete()
        assert UserTradeStatus.objects.count() == 0
        user_one_trade_status_before_command = UserTradeStatus.objects.create(user=self.user1, month_trades_count=10)

        call_command('create_user_trade_status_command')
        assert UserTradeStatus.objects.get(user=self.user1) == user_one_trade_status_before_command
        trade_statuses = sorted(
            list(UserTradeStatus.objects.filter(user__in=[self.user2, self.user3])),
            key=lambda uts: uts.user_id,
        )
        assert len(trade_statuses) == 2
        for ts in trade_statuses:
            for attr in ts.__dict__:
                if attr in ('month_trades_count', 'month_trades_total', 'month_trades_total_trader'):
                    assert getattr(ts, attr) == 0


class RenameMarketCommandTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)

        self.prefs = ['BTCIRT', 'BTCUSDT', 'ETHIRT', 'USDTIRT', 'SHIBIRT', 'DOGEIRT', 'ADAIRT']
        self.user_pref = UserMarketsPreferences.objects.create(user=self.user, favorite_markets=json.dumps(self.prefs))

        self.chart_1 = Chart.objects.create(
            ownerSource='nobitex',
            ownerId='201',
            name='View1',
            symbol='BTCIRT',
            resolution='60',
            lastModified=now(),
            content=json.dumps(
                {
                    'exchange': 'نوبیتکس',
                    'is_realtime': '1',
                    'legs': '[{"symbol":"BTCIRT","pro_symbol":"BTCIRT"}]',
                    'listed_exchange': '',
                    'name': 'View1',
                    'publish_request_id': 'h5dq2kpf5qj',
                    'resolution': '60',
                    'short_name': 'BTCIRT',
                    'symbol': 'BTCIRT',
                    'symbol_type': 'crypto-currency',
                },
            ),
        )
        self.chart_2 = Chart.objects.create(
            ownerSource='nobitex',
            ownerId='201',
            name='View2',
            symbol='ETHIRT',
            resolution='60',
            lastModified=now(),
            content=json.dumps(
                {
                    'exchange': 'نوبیتکس',
                    'is_realtime': '22',
                    'legs': '[{"symbol":"ETHIRT","pro_symbol":"ETHIRT"}]',
                    'listed_exchange': '',
                    'name': 'View2',
                    'publish_request_id': 'dw2211pf5qj',
                    'resolution': '60',
                    'short_name': 'ETHIRT',
                    'symbol': 'ETHIRT',
                    'symbol_type': 'crypto-currency',
                },
            ),
        )

        self.study_template = StudyTemplate.objects.create(
            ownerSource='nobitex',
            ownerId='201',
            name='RNDR',
        )

    @mock.patch('exchange.market.management.commands.market_rename_side_changes.copy_cache_data')
    def test_rename_market_command(self, mock_copy_cache_data):
        call_command('market_rename_side_changes', from_name='BTC', to='BITCOIN')

        self.user_pref.refresh_from_db()
        self.chart_1.refresh_from_db()

        expected_markets = json.dumps(['BITCOINIRT', 'BITCOINUSDT', *self.prefs[2:]])
        assert self.user_pref.favorite_markets == expected_markets

        assert self.chart_1.symbol == 'BITCOINIRT'

    @mock.patch('exchange.market.management.commands.market_rename_side_changes.copy_cache_data')
    def test_no_update_for_non_matching_tokens(self, mock_copy_cache_data):
        call_command('market_rename_side_changes', from_name='DOGE', to='DOGECOIN')

        self.user_pref.refresh_from_db()
        self.chart_1.refresh_from_db()

        expected_markets = json.dumps(['BTCIRT', 'BTCUSDT', 'ETHIRT', 'USDTIRT', 'SHIBIRT', 'DOGECOINIRT', 'ADAIRT'])
        assert self.user_pref.favorite_markets == expected_markets

        assert self.chart_1.symbol == 'BTCIRT'

    @mock.patch('exchange.market.management.commands.market_rename_side_changes.copy_cache_data')
    def test_edge_case_no_unwanted_replacements(self, mock_copy_cache_data):
        self.user_pref.favorite_markets = json.dumps(['HELIRT', 'HELLOIRT', 'BTCIRT', 'DOGEIRT'])
        self.user_pref.save()

        call_command('market_rename_side_changes', from_name='HEL', to='AHEL')

        self.user_pref.refresh_from_db()

        expected_markets = json.dumps(['AHELIRT', 'HELLOIRT', 'BTCIRT', 'DOGEIRT'])
        assert self.user_pref.favorite_markets == expected_markets

    @mock.patch('exchange.market.management.commands.market_rename_side_changes.copy_cache_data')
    def test_no_changes_for_unrelated_symbols(self, mock_copy_cache_data):
        call_command('market_rename_side_changes', from_name='XRP', to='RIPPLE')

        self.user_pref.refresh_from_db()
        self.chart_1.refresh_from_db()

        expected_markets = json.dumps(self.prefs)
        assert self.user_pref.favorite_markets == expected_markets

        assert self.chart_1.symbol == 'BTCIRT'

    @mock.patch('exchange.market.management.commands.market_rename_side_changes.copy_cache_data')
    def test_rename_market_command_updates_content_field(self, mock_copy_cache_data):
        call_command('market_rename_side_changes', from_name='BTC', to='BITCOIN')

        self.chart_1.refresh_from_db()

        assert self.chart_1.symbol == 'BITCOINIRT'

        expected_content = json.dumps(
            {
                'exchange': 'نوبیتکس',
                'is_realtime': '1',
                'legs': '[{"symbol":"BITCOINIRT","pro_symbol":"BITCOINIRT"}]',
                'listed_exchange': '',
                'name': 'View1',
                'publish_request_id': 'h5dq2kpf5qj',
                'resolution': '60',
                'short_name': 'BITCOINIRT',
                'symbol': 'BITCOINIRT',
                'symbol_type': 'crypto-currency',
            },
        )

        assert json.loads(self.chart_1.content) == json.loads(expected_content)

    @mock.patch('exchange.market.management.commands.market_rename_side_changes.copy_cache_data')
    def test_rename_market_command_does_with_explicit_user(self, mock_copy_cache_data):
        call_command('market_rename_side_changes', from_name='BTC', to='BITCOIN', user_id=201)

        self.user_pref.refresh_from_db()
        self.chart_1.refresh_from_db()

        expected_markets = json.dumps(['BITCOINIRT', 'BITCOINUSDT', *self.prefs[2:]])
        assert self.user_pref.favorite_markets == expected_markets
        assert self.chart_1.symbol == 'BITCOINIRT'

        expected_content = json.dumps(
            {
                'exchange': 'نوبیتکس',
                'is_realtime': '1',
                'legs': '[{"symbol":"BITCOINIRT","pro_symbol":"BITCOINIRT"}]',
                'listed_exchange': '',
                'name': 'View1',
                'publish_request_id': 'h5dq2kpf5qj',
                'resolution': '60',
                'short_name': 'BITCOINIRT',
                'symbol': 'BITCOINIRT',
                'symbol_type': 'crypto-currency',
            },
        )

        assert json.loads(self.chart_1.content) == json.loads(expected_content)

    @mock.patch('exchange.market.management.commands.market_rename_side_changes.copy_cache_data')
    def test_rename_market_command_does_with_explicit_user_without_change(self, mock_copy_cache_data):
        call_command('market_rename_side_changes', from_name='BTC', to='BITCOIN', user_id=1212)

        self.user_pref.refresh_from_db()
        self.chart_1.refresh_from_db()

        expected_markets = json.dumps(['BTCIRT', 'BTCUSDT', *self.prefs[2:]])
        assert self.user_pref.favorite_markets == expected_markets
        assert self.chart_1.symbol == 'BTCIRT'

        expected_content = json.dumps(
            {
                'exchange': 'نوبیتکس',
                'is_realtime': '1',
                'legs': '[{"symbol":"BTCIRT","pro_symbol":"BTCIRT"}]',
                'listed_exchange': '',
                'name': 'View1',
                'publish_request_id': 'h5dq2kpf5qj',
                'resolution': '60',
                'short_name': 'BTCIRT',
                'symbol': 'BTCIRT',
                'symbol_type': 'crypto-currency',
            },
        )

        assert json.loads(self.chart_1.content) == json.loads(expected_content)


class CopyCacheDataTestCase(TestCase):
    @mock.patch('exchange.market.management.commands.market_rename_side_changes.caches')
    def test_copy_cache_data(self, mock_caches):
        mock_cache = MagicMock()
        mock_cache.make_key.side_effect = lambda k: f"mk:{k}"
        mock_client = MagicMock()

        mock_cache.client.get_client.return_value = mock_client

        mock_client.scan_iter.return_value = [
            b'marketdata_RNDRUSDT_123',
            b'marketdata_RNDRUSDT_456',
        ]

        mock_cache.get.side_effect = lambda key: f'value_for_{key}'
        mock_cache.ttl.side_effect = lambda key: 300

        mock_pipeline = MagicMock()
        mock_client.pipeline.return_value = mock_pipeline
        mock_pipeline.__enter__.return_value = mock_pipeline

        mock_caches.__getitem__.return_value = mock_cache

        copy_cache_data('RNDRUSDT', 'RENDERUSDT')

        mock_client.scan_iter.assert_called_once_with(match='marketdata_RNDRUSDT_*', count=1000)

        mock_cache.get.assert_any_call('marketdata_RNDRUSDT_123')
        mock_cache.get.assert_any_call('marketdata_RNDRUSDT_456')

        mock_cache.ttl.assert_any_call('marketdata_RNDRUSDT_123')
        mock_cache.ttl.assert_any_call('marketdata_RNDRUSDT_456')

        mock_pipeline.set.assert_any_call(
            mock_cache.make_key('marketdata_RENDERUSDT_123'),
            'value_for_marketdata_RNDRUSDT_123',
            ex=300,
        )
        mock_pipeline.set.assert_any_call(
            mock_cache.make_key('marketdata_RENDERUSDT_456'),
            'value_for_marketdata_RNDRUSDT_456',
            ex=300,
        )

        mock_pipeline.execute.assert_called_once()
        mock_pipeline.__enter__.assert_called_once()
        mock_pipeline.__exit__.assert_called_once()

        mock_cache.make_key.assert_has_calls(
            [
                call('marketdata_RENDERUSDT_123'),
                call('marketdata_RENDERUSDT_456'),
            ],
            any_order=True,
        )


class SettleMissingTransactionCommandTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):

        cls.user1 = User.objects.get(pk=201)
        cls.user2 = User.objects.get(pk=202)
        market = Market.objects.create(
            id=0,
            src_currency=Currencies.unknown,
            dst_currency=Currencies.usdt,
            is_active=True,
        )

        cls.market = market

    def setUp(self):
        in_range_datetime = ir_now() - datetime.timedelta(days=3)
        out_of_range_datetime = ir_now() - datetime.timedelta(days=365)

        trade = create_trade(
            self.user1,
            self.user2,
            amount=Decimal('0.01'),
            price=Decimal('2.7e9'),
            created_at=in_range_datetime,
        )
        out_of_range = create_trade(
            self.user1,
            self.user2,
            amount=Decimal('0.01'),
            price=Decimal('2.7e9'),
            created_at=out_of_range_datetime,
        )
        trade.create_sell_withdraw_transaction()
        trade.create_buy_withdraw_transaction()

        out_of_range.create_sell_withdraw_transaction()
        out_of_range.create_buy_withdraw_transaction()

        self.trade = trade
        self.out_of_range_trade = out_of_range


    def test_create_transaction(self):

        assert self.trade
        assert self.trade.sell_deposit_id is None
        assert self.trade.sell_withdraw_id is None
        assert self.trade.buy_deposit_id is None
        assert self.trade.buy_withdraw_id is None

        assert self.out_of_range_trade
        assert self.out_of_range_trade.sell_deposit_id is None
        assert self.out_of_range_trade.sell_withdraw_id is None
        assert self.out_of_range_trade.buy_deposit_id is None
        assert self.out_of_range_trade.buy_withdraw_id is None

        call_command('settle_missing_transactions', from_n_days_ago='60', to_n_days_ago='1', dry_run=False)

        self.trade.refresh_from_db()
        self.out_of_range_trade.refresh_from_db()
        assert self.trade.sell_deposit_id
        assert 'فروش ' in self.trade.sell_deposit.description
        assert 'فروش ' in self.trade.sell_withdraw.description
        assert self.trade.buy_deposit_id
        assert 'خرید ' in self.trade.buy_deposit.description
        assert 'خرید ' in self.trade.buy_withdraw.description

        assert self.out_of_range_trade
        assert self.out_of_range_trade.sell_deposit_id is None
        assert self.out_of_range_trade.sell_withdraw_id is None
        assert self.out_of_range_trade.buy_deposit_id is None
        assert self.out_of_range_trade.buy_withdraw_id is None


    def test_create_transaction_when_dry_run_is_enabled(self):

        assert self.trade
        assert self.trade.sell_deposit_id is None
        assert self.trade.sell_withdraw_id is None
        assert self.trade.buy_deposit_id is None
        assert self.trade.buy_withdraw_id is None

        call_command('settle_missing_transactions', from_n_days_ago='60', to_n_days_ago='1', dry_run=True)

        self.trade.refresh_from_db()

        assert self.trade
        assert self.trade.sell_deposit_id is None
        assert self.trade.sell_withdraw_id is None
        assert self.trade.buy_deposit_id is None
        assert self.trade.buy_withdraw_id is None


class ReverseTradeCommand(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.market = Market.by_symbol('BTCUSDT')
        cls.users = list(User.objects.filter(pk__gt=200)[:2])

    def _check_wallets(self, users, currencies, balances):
        for u, c, b in zip(users, currencies, balances):
            assert Wallet.get_user_wallet(u, c).balance == b

    def test_reverse_trade(self):
        create_order(
            self.users[0], self.market.src_currency, self.market.dst_currency, Decimal('1'), Decimal('1000'), True
        )
        create_order(
            self.users[1], self.market.src_currency, self.market.dst_currency, Decimal('1'), Decimal('1000'), False
        )
        assert Transaction.objects.count() == 2
        self._check_wallets(
            self.users,
            (self.market.src_currency, self.market.dst_currency),
            (Decimal('1'), Decimal('1000')),
        )

        do_matching_round(self.market, reinitialize_caches=True)
        assert Transaction.objects.count() == 6
        trade = OrderMatching.objects.order_by('-id').first()
        self._check_wallets(
            self.users,
            (self.market.dst_currency, self.market.src_currency),
            (Decimal('1000') - trade.sell_fee_amount, Decimal('1') - trade.buy_fee_amount),
        )

        assert trade.matched_amount == Decimal('1')
        call_command(
            'reverse_trade',
            trade=trade.id,
        )
        trade.refresh_from_db()
        assert trade.matched_amount == Decimal('0')
        assert trade.buy_fee_amount == Decimal('0')
        assert trade.sell_fee_amount == Decimal('0')
        assert Transaction.objects.count() == 10
        self._check_wallets(
            self.users,
            (self.market.src_currency, self.market.dst_currency),
            (Decimal('1'), Decimal('1000')),
        )
