from datetime import date
from decimal import ROUND_DOWN, Decimal
from time import sleep
from typing import List, Union

from django.db import transaction
from django.db.models import Count, Exists, F, OuterRef, Q, QuerySet, Sum
from django.db.models.functions import Coalesce

from exchange.base.calendar import get_first_and_last_of_jalali_month, ir_today
from exchange.base.constants import ZERO
from exchange.base.logging import report_event
from exchange.base.models import RIAL, Currencies, Settings
from exchange.base.money import money_is_zero, quantize_number
from exchange.market.models import MarketCandle
from exchange.pool.errors import NullAmountUDPExists, PartialConversionOrderException
from exchange.pool.models import (
    DelegationTransaction,
    LiquidityPool,
    PoolProfit,
    PoolStat,
    UserDelegation,
    UserDelegationProfit,
)
from exchange.wallet.estimator import PriceEstimator


def populate_daily_profit_for_target_pools(
    from_date: date, to_date: date, target_pools: Union[List[LiquidityPool], QuerySet]
):
    today = ir_today()

    with transaction.atomic():
        # Reset
        pools_dict = {pool.id: pool for pool in target_pools}
        LiquidityPool.objects.filter(id__in=list(pools_dict.keys())).update(current_profit=ZERO)

        # Update
        updated_pools = []
        profits = PoolProfit.calc_pools_profit(target_pools, from_date, to_date)
        updated_profits = []
        for pool_id, pool_profits in profits.items():
            pool = pools_dict[pool_id]
            is_profit_date = pool.profit_date == today
            current_profit = ZERO
            for dst_currency, profit in pool_profits.items():
                if is_profit_date and dst_currency != RIAL:
                    profit.create_convert_to_rial_order()

                profit.rial_value = PriceEstimator.get_rial_value_by_best_price(
                    profit.position_profit, dst_currency, 'buy', db_fallback=True
                )
                updated_profits.append(profit)
                current_profit += profit.rial_value

            pool.current_profit = current_profit
            updated_pools.append(pool)

        PoolProfit.objects.bulk_update(updated_profits, ('rial_value',))
        LiquidityPool.objects.bulk_update(updated_pools, ('current_profit',))


def convert_target_pools_usdt_profits_to_rial(
    from_date: date, to_date: date, target_pools: Union[List[LiquidityPool], QuerySet]
):
    pool_profits = PoolProfit.objects.filter(from_date=from_date, to_date=to_date, pool__in=target_pools).exclude(
        currency=Currencies.rls
    )
    for pool_profit in pool_profits:
        pool_profit.create_convert_to_rial_order()


def populate_realized_profits_for_target_pools(from_date: date, target_pools):
    with transaction.atomic():
        pool_profits = PoolProfit.objects.filter(from_date=from_date, pool__in=target_pools)
        non_rial_pool_profits = pool_profits.exclude(currency=RIAL).prefetch_related('orders')

        updated_pool_profits = []
        for pool_profit in non_rial_pool_profits:
            profit = pool_profit.position_profit
            if profit <= 0:
                pool_profit.rial_value = ZERO
            else:
                if not money_is_zero(pool_profit.unmatched_amount):
                    report_event(f'Pool profit {pool_profit.pk} is not converted to RIAL.')
                    raise PartialConversionOrderException(pool_profit.pk)

                pool_profit.rial_value = sum(order.matched_total_price for order in pool_profit.orders.all())

            updated_pool_profits.append(pool_profit)

        PoolProfit.objects.bulk_update(updated_pool_profits, ('rial_value',))

        pool_profits = pool_profits.values('pool_id').annotate(profit=Sum('rial_value'))
        pool_dict = {pool.id: pool for pool in target_pools}
        for pool_profit in pool_profits:
            pool_dict[pool_profit['pool_id']].current_profit = pool_profit['profit']

        LiquidityPool.objects.bulk_update(pool_dict.values(), ('current_profit',))


def day_in_row_factor(days: int):
    factor = Decimal(Settings.get_value('liquidity_pool_day_in_row_factor', '0.1'))
    return 1 + factor * (min(days, 31) - 1)


def effective_days(days):
    return days * day_in_row_factor(days)


