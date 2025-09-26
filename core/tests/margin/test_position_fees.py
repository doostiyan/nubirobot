from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from exchange.accounts.models import User
from exchange.base.calendar import ir_today
from exchange.base.models import Currencies, Settings
from exchange.margin.crons import PositionExtensionFeeCron
from exchange.margin.models import Position, PositionFee
from exchange.margin.services import MarginManager
from exchange.wallet.models import Wallet
from tests.base.utils import create_order


class PositionFeeModelTest(TestCase):

    user: User

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)

    @classmethod
    def reset_wallet(cls, currency: int):
        wallet = Wallet.get_user_wallet(cls.user, currency, tp=Wallet.WALLET_TYPE.margin)
        if wallet.balance_blocked:
            wallet.unblock(wallet.balance_blocked)
        if wallet.balance:
            wallet.create_transaction('manual', -wallet.balance).commit()

    @classmethod
    def charge_margin_wallet(cls, currency: int, amount: str) -> Wallet:
        wallet = Wallet.get_user_wallet(cls.user, currency, tp=Wallet.WALLET_TYPE.margin)
        wallet.create_transaction('manual', amount).commit()
        return wallet

    @classmethod
    def create_position(cls, src_currency: int, dst_currency: int, is_sell: bool, collateral: str) -> Position:
        collateral = Decimal(collateral)
        wallet = Wallet.get_user_wallet(cls.user, dst_currency, tp=Wallet.WALLET_TYPE.margin)
        wallet.block(collateral)
        position = Position.objects.create(
            user=cls.user,
            src_currency=src_currency,
            dst_currency=dst_currency,
            side=Position.SIDES.sell if is_sell else Position.SIDES.buy,
            collateral=collateral,
            created_at=timezone.now() - timezone.timedelta(days=1),
        )
        price = Decimal(collateral) * 100
        order = create_order(position.user, position.src_currency, position.dst_currency, '0.01', price, is_sell)
        position.orders.add(order, through_defaults={})
        return position

    def _test_position_fee_amount(
        self,
        src_currency: int,
        dst_currency: int,
        is_sell: bool,
        margin_balance: str,
        collateral: str,
        expected_fee: str,
    ):
        self.reset_wallet(dst_currency)
        wallet = self.charge_margin_wallet(dst_currency, amount=margin_balance)
        position = self.create_position(src_currency, dst_currency, is_sell, collateral=collateral)
        fee = PositionFee.objects.create(position=position, date=ir_today())
        assert fee.amount == Decimal(expected_fee)
        position.refresh_from_db()
        assert position.collateral == Decimal(collateral) - Decimal(expected_fee)
        wallet.refresh_from_db()
        assert wallet.balance_blocked == position.collateral
        assert wallet.balance == Decimal(margin_balance) - Decimal(expected_fee)
        assert wallet.active_balance == Decimal(margin_balance) - Decimal(collateral)

    def test_position_fee_collateral_below_step(self):
        for currency in (Currencies.btc, Currencies.usdt, Currencies.rls):
            Settings.set(f'position_fee_rate_{currency}', Decimal('0.0005'))
        for is_sell in (True, False):
            self._test_position_fee_amount(
                Currencies.btc,
                Currencies.usdt,
                is_sell,
                margin_balance='50',
                collateral='25',
                expected_fee='0.015',
            )
            self._test_position_fee_amount(
                Currencies.usdt,
                Currencies.rls,
                is_sell,
                margin_balance='5E6',
                collateral='4E6',
                expected_fee='5000',
            )

    def test_position_fee_collateral_above_step(self):
        for currency in (Currencies.bnb, Currencies.usdt):
            Settings.set(f'position_fee_rate_{currency}', Decimal('0.0005'))
        for is_sell in (True, False):
            self._test_position_fee_amount(
                Currencies.bnb,
                Currencies.usdt,
                is_sell,
                margin_balance='580',
                collateral='290',
                expected_fee='0.15',
            )

    def test_position_fee_collateral_multiple_of_step(self):
        for currency in (Currencies.ltc, Currencies.rls):
            Settings.set(f'position_fee_rate_{currency}', Decimal('0.0005'))
        for is_sell in (True, False):
            self._test_position_fee_amount(
                Currencies.ltc,
                Currencies.rls,
                is_sell,
                margin_balance='7E8',
                collateral='6E8',
                expected_fee='300000',
            )

    def test_position_fee_custom_fee_rate_nonzero(self):
        Settings.set(f'position_fee_rate_{Currencies.btc}', '2E-4')
        cache.delete(f'setting_position_fee_rate_{Currencies.btc}')
        Settings.set(f'position_fee_rate_{Currencies.rls}', '1E-4')
        cache.delete(f'setting_position_fee_rate_{Currencies.rls}')
        assert PositionFee.get_fee_rate(Currencies.btc) == Decimal('2E-4')
        assert PositionFee.get_fee_rate(Currencies.rls) == Decimal('1E-4')
        self._test_position_fee_amount(
            Currencies.btc,
            Currencies.rls,
            is_sell=True,
            margin_balance='4E7',
            collateral='3.5E7',
            expected_fee='8000',
        )
        self._test_position_fee_amount(
            Currencies.btc,
            Currencies.rls,
            is_sell=False,
            margin_balance='4E7',
            collateral='3.5E7',
            expected_fee='4000',
        )

    def test_position_fee_custom_fee_rate_zero(self):
        Settings.set(f'position_fee_rate_{Currencies.btc}', '0')
        cache.delete(f'setting_position_fee_rate_{Currencies.btc}')
        Settings.set(f'position_fee_rate_{Currencies.rls}', '0')
        cache.delete(f'setting_position_fee_rate_{Currencies.rls}')
        assert PositionFee.get_fee_rate(Currencies.btc) == 0
        assert PositionFee.get_fee_rate(Currencies.rls) == 0
        for is_sell in (True, False):
            self._test_position_fee_amount(
                Currencies.btc,
                Currencies.rls,
                is_sell,
                margin_balance='4E7',
                collateral='3.5E7',
                expected_fee='0',
            )


