import datetime
from collections import defaultdict
from decimal import Decimal
from itertools import chain
from typing import Dict, List, Optional, Tuple, Type

from django.conf import settings
from django.db import connection
from django.db.models import Case, DecimalField, F, Model, Q, Sum, When, Window
from django.db.models.functions import Coalesce, FirstValue
from django.utils import timezone
from django.utils.functional import cached_property

from exchange.accounts.models import User
from exchange.base.calendar import get_earliest_time, get_first_and_last_of_jalali_month, get_latest_time, ir_today
from exchange.base.constants import MAX_32_INT, MIN_32_INT, ZERO
from exchange.base.decorators import measure_time, measure_time_cm
from exchange.base.helpers import batcher
from exchange.base.models import XCHANGE_CURRENCIES, Currencies
from exchange.corporate_banking.models import CoBankUserDeposit
from exchange.direct_debit.models import DirectDeposit
from exchange.features.models import QueueItem
from exchange.market.models import MarketCandle
from exchange.portfolio.models import UserTotalDailyProfit, UserTotalMonthlyProfit
from exchange.shetab.models import ShetabDeposit
from exchange.wallet.models import BankDeposit, ConfirmedWalletDeposit, Transaction, WithdrawRequest
from exchange.xchange.models import MarketStatus


class Portfolio:
    def __init__(
        self,
        user_id: int,
        initial_balance: Decimal,
        final_balance: Decimal,
        total_deposit: Decimal,
        total_withdraw: Decimal,
    ):
        self.user_id = user_id
        self.initial_balance = initial_balance
        self.final_balance = final_balance
        self.total_deposit = total_deposit
        self.total_withdraw = total_withdraw

    @cached_property
    def cost(self) -> Optional[Decimal]:
        return self.initial_balance + self.total_deposit

    @cached_property
    def revenue(self) -> Optional[Decimal]:
        return self.final_balance + self.total_withdraw

    @cached_property
    def profit(self) -> Decimal:
        if not self.cost:
            return Decimal(0)
        return self.revenue - self.cost

    @cached_property
    def profit_percent(self) -> Decimal:
        if not self.cost:
            return Decimal(0)
        return min(self.profit / self.cost * 100, Decimal(10_000))


class BasePortfolioGenerator:
    profit_model: Type[Model]
    batch_size: int

    def __init__(self, report_date: datetime.date, user_ids: Optional[tuple] = None):
        self.from_date, self.to_date = self.get_date_range(report_date)
        self.user_ids = user_ids or tuple(self.get_enabled_user_ids())

    @staticmethod
    def get_date_range(report_date: datetime.date) -> Tuple[datetime.date, datetime.date]:
        raise NotImplementedError()

    @staticmethod
    def get_enabled_user_ids():
        enabled_users = User.objects.annotate(
            active_profile=F('track').bitand(QueueItem.BIT_FLAG_PORTFOLIO),
        ).filter(active_profile=QueueItem.BIT_FLAG_PORTFOLIO)
        if settings.IS_TESTNET:
            enabled_users |= User.objects.filter(
                user_type__gte=User.USER_TYPES.level2, user_type__lt=User.USER_TYPES.nobitex
            )
        return enabled_users.order_by('id').values_list('id', flat=True)

    def create_users_profits(self):
        for batch_user_ids in batcher(self.user_ids, self.batch_size):
            portfolios = self.get_batch_portfolios(batch_user_ids)
            profits = [self.get_profit_record(portfolio=portfolio) for portfolio in portfolios]
            with measure_time_cm(metric=f'portfolio_save_milliseconds__{self.batch_size}', verbose=False):
                self.profit_model.objects.bulk_create(profits, batch_size=100, ignore_conflicts=True)

    def get_batch_portfolios(self, user_ids: List[int]) -> List[Portfolio]:
        raise NotImplementedError()

    def get_profit_record(self, portfolio: Portfolio) -> Model:
        raise NotImplementedError()