def calculate_user_score(user_delegation: UserDelegation, from_date: date, to_date: date) -> Decimal:
    """Calculate user delegation score

    Check this doc for more info: https://bitex-doc.nobitex.ir/doc/astkhr-msharkt-draft-ua4bWfNCHn

    Args:
        user_delegation (UserDelegation): UserDelegation object
        from_date (date): start date
        to_date (date): end date

    Returns:
        Decimal: User score

    Examples:

        Example 1:

            #      ^
            #      |
            # 3    + +-+
            #      | | |
            # 2    | | |     +-----------
            #      | | |     |xxxxxxxxxxx
            # 1.23 | |-+-----+ - - - - -
            #      | |yyyyyyyyyyyyyyyyyyy
            #      +-+------------------>
            #        1 2     6          10

            Returns:
                  0.77 * effective_days(4)
                + 1.23 * effective_days(9)

        --------------------------------------------

        Example 2:

            #  4    ^ +-+ +-+           +----
            #       | | | | |           |xxxx
            #  3    | | +-+ |  +--+     |xxxx
            #  2.5  | |     |  |  +-----+ - -
            #  2    | | - - +--+yyyyyyyyyyyyy
            #       | |zzzzzzzzzzzzzzzzzzzzzz
            #       +-+--------------------->
            #         1 2 3 4  5  6      8

            Returns:
                  1.5 * effective_days(2)
                + 0.5 * effective_days(5)
                + 2   * effective_days(9)
    """

    score = ZERO
    overtime_balance = DelegationTransaction.objects.filter(
        user_delegation=user_delegation,
        created_at__date__gt=to_date,
        transaction__isnull=False,
    ).aggregate(overtime_balance=Coalesce(Sum('amount'), ZERO))['overtime_balance']

    balance = user_delegation.balance - overtime_balance
    delegation_txs = DelegationTransaction.objects.filter(
        user_delegation=user_delegation,
        created_at__date__lte=to_date,
        created_at__date__gte=from_date,
        transaction__isnull=False,
    ).order_by('-created_at')

    min_balance = balance
    for tx in delegation_txs:
        balance = balance - tx.amount

        if tx.amount > 0 and balance < min_balance:
            # DANGER! DON'T DO THIS:
            # delegation_days = (to_date - tx.created_at.date()).days
            # Because tx.created_at is in utc tz but the to_date is in IR tz.
            delegation_days = (to_date - tx.created_at.astimezone().date()).days + 1
            delegation_amount = min_balance - balance
            score += delegation_amount * effective_days(delegation_days)
            min_balance = balance

        if balance <= ZERO:
            break

    min_balance_days = (to_date - max(user_delegation.created_at.astimezone().date(), from_date)).days + 1
    score += min_balance * effective_days(min_balance_days)
    if score < ZERO:
        raise ValueError('Delegation score cannot be negative')
    return score


def populate_users_delegation_score_on_target_pools(
    from_date: date, to_date: date, target_pools: Union[List[LiquidityPool], QuerySet]
) -> None:
    user_delegations = (
        UserDelegation.objects.filter(
            Q(closed_at__isnull=True) | Q(closed_at__date__gt=to_date),
            created_at__date__lte=to_date,
            pool__in=target_pools,
        )
        .annotate(
            is_already_done=Exists(
                UserDelegationProfit.objects.filter(
                    user_delegation=OuterRef('id'),
                    from_date=from_date,
                    to_date=to_date,
                )
            )
        )
        .filter(is_already_done=False)
    )

    batch_size = 1000
    total_delegations = user_delegations.count()
    num_batches = (total_delegations + batch_size - 1) // batch_size

    for _ in range(num_batches):
        batch_delegations = user_delegations[:batch_size]

        user_delegation_profits = []
        for user_delegation in batch_delegations:
            score = calculate_user_score(user_delegation, from_date, to_date)
            user_delegation_profit = UserDelegationProfit(
                user_delegation=user_delegation,
                delegation_score=score,
                from_date=from_date,
                to_date=to_date,
            )
            user_delegation_profits.append(user_delegation_profit)

        UserDelegationProfit.objects.bulk_create(user_delegation_profits, batch_size=batch_size)


