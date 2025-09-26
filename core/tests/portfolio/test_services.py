import datetime
from decimal import Decimal
from typing import List, Tuple
from unittest.mock import patch

from django.test import TestCase
from freezegun import freeze_time

from exchange.accounts.models import BankAccount, User
from exchange.base.calendar import get_earliest_time, get_first_and_last_of_jalali_month, ir_now, ir_today, ir_tz
from exchange.base.constants import ZERO
from exchange.base.models import Currencies
from exchange.corporate_banking.models import (
    ACCOUNT_TP,
    NOBITEX_BANK_CHOICES,
    STATEMENT_STATUS,
    STATEMENT_TYPE,
    CoBankAccount,
    CoBankStatement,
    CoBankUserDeposit,
)
from exchange.direct_debit.models import DirectDebitBank, DirectDebitContract, DirectDeposit
from exchange.features.models import QueueItem
from exchange.market.models import Market, MarketCandle, Order, OrderMatching
from exchange.pool.models import DelegationTransaction, LiquidityPool, UserDelegation
from exchange.portfolio.models import UserTotalDailyProfit, UserTotalMonthlyProfit
from exchange.portfolio.services import (
    DailyPortfolioGenerator,
    MonthlyPortfolioGenerator,
    delete_old_daily_user_profit,
    enable_portfolios,
)
from exchange.shetab.models import ShetabDeposit
from exchange.staking.models.external import ExternalEarningPlatform
from exchange.staking.models.plan import Plan
from exchange.staking.models.staking import StakingTransaction
from exchange.staking.service.reject_requests.subscription import reject_user_subscription
from exchange.staking.service.subscription import subscribe
from exchange.wallet.models import BankDeposit, ConfirmedWalletDeposit, Wallet, WithdrawRequest
from exchange.xchange.models import ExchangeTrade, MarketStatus
from exchange.xchange.trader import XchangeTrader

original_get_first_transaction_id = DailyPortfolioGenerator.get_first_transaction_id