class DailyPortfolioGenerator(BasePortfolioGenerator):
    profit_model = UserTotalDailyProfit
    batch_size = 1000

    def __init__(self, report_date: datetime.date, user_ids: Optional[tuple] = None, *, is_first: bool = False):
        self.is_first = is_first
        super().__init__(report_date, user_ids)
        self.from_time = get_earliest_time(self.from_date)
        self.to_time = get_latest_time(self.to_date)
        self.from_trx_id = self.get_first_transaction_id(self.from_time)
        self.currency_rial_values = self.get_currency_rial_values()

    def get_enabled_user_ids(self):
        user_ids = super().get_enabled_user_ids()
        if self.is_first:
            user_ids = user_ids.filter(daily_profits__isnull=True)
        return user_ids

    @staticmethod
    def get_first_transaction_id(from_time: datetime.datetime, transaction_safety_margin=1000):
        first_transaction = Transaction.objects.filter(created_at__gte=from_time).order_by('created_at').first()
        if not first_transaction:
            return 1
        if first_transaction.id < MIN_32_INT + transaction_safety_margin:
            return MAX_32_INT - transaction_safety_margin
        return first_transaction.id - transaction_safety_margin

    @staticmethod
    def get_date_range(report_date: datetime.date) -> Tuple[datetime.date, datetime.date]:
        return report_date, report_date

    def get_currency_rial_values(self) -> Dict[int, Decimal]:
        rial_values = {Currencies.rls: Decimal(1)}
        last_day_candles = MarketCandle.objects.filter(
            resolution=MarketCandle.RESOLUTIONS.day,
            start_time__date=self.to_date,
        ).values_list('market__src_currency', 'close_price')
        rls_prices = last_day_candles.filter(market__dst_currency=Currencies.rls)
        for currency, rial_value in rls_prices:
            rial_values[currency] = rial_value
        if Currencies.usdt in rls_prices:
            # For currencies such as PMN,
            usdt_only_prices = last_day_candles.exclude(market__src_currency__in=rial_values).filter(
                market__dst_currency=Currencies.usdt,
            )
            for currency, usdt_value in usdt_only_prices:
                rial_values[currency] = usdt_value * rial_values[Currencies.usdt]

        # For xchange_only currencies
        xchange_pairs_prices = MarketStatus.objects.filter(base_currency__in=XCHANGE_CURRENCIES).values_list(
            'base_currency', 'quote_currency', 'base_to_quote_price_sell'
        )
        pairs_prices_dict = {
            (base_currency, quote_currency): base_to_quote_price_sell
            for base_currency, quote_currency, base_to_quote_price_sell in xchange_pairs_prices
        }
        for currency_pair, price in pairs_prices_dict.items():
            if currency_pair[1] == Currencies.rls:
                rial_values[currency_pair[0]] = price
            elif currency_pair[1] == Currencies.usdt and (currency_pair[0], Currencies.rls) not in pairs_prices_dict:
                rial_values[currency_pair[0]] = price * rial_values[Currencies.usdt]

        return rial_values

    def get_batch_portfolios(self, batch_user_ids: Tuple[int, ...]) -> List[Portfolio]:
        final_balances = self.get_final_balances(batch_user_ids)
        if self.is_first:
            initial_balances = total_deposits = total_withdraws = {}
        else:
            initial_balances = self.get_initial_balances(batch_user_ids)
            total_deposits = self.get_total_deposits(batch_user_ids)
            total_withdraws = self.get_total_withdraws(batch_user_ids)

        user_ids = set(final_balances) | set(total_deposits) | set(total_withdraws)

        return [
            Portfolio(
                user_id=user_id,
                initial_balance=initial_balances.get(user_id, ZERO),
                final_balance=final_balances.get(user_id, ZERO),
                total_deposit=total_deposits.get(user_id, ZERO),
                total_withdraw=total_withdraws.get(user_id, ZERO),
            )
            for user_id in user_ids
        ]

    @measure_time(metric='portfolio_daily_initial_balances_milliseconds', verbose=False)
    def get_initial_balances(self, user_ids: Tuple[int, ...]) -> Dict[int, Decimal]:
        last_balances = UserTotalDailyProfit.objects.filter(
            user_id__gte=user_ids[0],
            user_id__lte=user_ids[-1],
            report_date=self.from_date - datetime.timedelta(days=1),
        ).values('user_id', 'total_balance')
        return {r['user_id']: max(r['total_balance'], Decimal(0)) for r in last_balances}

    @measure_time(metric='portfolio_daily_final_balances_milliseconds', verbose=False)
    def get_final_balances(self, batch_user_ids: Tuple[int, ...]) -> Dict[int, Decimal]:
        wallet_balances = self.get_wallet_balances(batch_user_ids)
        total_pool_balances = self.get_total_pool_balances(batch_user_ids)
        total_external_earning_balances = self.get_external_earning_balances(batch_user_ids)

        user_ids = set(wallet_balances) | set(total_pool_balances) | set(total_external_earning_balances)
        return {
            user_id: (
                wallet_balances.get(user_id, ZERO)
                + total_pool_balances.get(user_id, ZERO)
                + total_external_earning_balances.get(user_id, ZERO)
            )
            for user_id in user_ids
        }

    @measure_time(metric='portfolio_daily_wallet_balances_milliseconds', verbose=False)
    def get_wallet_balances(self, user_ids: Tuple[int, ...]) -> Dict[int, Decimal]:
        rial_value_cases = ' '.join(
            [
                f'WHEN currency = {currency} THEN final_balance * {rial_value}'
                for currency, rial_value in self.currency_rial_values.items()
            ]
        )
        if self.from_trx_id < 0:
            transaction_id_where_clause = f'wallet_transaction.id >= {self.from_trx_id} AND wallet_transaction.id < 0'
        else:
            transaction_id_where_clause = f'''(
                (wallet_transaction.id < 0 or wallet_transaction.id >= {self.from_trx_id})
            )'''
        with connection.cursor() as cursor:
            cursor.execute(
                f'''
            WITH wallet_balances AS (
                SELECT user_id, currency, (balance - COALESCE(SUM(amount), 0)) AS final_balance
                FROM wallet_wallet LEFT OUTER JOIN (
                    select wallet_id, amount from wallet_transaction
                    where (
                        {transaction_id_where_clause} AND
                        wallet_transaction.created_at > %(to_time)s
                    )
                ) AS U0 ON (wallet_wallet.id = U0.wallet_id)
                WHERE user_id IN %(user_ids)s
                GROUP BY user_id, currency, balance
            )
            SELECT user_id, SUM(CASE {rial_value_cases} ELSE 0 END) AS total_balance
            FROM wallet_balances
            GROUP BY user_id
            HAVING SUM(CASE {rial_value_cases} ELSE 0 END) > 0
            ''',
                {
                    'to_time': self.to_time,
                    'user_ids': user_ids,
                },
            )
            return dict(cursor.fetchall())

    @measure_time(metric='portfolio_daily_total_deposits_milliseconds', verbose=False)
    def get_total_deposits(self, user_ids: Tuple[int, ...]) -> Dict[int, Decimal]:
        if self.from_trx_id < 0:
            transaction_id_queryset = Q(transaction_id__gte=self.from_trx_id, transaction_id__lt=0)
        else:
            transaction_id_queryset = Q(transaction_id__lt=0) | Q(transaction_id__gte=self.from_trx_id)
        transaction_filters = dict(
            transaction__created_at__gte=self.from_time,
            transaction__created_at__lte=self.to_time,
        )
        confirmed_wallet_deposits = (
            ConfirmedWalletDeposit.objects.filter(
                transaction_id_queryset,
                _wallet__user_id__in=user_ids,
                confirmed=True,
                validated=True,
                **transaction_filters,
            )
            .values('_wallet__user')
            .annotate(sum=Sum('rial_value'))
            .values_list('_wallet__user', 'sum')
        )
        shetab_deposits = (
            ShetabDeposit.objects.filter(
                transaction_id_queryset,
                user_id__in=user_ids,
                status_code=ShetabDeposit.STATUS.pay_success,
                **transaction_filters,
            )
            .values('user')
            .annotate(sum=Sum('amount'))
            .values_list('user', 'sum')
        )
        bank_deposits = (
            BankDeposit.objects.filter(
                transaction_id_queryset,
                user_id__in=user_ids,
                confirmed=True,
                status=BankDeposit.STATUS.confirmed,
                **transaction_filters,
            )
            .values('user')
            .annotate(sum=Sum('amount'))
            .values_list('user', 'sum')
        )
        direct_deposits = (
            DirectDeposit.objects.filter(
                transaction_id_queryset,
                contract__user_id__in=user_ids,
                status=DirectDeposit.STATUS.succeed,
                **transaction_filters,
            )
            .values('contract__user')
            .annotate(sum=Sum('amount'))
            .values_list('contract__user', 'sum')
        )
        cobank_deposits = (
            CoBankUserDeposit.objects.filter(
                transaction_id_queryset,
                user_id__in=user_ids,
                **transaction_filters,
            )
            .values('user')
            .annotate(sum=Sum('amount'))
            .values_list('user', 'sum')
        )

        total_deposits = defaultdict(Decimal)
        for user_id, partial_deposit in chain(
            confirmed_wallet_deposits,
            shetab_deposits,
            bank_deposits,
            direct_deposits,
            cobank_deposits,
        ):
            partial_deposit = partial_deposit if partial_deposit else Decimal('0')
            total_deposits[user_id] += partial_deposit
        return total_deposits

    @measure_time(metric='portfolio_daily_total_withdraws_milliseconds', verbose=False)
    def get_total_withdraws(self, user_ids: Tuple[int, ...]) -> Dict[int, Decimal]:
        if self.from_trx_id < 0:
            transaction_id_queryset = Q(transaction_id__gte=self.from_trx_id, transaction_id__lt=0)
        else:
            transaction_id_queryset = Q(transaction_id__lt=0) | Q(transaction_id__gte=self.from_trx_id)
        transaction_filters = dict(
            transaction__created_at__gte=self.from_time,
            transaction__created_at__lte=self.to_time,
        )
        withdraws = (
            WithdrawRequest.objects.filter(transaction_id_queryset, wallet__user_id__in=user_ids, **transaction_filters)
            .exclude(
                status__in=WithdrawRequest.STATUSES_INACTIVE,
            )
            .values('wallet__user')
            .annotate(sum=Sum('rial_value'))
        )
        return {r['wallet__user']: r['sum'] or Decimal(0) for r in withdraws}

    @measure_time(metric='portfolio_daily_total_pool_balances_milliseconds', verbose=False)
    def get_total_pool_balances(self, user_ids: Tuple[int, ...]) -> Dict[int, Decimal]:
        rial_value_cases = ' '.join(
            [
                f'WHEN currency = {currency} THEN final_balance * {rial_value}'
                for currency, rial_value in self.currency_rial_values.items()
            ]
        )
        with connection.cursor() as cursor:
            cursor.execute(
                f'''
            WITH pool_balances AS (
                SELECT ud.user_id, lp.currency, (ud.balance - COALESCE(SUM(U0.amount), 0)) AS final_balance
                FROM pool_userdelegation ud
                JOIN pool_liquiditypool lp on lp.id = ud.pool_id
                LEFT OUTER JOIN (
                    SELECT user_delegation_id, amount from pool_delegationtransaction
                    WHERE (pool_delegationtransaction.created_at AT TIME ZONE 'Asia/Tehran')::date > %(to_date)s
                ) AS U0 ON (ud.id = U0.user_delegation_id)
                WHERE user_id IN %(user_ids)s AND (ud.closed_at IS NULL OR (ud.closed_at AT TIME ZONE 'Asia/Tehran')::date >= %(to_date)s)
                GROUP BY user_id, currency, balance
            )
            SELECT user_id, SUM(CASE {rial_value_cases} ELSE 0 END) AS total_balance
            FROM pool_balances
            WHERE final_balance > 0
            GROUP BY user_id
            ''',
                {
                    'to_date': self.to_date,
                    'user_ids': user_ids,
                },
            )
            return dict(cursor.fetchall())

    @measure_time(metric='portfolio_daily_total_external_earning_balances_milliseconds', verbose=False)
    def get_external_earning_balances(
        self,
        user_ids: Tuple[int, ...],
    ) -> Dict[int, Decimal]:

        rial_value_cases = ' '.join(
            [
                f'WHEN w.currency = {currency} THEN t.amount * {-rate}'
                for currency, rate in self.currency_rial_values.items()
            ],
        )
        with connection.cursor() as cursor:
            cursor.execute(
                f'''
                WITH transaction_cte AS (
                    SELECT
                        wallet_id,
                        amount
                    FROM wallet_transaction
                    WHERE (created_at AT TIME ZONE 'Asia/Tehran')::date <= %(to_date)s
                        AND id IN (
                            SELECT wallet_transaction_id
                            FROM staking_stakingtransaction
                            WHERE user_id IN %(user_ids)s
                                AND tp != 302
                        )
                )
                SELECT
                    w.user_id,
                    SUM(CASE {rial_value_cases} ELSE 0 END) AS total_balance
                FROM transaction_cte t
                JOIN wallet_wallet w ON t.wallet_id = w.id
                GROUP BY w.user_id;
                ''',
                {
                    'to_date': self.to_date,
                    'user_ids': user_ids,
                },
            )
            return dict(cursor.fetchall())

    def get_profit_record(self, portfolio: Portfolio) -> profit_model:
        return self.profit_model(
            report_date=self.from_date,
            user_id=portfolio.user_id,
            total_balance=portfolio.final_balance,
            profit=portfolio.profit,
            profit_percentage=portfolio.profit_percent,
            total_withdraw=portfolio.total_withdraw,
            total_deposit=portfolio.total_deposit,
        )