def populate_users_profit_on_target_pools(from_date: date, target_pools: Union[List[LiquidityPool], QuerySet]) -> None:
    with transaction.atomic():
        delegation_profits = UserDelegationProfit.objects.filter(
            from_date=from_date, user_delegation__pool__in=target_pools
        ).annotate(pool_id=F('user_delegation__pool__id'))
        total_scores = {
            p['pool_id']: p['total_score']
            for p in delegation_profits.values('pool_id').annotate(total_score=Sum(F('delegation_score')))
        }
        pool_profits = PoolProfit.objects.filter(pool__in=target_pools)
        pool_profits = dict(
            pool_profits.filter(from_date=from_date)
            .values('pool_id')
            .annotate(current_profit=Sum('rial_value'))
            .values_list('pool_id', 'current_profit')
        )

        delegation_profits = delegation_profits.filter(amount__isnull=True)
        udps_count = delegation_profits.count()
        batch_size = 1000
        num_batches = (udps_count + batch_size - 1) // batch_size

        for _ in range(num_batches):
            batch_base = delegation_profits[:batch_size]
            batch_udps = []

            for udp in batch_base:
                if total_scores[udp.pool_id] != 0 and pool_profits.get(udp.pool_id, ZERO) > ZERO:
                    udp.amount = quantize_number(
                        udp.delegation_score * pool_profits[udp.pool_id] / total_scores[udp.pool_id],
                        Decimal(1),
                        ROUND_DOWN,
                    )
                else:
                    udp.amount = ZERO
                batch_udps.append(udp)

            UserDelegationProfit.objects.bulk_update(batch_udps, ['amount'])


def distribute_user_profit_on_target_pools(from_date: date, target_pools: Union[List[LiquidityPool], QuerySet]) -> None:
    udps = UserDelegationProfit.objects.filter(user_delegation__pool__in=target_pools)
    null_amount_udp_exists = udps.filter(from_date=from_date, amount__isnull=True).exists()
    if null_amount_udp_exists:
        raise NullAmountUDPExists()

    with transaction.atomic():
        pool_profit_amounts = {
            p['user_delegation__pool']: p['sum_of_profits']
            for p in udps.filter(from_date=from_date)
            .values('user_delegation__pool')
            .annotate(sum_of_profits=Sum('amount'))
        }
        pool_profits = PoolProfit.objects.filter(pool__in=target_pools)
        pool_profits = (
            pool_profits.filter(
                from_date=from_date,
                transaction__isnull=True,
                currency=RIAL,
            )
            .select_related('pool', 'transaction')
            .select_for_update(of=('self',))
        )

        for pool_profit in pool_profits:
            pool_profit.create_transaction(pool_profit_amounts.get(pool_profit.pool.pk, Decimal('0')))

        PoolProfit.objects.bulk_update(pool_profits, ('transaction',))

    udps = (
        udps.filter(transaction__isnull=True, from_date=from_date)
        .select_related('user_delegation')
        .prefetch_related('user_delegation__pool', 'user_delegation__user')
    )

    for i, udp in enumerate(udps):
        with transaction.atomic():
            udp.create_transaction()
            udp.save(update_fields=('transaction',))

        # To create some time for other parts of system
        if i % 100 == 0:
            sleep(0.1)


def calculate_apr(pool: LiquidityPool, total_score: Decimal, from_date: date, to_date: date) -> Union[Decimal, None]:
    """Calculate annual percentage rate as follow:

        1. calculate score of holding 1 unit of token for 30 days
        2. calculate share of profit for the calculated score
        3. calculate current APR by dividing share of profit by equivalent of the 1 unit of token in rial
        4. take avg of current and previous APR

    Args:
        pool (LiquidityPool): input pool
        total_score (Decimal): sum of all scores for pool
        from_date (date): from date
        to_date (date): to date
    Returns:
        Decimal: APR
    """

    if pool.capacity == 0:
        return

    base_amount = Decimal(1)
    period = (to_date - from_date).days + 1
    base_score = base_amount * effective_days(period)
    share_of_pool = base_score / (total_score or base_score)
    pool_profit = (
        PoolProfit.objects.filter(pool=pool, from_date=from_date).values('pool').aggregate(profit=Sum('rial_value'))
    )['profit']

    if not pool_profit or pool_profit <= ZERO:
        return ZERO

    share_of_profit = max(pool_profit * share_of_pool, ZERO)
    token_candle = MarketCandle.objects.filter(
        start_time__date=to_date,
        resolution=MarketCandle.RESOLUTIONS.day,
        market=pool.get_market(Currencies.rls),
    ).first()

    if token_candle:
        token_price = token_candle.close_price
        base_amount_in_rial = base_amount * token_price
    else:
        base_amount_in_rial = PriceEstimator.get_rial_value_by_best_price(
            base_amount,
            pool.currency,
            'buy',
            db_fallback=True,
        )

    if not base_amount_in_rial or money_is_zero(base_amount):
        return ZERO

    current_apr = share_of_profit / base_amount_in_rial * 100 * 12
    return current_apr