today = datetime.date.today()
utcoffset = ir_tz().utcoffset(datetime.datetime.now()).total_seconds() / 3600
# DailyPortfolioGenerator.get_first_transaction_id has an issue when the first transaction ID
# after `from_time` is less than 1000. This is not a problem in production or when running all tests together.
# But, when running only the portfolio tests on their own,
# the method returns a negative number because the safety margin is set to 1000.
# To avoid this, we mock the `get_first_transaction_id` method and force the safety margin to be 1.
@patch.object(
    DailyPortfolioGenerator,
    'get_first_transaction_id',
    side_effect=lambda from_time, transaction_safety_margin=1000: original_get_first_transaction_id(
        from_time, transaction_safety_margin=1
    ),
)
class DailyPortfolioTest(TestCase):
    now: datetime.datetime
    cobank_account: CoBankAccount

    @classmethod
    def setUpTestData(cls):
        cls.now = ir_now()
        cls.set_market_prices(
            {
                Currencies.btc: 1_250_000_000_0,
                Currencies.usdt: 50_000_0,
                Currencies.doge: 3_000_0,
            },
            date=cls.now.date(),
        )
        enable_portfolios(user_ids=(201, 202, 203))  # set flags
        BankAccount.objects.create(id=1, user_id=201)
        BankAccount.objects.create(id=2, user_id=202)

        direct_debit_bank_1 = DirectDebitBank.objects.create(
            id=1, bank_id='101', daily_max_transaction_amount='500_000_000_0', name="ملت"
        )
        direct_debit_bank_2 = DirectDebitBank.objects.create(
            id=2, bank_id='102', daily_max_transaction_amount='500_000_000_0', name="صادرات"
        )
        direct_debit_bank_3 = DirectDebitBank.objects.create(
            id=3, bank_id='103', daily_max_transaction_amount='500_000_000_0', name="ملی"
        )
        DirectDebitContract.objects.create(
            id=1,
            user_id=201,
            status=DirectDebitContract.STATUS.active,
            bank=direct_debit_bank_1,
            contract_code="cc101",
            contract_id="ci101",
            trace_id="t101",
            expires_at=cls.now + datetime.timedelta(days=10),
        )
        DirectDebitContract.objects.create(
            id=2,
            user_id=202,
            status=DirectDebitContract.STATUS.active,
            bank=direct_debit_bank_2,
            contract_code="cc102",
            contract_id="ci102",
            trace_id="t102",
            expires_at=cls.now + datetime.timedelta(days=10),
        )
        DirectDebitContract.objects.create(
            id=3,
            user_id=203,
            status=DirectDebitContract.STATUS.active,
            bank=direct_debit_bank_3,
            contract_code="cc103",
            contract_id="ci103",
            trace_id="t103",
            expires_at=cls.now + datetime.timedelta(days=10),
        )
        cls.cobank_account = CoBankAccount.objects.create(
            provider_bank_id=11,
            bank=NOBITEX_BANK_CHOICES.saman,
            iban='IR999999999999999999999991',
            account_number='000111222',
            account_owner='راهکار فناوری نویان',
            is_active=True,
            account_tp=ACCOUNT_TP.operational,
            is_deleted=False,
        )

    @staticmethod
    def set_market_prices(currency_prices: dict, date: datetime.date):
        for currency, price in currency_prices.items():
            MarketCandle.objects.create(
                market=Market.get_for(currency, Currencies.rls),
                resolution=MarketCandle.RESOLUTIONS.day,
                start_time=get_earliest_time(date),
                open_price=price * Decimal('1.01'),
                low_price=price * Decimal('0.95'),
                high_price=price * Decimal('1.06'),
                close_price=price,
            )

    @staticmethod
    def create_shetab_deposit(user_id: int, amount: int, created_at: datetime.datetime) -> ShetabDeposit:
        wallet = Wallet.get_user_wallet(user_id, Currencies.rls)
        deposit = ShetabDeposit(
            user_id=user_id,
            status_code=ShetabDeposit.STATUS.pay_success,
            amount=amount,
            fee=1_000_0,
        )
        transaction = wallet.create_transaction('deposit', deposit.net_amount, created_at=created_at)
        transaction.commit()
        deposit.transaction = transaction
        deposit.save()
        return deposit

    @staticmethod
    def create_bank_deposit(user_id: int, amount: int, created_at: datetime.datetime) -> BankDeposit:
        deposit = BankDeposit.objects.create(
            user_id=user_id,
            receipt_id=f'{user_id}-{BankDeposit.objects.filter(user_id=user_id).count()}',
            src_bank_account_id=user_id % 200,
            dst_bank_account='nobitex',
            deposited_at=ir_today() - datetime.timedelta(days=1),
            amount=amount,
            fee=1_000_0,
            confirmed=True,
        )
        with patch('exchange.wallet.models.now', return_value=created_at):
            deposit.commit_deposit()
        return deposit

    @staticmethod
    def create_coin_deposit(
        user_id: int,
        amount: str,
        currency: int,
        rial_value: int,
        created_at: datetime.datetime,
    ) -> ConfirmedWalletDeposit:
        wallet = Wallet.get_user_wallet(user_id, currency)
        transaction = wallet.create_transaction('deposit', amount, created_at=created_at)
        transaction.commit()
        tx_hash = f'{wallet.id}-{ConfirmedWalletDeposit.objects.filter(_wallet=wallet).count()}'
        return ConfirmedWalletDeposit.objects.create(
            tx_hash=tx_hash,
            _wallet=wallet,
            invoice=f'lnbt200u...{tx_hash}',
            amount=Decimal(amount),
            rial_value=rial_value,
            transaction=transaction,
            confirmed=True,
            created_at=created_at,
        )

    @staticmethod
    def create_direct_deposit(user_id: int, amount: int, created_at: datetime.datetime) -> DirectDeposit:
        deposit = DirectDeposit.objects.create(
            status=DirectDeposit.STATUS.succeed,
            contract_id=user_id % 100,
            amount=amount,
            fee=1_000_0,
        )
        with patch('exchange.wallet.models.now', return_value=created_at):
            deposit.commit_deposit()
        return deposit

    @classmethod
    def create_cobank_deposit(cls, user_id: int, amount: int, created_at: datetime.datetime) -> CoBankUserDeposit:
        statement = CoBankStatement.objects.create(
            amount=amount,
            tp=STATEMENT_TYPE.deposit,
            tracing_number='abcd1234',
            transaction_datetime=created_at,
            status=STATEMENT_STATUS.executed,
            destination_account=cls.cobank_account,
            payment_id='12345',
        )

        with patch('exchange.corporate_banking.models.deposit.ir_now', return_value=created_at):
            return CoBankUserDeposit.objects.create(
                cobank_statement=statement,
                user_id=user_id,
                user_bank_account_id=user_id % 200,
                amount=amount,
                created_at=created_at,
            )

    @staticmethod
    def create_withdraw(
        user_id: int,
        amount: str,
        currency: int,
        rial_value: int,
        created_at: datetime.datetime,
    ) -> WithdrawRequest:
        with patch('exchange.wallet.models.now', return_value=created_at):
            withdraw = WithdrawRequest.objects.create(
                wallet=Wallet.get_user_wallet(user_id, currency),
                amount=Decimal(amount),
                status=WithdrawRequest.STATUS.sent,
            )
        WithdrawRequest.objects.filter(pk=withdraw.pk).update(rial_value=rial_value)
        return withdraw

    @staticmethod
    def create_trade(
        seller_id: int,
        buyer_id: int,
        src: int,
        dst: int,
        amount: str,
        price: str,
        created_at: datetime.datetime,
    ) -> OrderMatching:
        amount = Decimal(amount)
        price = Decimal(price)
        fee_rate = Decimal('0.002')
        order_shared_data = dict(src_currency=src, dst_currency=dst, amount=amount, price=price)
        sell_order = Order.objects.create(user_id=seller_id, order_type=Order.ORDER_TYPES.sell, **order_shared_data)
        buy_order = Order.objects.create(user_id=buyer_id, order_type=Order.ORDER_TYPES.buy, **order_shared_data)
        trade = OrderMatching(
            created_at=created_at,
            market=Market.get_for(src, dst),
            sell_order=sell_order,
            buy_order=buy_order,
            seller_id=seller_id,
            buyer_id=buyer_id,
            matched_price=price,
            matched_amount=amount,
            is_seller_maker=True,
            sell_fee_amount=amount * price * fee_rate,
            buy_fee_amount=amount * fee_rate,
        )
        sell_withdraw = Wallet.get_user_wallet(seller_id, src).create_transaction(
            'sell',
            -trade.matched_amount,
            created_at=created_at,
        )
        sell_deposit = Wallet.get_user_wallet(seller_id, dst).create_transaction(
            'buy',
            trade.matched_total_price - trade.sell_fee_amount,
            created_at=created_at,
        )
        buy_deposit = Wallet.get_user_wallet(buyer_id, src).create_transaction(
            'buy',
            trade.matched_amount - trade.buy_fee_amount,
            created_at=created_at,
        )
        buy_withdraw = Wallet.get_user_wallet(buyer_id, dst).create_transaction(
            'sell',
            -trade.matched_total_price,
            created_at=created_at,
        )
        for transaction in (sell_withdraw, buy_withdraw, sell_deposit, buy_deposit):
            transaction.commit()
        trade.sell_withdraw = sell_withdraw
        trade.sell_deposit = sell_deposit
        trade.buy_deposit = buy_deposit
        trade.buy_withdraw = buy_withdraw
        trade.save()
        return trade

    @staticmethod
    def create_pool_tx(
        user_id: int,
        amount: str,
        currency: int,
        created_at: datetime.datetime,
        manager_id=410,
    ) -> DelegationTransaction:
        pool, _ = LiquidityPool.objects.get_or_create(currency=currency, capacity=10000, manager_id=manager_id)
        pool.src_wallet.create_transaction('manual', abs(amount)).commit()
        with patch('exchange.wallet.models.now', return_value=created_at), patch(
            'exchange.pool.models.timezone.now', return_value=created_at
        ):
            delegation_tx = DelegationTransaction.objects.create(
                user_delegation=UserDelegation.objects.get_or_create(pool=pool, user_id=user_id)[0],
                amount=Decimal(amount),
                created_at=created_at,
            )
        return delegation_tx

    @staticmethod
    def create_external_earning_tx(
        user_id: int,
        amount: Decimal,
        currency: int,
        tp: int,
        created_at: datetime.datetime,
    ) -> StakingTransaction:
        external_platform, _ = ExternalEarningPlatform.objects.get_or_create(
            tp=tp,
            currency=currency,
            network='network',
            address='address',
            tag='tag',
        )

        plan, _ = Plan.objects.get_or_create(
            external_platform=external_platform,
            defaults=dict(
                is_extendable=False,
                min_staking_amount=Decimal('1'),
                staking_precision=Decimal('0.1'),
                total_capacity=Decimal('100'),
                filled_capacity=Decimal('50'),
                request_period=datetime.timedelta(days=1000),
                staking_period=datetime.timedelta(days=0),
                unstaking_period=datetime.timedelta(days=0),
                fee=Decimal('0.2'),
                estimated_annual_rate=Decimal('.44'),
                initial_pool_capacity=Decimal('100'),
                reward_announcement_period=datetime.timedelta(days=1),
                announced_at=created_at - datetime.timedelta(days=100),
                opened_at=created_at - datetime.timedelta(days=100),
                staked_at=created_at - datetime.timedelta(days=100),
            ),
        )

        with patch('exchange.wallet.models.now', return_value=created_at), patch(
            'exchange.staking.models.staking.ir_now', return_value=created_at
        ), patch('exchange.staking.service.subscription.ir_now', return_value=created_at):
            amount = Decimal(amount)
            if amount > ZERO:
                staking_tx = subscribe(user=User.objects.get(id=user_id), plan_id=plan.id, amount=amount)
            else:
                staking_tx = reject_user_subscription(user_id=user_id, plan_id=plan.id, amount=amount * -1)
        return staking_tx

    def create_xchange_market_price(self, market_status_info: List[Tuple]):
        for base_currency, quote_currency, base_to_quote_price_sell in market_status_info:
            defaults = {
                'base_to_quote_price_buy': base_to_quote_price_sell * Decimal('1.1'),
                'quote_to_base_price_buy': Decimal(1) / base_to_quote_price_sell,
                'base_to_quote_price_sell': base_to_quote_price_sell,
                'quote_to_base_price_sell': Decimal(1) / base_to_quote_price_sell,
                'min_base_amount': Decimal(1),
                'max_base_amount': Decimal(1),
                'min_quote_amount': Decimal(1),
                'max_quote_amount': Decimal(1),
                'base_precision': Decimal('0.001'),
                'quote_precision': Decimal('0.001'),
                'status': MarketStatus.STATUS_CHOICES.available,
            }
            MarketStatus.objects.update_or_create(
                base_currency=base_currency,
                quote_currency=quote_currency,
                defaults=defaults,
            )

    def create_xchange_trade(
        self,
        user_id: int,
        xchange_user_id: int,
        src_currency: int,
        dst_currency: int,
        src_amount: Decimal,
        dst_amount: Decimal,
    ):
        xchange_trade = ExchangeTrade(
            user=User.objects.get(pk=user_id),
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=src_currency,
            dst_currency=dst_currency,
            src_amount=src_amount,
            dst_amount=dst_amount,
            quote_id='123',
            client_order_id='234',
        )
        xchange_trade.created_at = self.now
        xchange_trade.save()
        with patch(
            'exchange.xchange.trader.get_market_maker_system_user', return_value=User.objects.get(pk=xchange_user_id)
        ):
            XchangeTrader.create_and_commit_wallet_transactions(xchange_trade)

    def test_create_daily_profits_no_transactions(self, _):
        DailyPortfolioGenerator(report_date=self.now.date()).create_users_profits()
        profits = UserTotalDailyProfit.objects.all().order_by('report_date', 'user_id')
        assert len(profits) == 0

    def test_create_daily_profits_after_deposits_first_portfolio(self, _):
        self.create_shetab_deposit(user_id=201, amount=2_000_000_0, created_at=self.now.replace(hour=6))
        self.create_bank_deposit(user_id=202, amount=3_000_000_0, created_at=self.now.replace(hour=8))
        self.create_coin_deposit(
            user_id=203,
            amount='0.001',
            currency=Currencies.btc,
            rial_value=1_250_000_0,
            created_at=self.now.replace(hour=10),
        )
        self.create_coin_deposit(
            user_id=202,
            amount='120',
            currency=Currencies.doge,
            rial_value=360_000_0,
            created_at=self.now.replace(hour=12),
        )
        self.create_bank_deposit(user_id=201, amount=10_000_000_0, created_at=self.now.replace(hour=14))
        self.create_coin_deposit(
            user_id=203,
            amount='10',
            currency=Currencies.usdt,
            rial_value=500_000_0,
            created_at=self.now.replace(hour=16),
        )
        self.create_shetab_deposit(user_id=201, amount=1_000_000_0, created_at=self.now.replace(hour=14))
        DailyPortfolioGenerator(report_date=self.now.date(), is_first=True).create_users_profits()
        profits = UserTotalDailyProfit.objects.all().order_by('report_date', 'user_id')
        assert len(profits) == 3
        for i, profit in enumerate(profits, start=201):
            assert profit.total_deposit == 0
            assert profit.total_withdraw == 0
            assert profit.profit == 0
            assert profit.profit_percentage == 0
            assert profit.report_date == self.now.date()
            assert profit.user_id == i
        assert profits[0].total_balance == 12_997_000_0
        assert profits[1].total_balance == 3_359_000_0
        assert profits[2].total_balance == 1_750_000_0

    @freeze_time(f'{today} 00:00:00', tz_offset=utcoffset)
    def test_create_daily_profits_after_deposits_ongoing_portfolio(self, _):
        self.create_shetab_deposit(user_id=201, amount=2_000_000_0, created_at=self.now.replace(hour=6))
        self.create_bank_deposit(user_id=202, amount=3_000_000_0, created_at=self.now.replace(hour=8))
        self.create_coin_deposit(
            user_id=203,
            amount='0.001',
            currency=Currencies.btc,
            rial_value=1_280_000_0,
            created_at=self.now.replace(hour=10),
        )
        self.create_coin_deposit(
            user_id=202,
            amount='120',
            currency=Currencies.doge,
            rial_value=350_000_0,
            created_at=self.now.replace(hour=12),
        )
        self.create_direct_deposit(user_id=202, amount=5_000_000_0, created_at=self.now.replace(hour=13))
        self.create_bank_deposit(user_id=201, amount=10_000_000_0, created_at=self.now.replace(hour=14))
        self.create_cobank_deposit(user_id=201, amount=1_000_000_0, created_at=self.now.replace(hour=15))
        self.create_coin_deposit(
            user_id=203,
            amount='10',
            currency=Currencies.usdt,
            rial_value=510_000_0,
            created_at=self.now.replace(hour=16),
        )
        self.create_cobank_deposit(user_id=202, amount=20_000_000_0, created_at=self.now.replace(hour=17))
        self.create_direct_deposit(user_id=203, amount=500_000_0, created_at=self.now.replace(hour=18))
        DailyPortfolioGenerator(report_date=self.now.date()).create_users_profits()
        profits = UserTotalDailyProfit.objects.all().order_by('report_date', 'user_id')
        assert len(profits) == 3
        for i, profit in enumerate(profits, start=201):
            assert profit.total_withdraw == 0
            assert profit.report_date == self.now.date()
            assert profit.user_id == i
        assert profits[0].total_balance == 12_997_900_0
        assert profits[0].total_deposit == 13_000_000_0
        assert profits[0].profit == -21_000
        assert profits[0].profit_percentage == Decimal('-0.0161538462')
        assert profits[1].total_balance == 28_356_000_0
        assert profits[1].total_deposit == 28_350_000_0
        assert profits[1].profit == 6_000_0
        assert profits[1].profit_percentage == Decimal('0.0211640212')
        assert profits[2].total_balance == 2_249_000_0
        assert profits[2].total_deposit == 2_290_000_0
        assert profits[2].profit == -41_000_0
        assert profits[2].profit_percentage == Decimal('-1.7903930131')

    def test_create_daily_profits_after_withdraws(self, _):
        day_ago = self.now - datetime.timedelta(days=1)
        self.create_bank_deposit(user_id=201, amount=12_000_000_0, created_at=day_ago.replace(hour=6))
        self.create_coin_deposit(
            user_id=203,
            amount='0.001',
            currency=Currencies.btc,
            rial_value=1_280_000_0,
            created_at=day_ago.replace(hour=8),
        )
        self.create_coin_deposit(
            user_id=202,
            amount='20',
            currency=Currencies.usdt,
            rial_value=1_030_000_0,
            created_at=day_ago.replace(hour=10),
        )
        self.set_market_prices(
            {
                Currencies.btc: 1_280_000_000_0,
                Currencies.usdt: 52_000_0,
                Currencies.doge: 2_900_0,
            },
            day_ago.date(),
        )
        DailyPortfolioGenerator(report_date=day_ago.date(), is_first=True).create_users_profits()

        self.create_shetab_deposit(user_id=202, amount=3_000_000_0, created_at=self.now.replace(hour=7))
        self.create_coin_deposit(
            user_id=203,
            amount='10',
            currency=Currencies.usdt,
            rial_value=510_000_0,
            created_at=self.now.replace(hour=9),
        )
        self.create_withdraw(
            user_id=201,
            amount='2_000_000_0',
            currency=Currencies.rls,
            rial_value=2_000_000_0,
            created_at=self.now.replace(hour=11),
        )
        self.create_withdraw(
            user_id=202,
            amount='500_000_0',
            currency=Currencies.rls,
            rial_value=500_000_0,
            created_at=self.now.replace(hour=13),
        )
        self.create_withdraw(
            user_id=203,
            amount='6',
            currency=Currencies.usdt,
            rial_value=305_000_0,
            created_at=self.now.replace(hour=15),
        )
        self.create_withdraw(
            user_id=202,
            amount='10',
            currency=Currencies.usdt,
            rial_value=498_000_0,
            created_at=self.now.replace(hour=19),
        )
        DailyPortfolioGenerator(report_date=self.now.date()).create_users_profits()
        profits = UserTotalDailyProfit.objects.all().order_by('report_date', 'user_id')
        assert len(profits) == 6
        for profit in profits[:3]:
            assert profit.total_withdraw == 0
            assert profit.profit == 0
            assert profit.profit_percentage == 0
            assert profit.report_date < self.now.date()
        for i, profit in enumerate(profits[3:], start=201):
            assert profit.report_date == self.now.date()
            assert profit.user_id == i
        assert profits[0].total_balance == 11_999_000_0
        assert profits[3].total_balance == 9_999_000_0
        assert profits[3].total_deposit == 0
        assert profits[3].total_withdraw == 2_000_000_0
        assert profits[3].profit == 0
        assert profits[3].profit_percentage == 0
        assert profits[1].total_balance == 1_040_000_0
        assert profits[4].total_balance == 2_999_000_0
        assert profits[4].total_deposit == 3_000_000_0
        assert profits[4].total_withdraw == 998_000_0
        assert profits[4].profit == -43_000_0
        assert profits[4].profit_percentage == Decimal('-1.0643564356')
        assert profits[2].total_balance == 1_280_000_0
        assert profits[5].total_balance == 1_450_000_0
        assert profits[5].total_deposit == 510_000_0
        assert profits[5].total_withdraw == 305_000_0
        assert profits[5].profit == -35_000_0
        assert profits[5].profit_percentage == Decimal('-1.9553072626')

    def test_create_daily_profits_after_pool_transactions(self, _):
        day_ago = self.now - datetime.timedelta(days=1)
        self.set_market_prices(
            {
                Currencies.btc: 1_280_000_000_0,
                Currencies.usdt: 52_000_0,
                Currencies.doge: 2_900_0,
            },
            day_ago.date(),
        )

        Wallet.get_user_wallet(201, Currencies.btc).create_transaction(
            'manual', 5, created_at=day_ago - datetime.timedelta(days=4)
        ).commit()

        Wallet.get_user_wallet(201, Currencies.usdt).create_transaction(
            'manual', 100, created_at=day_ago - datetime.timedelta(days=4)
        ).commit()

        self.create_pool_tx(
            user_id=201, amount=1, currency=Currencies.btc, created_at=day_ago - datetime.timedelta(days=1)
        )
        self.create_pool_tx(user_id=201, amount=1, currency=Currencies.btc, created_at=day_ago.replace(hour=4))
        pool_tx1 = self.create_pool_tx(
            user_id=201, amount=1, currency=Currencies.btc, created_at=self.now.replace(hour=4)
        )

        self.create_pool_tx(
            user_id=201,
            amount=1,
            currency=Currencies.btc,
            created_at=self.now + datetime.timedelta(days=1),
        )

        pool_tx1.user_delegation.closed_at = self.now + datetime.timedelta(days=1)
        pool_tx1.user_delegation.save(update_fields=('closed_at',))

        self.create_pool_tx(
            user_id=201,
            amount=10,
            currency=Currencies.usdt,
            created_at=day_ago.replace(hour=4),
            manager_id=411,
        )

        DailyPortfolioGenerator(report_date=day_ago.date(), is_first=True).create_users_profits()
        profits = UserTotalDailyProfit.objects.filter(user_id=201).order_by('report_date', 'user_id')
        assert len(profits) == 1
        assert profits[0].total_balance == 1_280_000_000_0 * 5 + 52_000_0 * 100
        assert profits[0].total_deposit == 0
        assert profits[0].total_withdraw == 0
        assert profits[0].profit == 0
        assert profits[0].profit_percentage == 0

        DailyPortfolioGenerator(report_date=self.now.date()).create_users_profits()
        profits = UserTotalDailyProfit.objects.filter(user_id=201).order_by('report_date', 'user_id')
        assert len(profits) == 2
        assert profits[1].total_balance == 1_250_000_000_0 * 5 + 50_000_0 * 100
        assert profits[1].total_deposit == 0
        assert profits[1].total_withdraw == 0
        assert profits[1].profit == (1_250_000_000_0 - 1_280_000_000_0) * 5 + (50_000_0 - 52_000_0) * 100
        assert profits[1].profit_percentage == Decimal('-2.3449697121')

    def test_create_daily_profits_after_staking_and_yield_farming_transactions(self, _):
        day_ago = self.now - datetime.timedelta(days=1)
        self.set_market_prices(
            {
                Currencies.btc: 1_280_000_000_0,
                Currencies.usdt: 52_000_0,
                Currencies.doge: 2_900_0,
            },
            day_ago.date(),
        )

        Wallet.get_user_wallet(201, Currencies.btc).create_transaction(
            'manual', 10, created_at=day_ago - datetime.timedelta(days=4)
        ).commit()

        Wallet.get_user_wallet(201, Currencies.usdt).create_transaction(
            'manual', 10, created_at=day_ago - datetime.timedelta(days=4)
        ).commit()

        self.create_external_earning_tx(
            user_id=201,
            amount=4,
            currency=Currencies.btc,
            tp=ExternalEarningPlatform.TYPES.staking,
            created_at=day_ago.replace(hour=20),
        )

        self.create_external_earning_tx(
            user_id=201,
            amount=2,
            currency=Currencies.btc,
            tp=ExternalEarningPlatform.TYPES.yield_aggregator,
            created_at=day_ago - datetime.timedelta(days=1),
        )

        self.create_external_earning_tx(
            user_id=201,
            amount=-1,
            currency=Currencies.btc,
            tp=ExternalEarningPlatform.TYPES.yield_aggregator,
            created_at=self.now.replace(hour=4),
        )

        self.create_external_earning_tx(
            user_id=201,
            amount=-2,
            currency=Currencies.btc,
            tp=ExternalEarningPlatform.TYPES.staking,
            created_at=self.now.replace(hour=4),
        )

        self.create_external_earning_tx(
            user_id=201,
            amount=10,
            currency=Currencies.usdt,
            tp=ExternalEarningPlatform.TYPES.staking,
            created_at=self.now.replace(hour=4),
        )

        self.create_external_earning_tx(
            user_id=201,
            amount=1,
            currency=Currencies.btc,
            tp=ExternalEarningPlatform.TYPES.yield_aggregator,
            created_at=self.now + datetime.timedelta(days=4),
        )
        self.create_external_earning_tx(
            user_id=201,
            amount=1,
            currency=Currencies.btc,
            tp=ExternalEarningPlatform.TYPES.staking,
            created_at=self.now + datetime.timedelta(days=5),
        )

        DailyPortfolioGenerator(report_date=day_ago.date(), is_first=True).create_users_profits()
        profits = UserTotalDailyProfit.objects.filter(user_id=201).order_by('report_date', 'user_id')
        assert len(profits) == 1
        assert profits[0].total_balance == 1_280_000_000_0 * 10 + 52_000_0 * 10
        assert profits[0].total_deposit == 0
        assert profits[0].total_withdraw == 0
        assert profits[0].profit == 0
        assert profits[0].profit_percentage == 0

        DailyPortfolioGenerator(report_date=self.now.date()).create_users_profits()
        profits = UserTotalDailyProfit.objects.filter(user_id=201).order_by('report_date', 'user_id')
        assert len(profits) == 2
        assert profits[1].total_balance == 1_250_000_000_0 * 10 + 50_000_0 * 10
        assert profits[1].total_deposit == 0
        assert profits[1].total_withdraw == 0
        assert profits[1].profit == (1_250_000_000_0 - 1_280_000_000_0) * 10 + (50_000_0 - 52_000_0) * 10
        assert profits[1].profit_percentage == Decimal('-2.3438110327')

    def test_create_daily_profits_after_withdraws_empty_balance(self, _):
        two_days_ago = self.now - datetime.timedelta(days=2)
        self.create_bank_deposit(user_id=201, amount=2_000_000_0, created_at=two_days_ago.replace(hour=6))
        self.create_coin_deposit(
            user_id=202,
            amount='20',
            currency=Currencies.usdt,
            rial_value=1_030_000_0,
            created_at=two_days_ago.replace(hour=8),
        )
        self.set_market_prices(
            {
                Currencies.btc: 1_280_000_000_0,
                Currencies.usdt: 52_000_0,
                Currencies.doge: 2_900_0,
            },
            two_days_ago.date(),
        )
        DailyPortfolioGenerator(report_date=two_days_ago.date(), is_first=True).create_users_profits()

        day_ago = self.now - datetime.timedelta(days=1)
        self.create_withdraw(
            user_id=201,
            amount='1_999_000_0',
            currency=Currencies.rls,
            rial_value=1_999_000_0,
            created_at=day_ago.replace(hour=7),
        )
        self.create_withdraw(
            user_id=202,
            amount='20',
            currency=Currencies.usdt,
            rial_value=996_000_0,
            created_at=day_ago.replace(hour=9),
        )
        DailyPortfolioGenerator(report_date=day_ago.date()).create_users_profits()
        profits = UserTotalDailyProfit.objects.all().order_by('report_date', 'user_id')
        assert len(profits) == 4
        for profit in profits[:2]:
            assert profit.total_deposit == 0
            assert profit.total_withdraw == 0
            assert profit.profit == 0
            assert profit.profit_percentage == 0
            assert profit.report_date == two_days_ago.date()
        for profit in profits[2:]:
            assert profit.total_deposit == 0
            assert profit.total_balance == 0
            assert profit.report_date == day_ago.date()
        assert profits[0].user_id == profits[2].user_id == 201
        assert profits[0].total_balance == 1_999_000_0
        assert profits[2].total_withdraw == 1_999_000_0
        assert profits[2].profit == 0
        assert profits[2].profit_percentage == 0
        assert profits[1].total_balance == 1_040_000_0
        assert profits[3].total_withdraw == 996_000_0
        assert profits[3].profit == -44_000_0
        assert profits[3].profit_percentage == Decimal('-4.2307692308')

        DailyPortfolioGenerator(report_date=self.now.date()).create_users_profits()
        profits = UserTotalDailyProfit.objects.all().order_by('report_date', 'user_id')
        assert len(profits) == 4

    def test_create_daily_profits_with_balance_changes_after_midnight(self, _):
        two_days_ago = self.now - datetime.timedelta(days=2)
        self.create_shetab_deposit(user_id=201, amount=2_000_000_0, created_at=two_days_ago.replace(hour=6))
        self.create_bank_deposit(user_id=202, amount=3_000_000_0, created_at=two_days_ago.replace(hour=8))
        self.set_market_prices(
            {
                Currencies.btc: 1_270_000_000_0,
                Currencies.usdt: 51_000_0,
                Currencies.doge: 3_100_0,
            },
            two_days_ago.date(),
        )
        DailyPortfolioGenerator(report_date=two_days_ago.date(), is_first=True).create_users_profits()

        day_ago = self.now - datetime.timedelta(days=1)
        self.create_bank_deposit(user_id=201, amount=2_000_000_0, created_at=day_ago.replace(hour=22))
        self.create_coin_deposit(
            user_id=201,
            amount='0.001',
            currency=Currencies.btc,
            rial_value=1_270_000_0,
            created_at=self.now.replace(hour=0),
        )
        self.create_withdraw(
            user_id=202,
            amount='500_000_0',
            currency=Currencies.rls,
            rial_value=500_000_0,
            created_at=self.now.replace(hour=0),
        )
        self.set_market_prices(
            {
                Currencies.btc: 1_280_000_000_0,
                Currencies.usdt: 52_000_0,
                Currencies.doge: 2_900_0,
            },
            day_ago.date(),
        )
        DailyPortfolioGenerator(report_date=day_ago.date()).create_users_profits()

        self.create_shetab_deposit(user_id=203, amount=1_000_000_0, created_at=self.now.replace(hour=7))
        DailyPortfolioGenerator(report_date=self.now.date()).create_users_profits()
        profits = UserTotalDailyProfit.objects.all().order_by('report_date', 'user_id')
        assert len(profits) == 7
        for profit in profits[:2] + [profits[3]]:
            assert profit.total_withdraw == 0
            assert profit.profit == 0
            assert profit.profit_percentage == 0
        # User 1: deposit after midnight
        assert profits[0].user_id == profits[2].user_id == profits[4].user_id == 201
        assert profits[0].total_balance == 1_999_000_0
        assert profits[2].total_balance == 3_998_000_0
        assert profits[2].total_deposit == 2_000_000_0
        assert profits[2].total_withdraw == 0
        assert profits[2].profit == -1_000_0
        assert profits[4].total_balance == 5_248_000_0
        assert profits[4].total_deposit == 1_270_000_0
        assert profits[4].total_withdraw == 0
        assert profits[4].profit == -20_000_0
        # User 2: withdraw after midnight
        assert profits[1].user_id == profits[3].user_id == profits[5].user_id == 202
        assert profits[1].total_balance == 2_999_000_0
        assert profits[3].total_balance == 2_999_000_0
        assert profits[3].total_deposit == 0
        assert profits[3].total_withdraw == 0
        assert profits[3].profit == profits[3].profit_percentage == 0
        assert profits[5].total_balance == 2_499_000_0
        assert profits[5].total_deposit == 0
        assert profits[5].total_withdraw == 500_000_0
        assert profits[5].profit == profits[3].profit_percentage == 0

    def test_create_daily_profits_on_trade(self, _):
        day_ago = self.now - datetime.timedelta(days=1)
        self.create_bank_deposit(user_id=201, amount=1_300_000_0, created_at=day_ago.replace(hour=6))
        self.create_coin_deposit(
            user_id=203,
            amount='0.001',
            currency=Currencies.btc,
            rial_value=1_220_000_0,
            created_at=day_ago.replace(hour=8),
        )
        self.create_coin_deposit(
            user_id=202,
            amount='30',
            currency=Currencies.usdt,
            rial_value=1_530_000_0,
            created_at=day_ago.replace(hour=10),
        )
        self.set_market_prices(
            {
                Currencies.btc: 1_230_000_000_0,
                Currencies.usdt: 52_000_0,
                Currencies.doge: 2_900_0,
            },
            day_ago.date(),
        )
        DailyPortfolioGenerator(report_date=day_ago.date(), is_first=True).create_users_profits()

        self.create_trade(
            seller_id=203,
            buyer_id=201,
            src=Currencies.btc,
            dst=Currencies.rls,
            amount='0.0005',
            price='1_230_000_000_0',
            created_at=self.now.replace(hour=7),
        )
        self.create_trade(
            seller_id=203,
            buyer_id=202,
            src=Currencies.btc,
            dst=Currencies.usdt,
            amount='0.0005',
            price='25_000',
            created_at=self.now.replace(hour=9),
        )
        self.create_trade(
            seller_id=202,
            buyer_id=201,
            src=Currencies.usdt,
            dst=Currencies.rls,
            amount='11.5',
            price='51_000_0',
            created_at=self.now.replace(hour=11),
        )
        DailyPortfolioGenerator(report_date=self.now.date()).create_users_profits()
        profits = UserTotalDailyProfit.objects.all().order_by('report_date', 'user_id')
        assert len(profits) == 6
        for profit in profits[:3]:
            assert profit.total_withdraw == 0
            assert profit.profit == profit.profit_percentage == 0
            assert profit.report_date < self.now.date()
        for i, profit in enumerate(profits[3:], start=201):
            assert profit.total_deposit == 0
            assert profit.total_withdraw == 0
            assert profit.report_date == self.now.date()
            assert profit.user_id == i
        assert profits[0].total_balance == 1_299_000_0
        assert profits[3].total_balance == 1_295_100_0
        assert profits[3].profit == -3_900_0
        assert profits[3].profit_percentage == Decimal('-0.3002309469')
        assert profits[1].total_balance == 1_560_000_0
        assert profits[4].total_balance == 1_509_077_0
        assert profits[4].profit == -50_923_0
        assert profits[4].profit_percentage == Decimal('-3.2642948718')
        assert profits[2].total_balance == 1_230_000_0
        assert profits[5].total_balance == 1_237_520_0
        assert profits[5].profit == 7_520_0
        assert profits[5].profit_percentage == Decimal('0.6113821138')

    def test_delete_old_daily_profit(self, _):
        User.objects.filter(pk=201).update(user_type=User.USER_TYPES.trader)
        User.objects.filter(pk=202).update(user_type=User.USER_TYPES.verified)

        initial_profits = [
            UserTotalDailyProfit.objects.create(
                user_id=user_id,
                report_date=self.now - datetime.timedelta(days=days_ago),
                total_balance=30_000_000_0,
                profit=0,
                profit_percentage=0,
            )
            for user_id in (201, 202)
            for days_ago in (91, 90, 33, 32, 1)
        ]

        delete_old_daily_user_profit()
        profits = UserTotalDailyProfit.objects.order_by('id')
        assert len(profits) == 6
        deleted_profits = initial_profits[:3] + initial_profits[5:6]
        for profit in profits:
            assert profit in initial_profits
            assert profit not in deleted_profits

    @patch('exchange.portfolio.services.XCHANGE_CURRENCIES', [Currencies.flr, Currencies.bigtime])
    @freeze_time(f'{today} 00:00:00', tz_offset=utcoffset)
    def test_xchange_only_coins(self, _):
        two_days_ago = self.now - datetime.timedelta(days=2)
        day_ago = self.now - datetime.timedelta(days=1)

        # Testing portfolio with no xchange prices
        self.set_market_prices(
            {
                Currencies.btc: 1_280_000_000_0,
                Currencies.usdt: 52_000_0,
            },
            two_days_ago.date(),
        )
        self.create_shetab_deposit(user_id=201, amount=2_000_000_0, created_at=two_days_ago.replace(hour=6))
        self.create_bank_deposit(user_id=201, amount=10_000_000_0, created_at=two_days_ago.replace(hour=14))
        self.create_bank_deposit(user_id=202, amount=3_000_000_0, created_at=two_days_ago.replace(hour=8))
        self.create_coin_deposit(
            user_id=202,
            amount='100',
            currency=Currencies.bigtime,
            rial_value=20_000_0,
            created_at=two_days_ago.replace(hour=10),
        )
        self.create_coin_deposit(
            user_id=203,
            amount='120',
            currency=Currencies.flr,
            rial_value=1_500_0,
            created_at=two_days_ago.replace(hour=12),
        )
        self.create_coin_deposit(
            user_id=203,
            amount='10',
            currency=Currencies.usdt,
            rial_value=500_000_0,
            created_at=two_days_ago.replace(hour=16),
        )
        DailyPortfolioGenerator(report_date=two_days_ago.date(), is_first=True).create_users_profits()
        profits = UserTotalDailyProfit.objects.all().order_by('report_date', 'user_id')
        assert len(profits) == 3
        for i, profit in enumerate(profits, start=201):
            assert profit.total_deposit == 0
            assert profit.total_withdraw == 0
            assert profit.profit == 0
            assert profit.profit_percentage == 0
            assert profit.report_date == two_days_ago.date()
            assert profit.user_id == i
        assert profits[0].total_balance == 11_998_000_0
        assert profits[1].total_balance == 2_999_000_0  # Value of Currencies.bigtime == 0 for not having a market
        assert profits[2].total_balance == 520_000_0  # Value of Currencies.flr == 0 for not having a market

        # Testing portfolio with xchange prices for xchange-only coins
        self.create_xchange_market_price(
            [
                (Currencies.bigtime, Currencies.rls, Decimal(25_000_0)),
                (Currencies.bigtime, Currencies.usdt, Decimal('0.5')),
                (Currencies.flr, Currencies.usdt, Decimal('0.05')),
            ]
        )
        self.set_market_prices(
            {
                Currencies.btc: 1_260_000_000_0,
                Currencies.usdt: 52_000_0,
            },
            day_ago.date(),
        )
        DailyPortfolioGenerator(report_date=day_ago.date()).create_users_profits()
        profits = list(UserTotalDailyProfit.objects.all().order_by('report_date', 'user_id'))
        assert len(profits) == 6
        for i, profit in enumerate(profits[3:], start=201):
            assert profit.total_deposit == 0
            assert profit.total_withdraw == 0
            assert profit.report_date == day_ago.date()
            assert profit.user_id == i
        assert profits[3].total_balance == 11_998_000_0
        assert profits[3].profit == 0
        assert profits[3].profit_percentage == 0
        assert profits[4].total_balance == 2_999_000_0 + 100 * 25_000_0
        assert profits[4].profit == 100 * 25_000_0  # For bigtime's rls price
        assert profits[4].profit_percentage == Decimal('83.3611203735')
        assert profits[5].total_balance == 520_000_0 + 120 * Decimal('0.05') * 52_000_0
        assert profits[5].profit == 120 * Decimal('0.05') * 52_000_0  # For flr's usdt price
        assert profits[5].profit_percentage == Decimal('60.0000000000')

        # Testing portfolio with deposits, withdraws, and trades for xchange-only coins
        self.create_coin_deposit(
            user_id=201,
            amount='10',
            currency=Currencies.bigtime,
            rial_value=240_000_0,
            created_at=self.now.replace(hour=5),
        )
        self.create_withdraw(
            user_id=202,
            amount='50',
            currency=Currencies.bigtime,
            rial_value=1_200_000_0,
            created_at=self.now.replace(hour=8),
        )
        self.create_xchange_trade(
            user_id=203,
            xchange_user_id=204,
            src_currency=Currencies.flr,
            dst_currency=Currencies.usdt,
            src_amount=Decimal(100),
            dst_amount=Decimal(5),
        )
        self.create_xchange_market_price(
            [
                (Currencies.bigtime, Currencies.rls, Decimal(25_500_0)),
                (Currencies.bigtime, Currencies.usdt, Decimal('0.5')),
                (Currencies.flr, Currencies.usdt, Decimal('0.06')),
            ]
        )
        DailyPortfolioGenerator(report_date=self.now.date()).create_users_profits()
        profits = list(UserTotalDailyProfit.objects.all().order_by('report_date', 'user_id'))
        assert len(profits) == 9
        for i, profit in enumerate(profits[6:], start=201):
            assert profit.report_date == self.now.date()
            assert profit.user_id == i
        assert profits[6].total_balance == 11_998_000_0 + 10 * 25_500_0
        assert profits[6].profit == 10 * 25_500_0 - 240_000_0  # for bigtime's value change after deposit
        assert profits[6].profit_percentage == Decimal('0.1225690472')
        assert profits[6].total_deposit == 240_000_0
        assert profits[6].total_withdraw == 0
        assert profits[7].total_balance == 2_999_000_0 + 50 * 25_500_0
        assert profits[7].profit == -50 * 500_0  # For change in bigtime's rls price
        assert profits[7].profit_percentage == Decimal('-0.4546281142')
        assert profits[7].total_deposit == 0
        assert profits[7].total_withdraw == 1_200_000_0
        assert profits[8].total_balance == 20 * Decimal('0.06') * 50_000_0 + 15 * 50_000_0
        assert profits[8].profit == -22_000_0  # For change in flr's usdt price and usdt price to rls
        assert profits[8].profit_percentage == Decimal('-2.6442307692')
        assert profits[8].total_deposit == 0
        assert profits[8].total_withdraw == 0