class PositionExtensionFeeTest(TestCase):
    positions: list

    @classmethod
    def setUpTestData(cls):
        cls.positions = [
            # Opened today: fee-free
            Position.objects.create(
                user_id=201,
                src_currency=Currencies.ltc,
                dst_currency=Currencies.usdt,
                side=Position.SIDES.sell,
                collateral='132',
            ),
            # Opened today: fee-free
            Position.objects.create(
                user_id=202,
                src_currency=Currencies.btc,
                dst_currency=Currencies.rls,
                side=Position.SIDES.sell,
                collateral='62000000',
                status=Position.STATUS.open,
                delegated_amount='0.01',
                entry_price='6200000000',
            ),
            # Opened yesterday: should pay fee
            Position.objects.create(
                user_id=201,
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                side=Position.SIDES.sell,
                collateral='213',
                status=Position.STATUS.open,
                created_at=timezone.now() - timezone.timedelta(days=1),
                delegated_amount='0.01',
                entry_price='21300',
            ),
            # Opened 3 days ago: should pay fee
            Position.objects.create(
                user_id=202,
                src_currency=Currencies.bnb,
                dst_currency=Currencies.rls,
                side=Position.SIDES.sell,
                collateral='15000000',
                created_at=timezone.now() - timezone.timedelta(days=3),
            ),
            # Opened 31 days ago: should expire
            Position.objects.create(
                user_id=203,
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                side=Position.SIDES.sell,
                collateral='156',
                status=Position.STATUS.open,
                created_at=timezone.now() - timezone.timedelta(days=31),
                delegated_amount='0.01',
                entry_price='15600',
            ),
            # Closed: left untouched
            Position.objects.create(
                user_id=201,
                src_currency=Currencies.ltc,
                dst_currency=Currencies.usdt,
                side=Position.SIDES.sell,
                collateral='70',
                status=Position.STATUS.closed,
                entry_price='7000',
            ),
            # Expired: left untouched
            Position.objects.create(
                user_id=201,
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                side=Position.SIDES.sell,
                collateral='21.3',
                status=Position.STATUS.expired,
            ),
            # Liquidated: left untouched
            Position.objects.create(
                user_id=202,
                src_currency=Currencies.btc,
                dst_currency=Currencies.rls,
                side=Position.SIDES.sell,
                collateral='27000000',
                status=Position.STATUS.liquidated,
                entry_price='6200000000',
            ),
            # Not enough collateral to pay fee: should expire
            Position.objects.create(
                user_id=203,
                src_currency=Currencies.btc,
                dst_currency=Currencies.rls,
                side=Position.SIDES.sell,
                collateral='2_000_0',
                status=Position.STATUS.open,
                created_at=timezone.now() - timezone.timedelta(days=26),
                delegated_amount='0.005',
                entry_price='610_000_000_0',
            ),
            # Not enough collateral to pay fee: should expire
            Position.objects.create(
                user_id=203,
                src_currency=Currencies.btc,
                dst_currency=Currencies.rls,
                side=Position.SIDES.buy,
                collateral='2_000_0',
                status=Position.STATUS.open,
                created_at=timezone.now() - timezone.timedelta(days=26),
                delegated_amount='0.005',
                earned_amount='-3_050_000_0',
            ),
        ]
        for position in cls.positions:
            position.refresh_from_db()
            cls.charge_position(position)
        currencies = {p.src_currency if p.is_short else p.dst_currency for p in cls.positions}
        for currency in currencies:
            PositionFee.get_fee_rate(currency)
            cache.delete(f'setting_position_fee_rate_{currency}')
        cls.add_order(cls.positions[0], '0.01', '13200')
        cls.add_order(cls.positions[3], '0.01', '150_000_000_0')
        cls.add_order(cls.positions[8], '0.005', '580_000_000_0')
        cls.add_order(cls.positions[9], '0.005', '580_000_000_0')
        Settings.set(f'position_fee_rate_{Currencies.btc}', '0.001')

    def setUp(self):
        self.positions = list(Position.objects.order_by('id'))

    @staticmethod
    def charge_position(position: Position):
        wallet = Wallet.get_user_wallet(position.user, position.dst_currency, tp=Wallet.WALLET_TYPE.margin)
        wallet.create_transaction('manual', position.collateral).commit()
        wallet.block(position.collateral)

    @staticmethod
    def add_order(position: Position, amount: str, price: str):
        order = create_order(
            position.user,
            position.src_currency,
            position.dst_currency,
            amount,
            price,
            sell=position.is_short,
        )
        position.orders.add(order, through_defaults={})

    @staticmethod
    def run_position_extension_fee_cron():
        with patch('exchange.margin.models.PositionFee.get_fee_rate', return_value=Decimal('0.0005')):
            PositionExtensionFeeCron().run()

    @staticmethod
    def check_system_fee_wallets(rls: str, usdt: str):
        rls_wallet = Wallet.get_fee_collector_wallet(Currencies.rls)
        assert rls_wallet.balance == Decimal(rls)
        usdt_wallet = Wallet.get_fee_collector_wallet(Currencies.usdt)
        assert usdt_wallet.balance == Decimal(usdt)

    def test_position_extension_1st_run_in_day(self):
        self.run_position_extension_fee_cron()
        fees = PositionFee.objects.order_by('position_id')
        assert len(fees) == 2
        assert fees[0].position_id == self.positions[2].id
        assert fees[0].amount == Decimal('0.12')
        assert fees[1].position_id == self.positions[3].id
        assert fees[1].amount == 1_000_0
        assert fees[0].date == fees[1].date
        self.check_system_fee_wallets(rls='1_000_0', usdt='0.12')

        for position in self.positions[8:10]:
            position.refresh_from_db()
            assert position.status == Position.STATUS.expired
            assert position.freezed_at

    def test_position_extension_2nd_run_in_day(self):
        self.run_position_extension_fee_cron()
        assert PositionFee.objects.count() == 2
        self.run_position_extension_fee_cron()
        assert PositionFee.objects.count() == 2
        self.check_system_fee_wallets(rls='1_000_0', usdt='0.12')

    def test_position_extension_semi_parallel_run(self):
        self.run_position_extension_fee_cron()
        fee = PositionFee.objects.order_by('position_id').first()
        assert fee.position_id == self.positions[2].id
        MarginManager.extend_position(fee.position_id, fee.date)
        assert PositionFee.objects.count() == 2
        assert self.positions[2].fees.count() == 1
        self.check_system_fee_wallets(rls='1_000_0', usdt='0.12')

    def test_position_extension_run_in_two_consecutive_days(self):
        self.run_position_extension_fee_cron()
        day_1_fees = PositionFee.objects.values_list('pk', flat=True)
        assert len(day_1_fees) == 2
        tomorrow = timezone.now() + timezone.timedelta(days=1)
        with patch.object(timezone, 'now', return_value=tomorrow), patch('django_cron.utc_now', return_value=tomorrow):
            self.run_position_extension_fee_cron()
        day_2_fees = PositionFee.objects.exclude(pk__in=list(day_1_fees)).order_by('position_id')
        assert len(day_2_fees) == 4
        for i in range(4):
            assert day_2_fees[i].position_id == self.positions[i].id
        self.check_system_fee_wallets(rls='5_500_0', usdt='0.315')

    def test_position_extension_run_before_position_check_daily_fee(self):
        for currency in (Currencies.btc, Currencies.rls):
            Settings.set(f'position_fee_rate_{currency}', '0.0005')
        self.run_position_extension_fee_cron()
        for position in self.positions:
            position.check_daily_fee()
        assert PositionFee.objects.count() == 2
        self.check_system_fee_wallets(rls='1_000_0', usdt='0.12')

    def test_position_extension_run_after_position_check_daily_fee(self):
        with patch('exchange.margin.models.PositionFee.get_fee_rate', return_value=Decimal('0.0005')):
            for position in self.positions:
                position.check_daily_fee()
        self.run_position_extension_fee_cron()
        assert PositionFee.objects.count() == 2
        self.check_system_fee_wallets(rls='1_000_0', usdt='0.12')