def populate_apr_of_target_pools(from_date: date, to_date: date, target_pools: Union[List[LiquidityPool], QuerySet]):
    """Update target pools APR and reset current profit

    Args:
        from_date (date): start date of calculation
        to_date (date): end date of calculation
        target_pools (LiquidityPool): list of pools to calculate apr for
    """
    udps = UserDelegationProfit.objects.filter(user_delegation__pool__in=target_pools)
    pools_total_score = {
        pool_score['pool']: pool_score['total_score']
        for pool_score in udps.filter(from_date=from_date)
        .values('user_delegation__pool')
        .annotate(pool=F('user_delegation__pool'), total_score=Sum('delegation_score'))
    }
    pool_dict = {pool.id: pool for pool in target_pools}

    for pool_id, total_score in pools_total_score.items():
        current_apr = calculate_apr(pool_dict[pool_id], total_score, from_date, to_date)
        previous_profit = pool_dict[pool_id].apr if pool_dict[pool_id].apr is not None else current_apr
        pool_dict[pool_id].apr = (current_apr + previous_profit) * Decimal('0.5')

    LiquidityPool.objects.bulk_update(pool_dict.values(), ('apr',))


def distribute_profits_for_target_pools(
    start_date: date,
    end_date: date,
    target_pools: Union[List[LiquidityPool], QuerySet],
    positions_close_date: date = None,
):
    if not positions_close_date:
        positions_close_date = end_date
    populate_daily_profit_for_target_pools(start_date, positions_close_date, target_pools)
    convert_target_pools_usdt_profits_to_rial(start_date, positions_close_date, target_pools)
    sleep(1)

    try:
        populate_realized_profits_for_target_pools(start_date, target_pools)
    except PartialConversionOrderException:
        convert_target_pools_usdt_profits_to_rial(start_date, positions_close_date, target_pools)
        raise

    populate_users_delegation_score_on_target_pools(start_date, end_date, target_pools)
    populate_users_profit_on_target_pools(start_date, target_pools)
    distribute_user_profit_on_target_pools(start_date, target_pools)

    with transaction.atomic():
        populate_apr_of_target_pools(start_date, end_date, target_pools)
        for liquidity_pool in target_pools:
            create_or_update_pool_stat(liquidity_pool, start_date, end_date, positions_close_date)

        # To reset current profit
        from_date, to_date = get_first_and_last_of_jalali_month(ir_today())
        populate_daily_profit_for_target_pools(from_date, to_date, target_pools)


def create_or_update_pool_stat(
    pool: LiquidityPool, from_date: date, to_date: date, positions_close_date: date
) -> PoolStat:
    udps = UserDelegationProfit.objects.filter(user_delegation__pool=pool, from_date=from_date, to_date=to_date)
    pool_profits = PoolProfit.objects.filter(pool=pool, from_date=from_date, to_date=positions_close_date)
    total_score = udps.aggregate(total_score=Coalesce(Sum('delegation_score'), ZERO))['total_score']

    token_candle = MarketCandle.objects.filter(
        start_time__date=to_date,
        resolution=MarketCandle.RESOLUTIONS.day,
        market=pool.get_market(Currencies.rls),
    ).first()

    data = dict(
        apr=calculate_apr(pool, total_score, from_date, to_date),
        balance=pool.filled_capacity,
        capacity=pool.capacity,
        total_delegators=udps.aggregate(count=Coalesce(Count('*'), 0))['count'],
        avg_balance=total_score / effective_days(pool.profit_period),
        total_profit_in_rial=pool_profits.aggregate(profit=Coalesce(Sum('rial_value'), ZERO))['profit'],
        token_price=token_candle.close_price if token_candle else ZERO,
    )

    pool_stat, _ = PoolStat.objects.update_or_create(pool=pool, from_date=from_date, to_date=to_date, defaults=data)
    return pool_stat