class MonthlyPortfolioGenerator(BasePortfolioGenerator):
    profit_model = UserTotalMonthlyProfit
    batch_size = 10000

    @staticmethod
    def get_date_range(report_date: datetime.date) -> Tuple[datetime.date, datetime.date]:
        return get_first_and_last_of_jalali_month(report_date)

    @measure_time(metric='portfolio_monthly_query_milliseconds', verbose=False)
    def get_batch_portfolios(self, user_ids: List[int]) -> List[Portfolio]:
        window = dict(partition_by=F('user_id'))
        last_month_condition = Q(report_date__gte=self.from_date)
        initial_balance = Case(
            When(last_month_condition, then=F('total_balance') - F('total_deposit') + F('total_withdraw')),
            default=F('total_balance'),
            output_field=DecimalField(),
        )
        portfolios_data = (
            UserTotalDailyProfit.objects.filter(
                user_id__gte=user_ids[0],
                user_id__lte=user_ids[-1],
                report_date__range=(self.from_date - datetime.timedelta(days=1), self.to_date),
            )
            .values('user_id')
            .annotate(
                initial_balance=Window(FirstValue(initial_balance), order_by=F('report_date').asc(), **window),
                final_balance=Window(FirstValue('total_balance'), order_by=F('report_date').desc(), **window),
                total_deposit=Coalesce(Window(Sum('total_deposit', filter=last_month_condition), **window), ZERO),
                total_withdraw=Coalesce(Window(Sum('total_withdraw', filter=last_month_condition), **window), ZERO),
            )
            .distinct('user_id')
        )
        return [Portfolio(**portfolio_data) for portfolio_data in portfolios_data]

    def get_profit_record(self, portfolio: Portfolio) -> profit_model:
        return self.profit_model(
            report_date=self.from_date,
            user_id=portfolio.user_id,
            total_balance=portfolio.final_balance,
            first_day_total_balance=portfolio.initial_balance,
            total_profit=portfolio.profit,
            total_profit_percentage=portfolio.profit_percent,
            total_withdraw=portfolio.total_withdraw,
            total_deposit=portfolio.total_deposit,
        )


def enable_portfolios(user_ids: Tuple[int, ...]):
    yesterday = ir_today() - datetime.timedelta(days=1)
    User.objects.filter(id__in=user_ids).update(track=Coalesce(F('track'), 0).bitor(QueueItem.BIT_FLAG_PORTFOLIO))
    DailyPortfolioGenerator(report_date=yesterday, user_ids=user_ids, is_first=True).create_users_profits()


def delete_old_daily_user_profit():
    """
    Delete old daily profit record
    The daily profits remains for user under lvl2 32days and lvl2 and above 90days
    """
    ninety_days_ago = timezone.now() - timezone.timedelta(days=90)
    lvl_2_or_above = Q(user__user_type__gte=46, report_date__lt=ninety_days_ago)

    thirty_days_ago = timezone.now() - timezone.timedelta(days=32)
    under_lvl_2 = Q(user__user_type__lt=46, report_date__lt=thirty_days_ago)

    UserTotalDailyProfit.objects.filter(under_lvl_2 | lvl_2_or_above).delete()