class MonthlyPortfolioTest(TestCase):
    now: datetime.datetime

    @classmethod
    def setUpTestData(cls):
        User.objects.filter(id__in=(201, 202, 203)).update(track=QueueItem.BIT_FLAG_PORTFOLIO)
        cls.now = ir_now()

    def test_create_monthly_profits_no_daily_profits(self):
        MonthlyPortfolioGenerator(report_date=self.now.date()).create_users_profits()
        profits = UserTotalMonthlyProfit.objects.all().order_by('report_date', 'user_id')
        assert len(profits) == 0

    def test_create_monthly_profits_one_daily_profits(self):
        UserTotalDailyProfit.objects.create(
            user_id=201,
            report_date=self.now.date(),
            total_balance=1_200_000_0,
            profit=0,
            profit_percentage=0,
            total_deposit=500_000_0,
        )
        UserTotalDailyProfit.objects.create(
            user_id=202,
            report_date=self.now.date(),
            total_balance=3_700_000_0,
            profit=0,
            profit_percentage=0,
            total_withdraw=1_300_000_0,
        )
        UserTotalDailyProfit.objects.create(
            user_id=203,
            report_date=self.now.date(),
            total_balance=2_400_000_0,
            profit=0,
            profit_percentage=0,
        )
        MonthlyPortfolioGenerator(report_date=self.now.date()).create_users_profits()
        profits = UserTotalMonthlyProfit.objects.all().order_by('report_date', 'user_id')
        assert len(profits) == 3
        for profit in profits:
            assert profit.total_profit == profit.total_profit_percentage == 0
            assert profit.report_date <= self.now.date()
        assert profits[0].first_day_total_balance == 700_000_0
        assert profits[0].total_balance == 1_200_000_0
        assert profits[0].total_deposit == 500_000_0
        assert profits[0].total_withdraw == 0
        assert profits[1].first_day_total_balance == 5_000_000_0
        assert profits[1].total_balance == 3_700_000_0
        assert profits[1].total_deposit == 0
        assert profits[1].total_withdraw == 1_300_000_0
        assert profits[2].first_day_total_balance == 2_400_000_0
        assert profits[2].total_balance == 2_400_000_0
        assert profits[2].total_deposit == 0
        assert profits[2].total_withdraw == 0

    def test_create_monthly_profits_multi_daily_profits(self):
        first_day, last_day = get_first_and_last_of_jalali_month(self.now)

        UserTotalDailyProfit.objects.create(
            user_id=201,
            report_date=last_day - datetime.timedelta(days=3),
            total_balance=1_200_000_0,
            profit=0,
            profit_percentage=0,
            total_deposit=500_000_0,
        )
        UserTotalDailyProfit.objects.create(
            user_id=201,
            report_date=last_day - datetime.timedelta(days=2),
            total_balance=900_000_0,
            profit=50_000_0,
            profit_percentage='4.17',
            total_withdraw=350_000_0,
        )
        UserTotalDailyProfit.objects.create(
            user_id=201,
            report_date=last_day - datetime.timedelta(days=1),
            total_balance=1_690_000_0,
            profit=-10_000_0,
            profit_percentage='5.88',
            total_deposit=800_000_0,
        )
        UserTotalDailyProfit.objects.create(
            user_id=201,
            report_date=last_day,
            total_balance=1_780_000_0,
            profit=90_000_0,
            profit_percentage='5.32',
        )

        UserTotalDailyProfit.objects.create(
            user_id=202,
            report_date=first_day - datetime.timedelta(days=1),
            total_balance=3_700_000_0,
            profit=0,
            profit_percentage=0,
            total_withdraw=1_300_000_0,
        )
        for i in range((last_day - first_day).days - 2):
            profit = 100_000_0 if i < 20 else 0
            UserTotalDailyProfit.objects.create(
                user_id=202,
                report_date=first_day + datetime.timedelta(days=i),
                total_balance=3_700_000_0,
                profit=profit,
                total_withdraw=profit,
                profit_percentage='2.7',
            )
        UserTotalDailyProfit.objects.create(
            user_id=202,
            report_date=last_day - datetime.timedelta(days=1),
            total_balance=4_600_000_0,
            profit=-100_000_0,
            profit_percentage='-2.78',
            total_deposit=1_000_000_0,
        )
        UserTotalDailyProfit.objects.create(
            user_id=202,
            report_date=last_day,
            total_balance=4_800_000_0,
            profit=100_000_0,
            profit_percentage='2.78',
        )

        MonthlyPortfolioGenerator(report_date=last_day).create_users_profits()
        profits = UserTotalMonthlyProfit.objects.all().order_by('report_date', 'user_id')
        assert len(profits) == 2
        for profit in profits:
            assert profit.report_date == first_day
        assert profits[0].first_day_total_balance == 700_000_0
        assert profits[0].total_balance == 1_780_000_0
        assert profits[0].total_deposit == 1_300_000_0
        assert profits[0].total_withdraw == 350_000_0
        assert profits[0].total_profit == 130_000_0
        assert profits[0].total_profit_percentage == Decimal('6.5')
        assert profits[1].first_day_total_balance == 3_700_000_0
        assert profits[1].total_balance == 4_800_000_0
        assert profits[1].total_deposit == 1_000_000_0
        assert profits[1].total_withdraw == 2_000_000_0
        assert profits[1].total_profit == 2_100_000_0
        assert profits[1].total_profit_percentage == Decimal('44.6808510638')
