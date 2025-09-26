import datetime
from decimal import Decimal
from typing import Optional

from django.core.management.base import BaseCommand
from django.db import transaction

from exchange.accounts.constants import SYSTEM_USER_IDS
from exchange.base.calendar import ir_today
from exchange.base.constants import ZERO
from exchange.base.logging import report_exception
from exchange.base.models import get_currency_codename, parse_market_symbol
from exchange.margin.models import Position, PositionFee, PositionOrder
from exchange.market.models import Order
from exchange.wallet.models import Transaction, Wallet


class Command(BaseCommand):
    """
    Examples:
        python manage.py reopen_shadow_positions \
            --market SOLIRT \
            --start '2023-12-21T20:58:00+03:30' \
            --mins 3 \
            --lp-threshold 60000000
    """

    help = 'Reopen positions liquidated in a market shadow.'

    def add_arguments(self, parser):
        parser.add_argument('--market', type=str, help='Market symbol')
        parser.add_argument('--start', type=str, help='Start time of shadow in ISO format')
        parser.add_argument('--mins', type=int, default=1, help='Duration of shadow in minutes')
        parser.add_argument('--lp-threshold', type=str, help='Liquidation price threshold')
        parser.add_argument('--ep-threshold', type=str, help='Exit price threshold')
        parser.add_argument('--user-ids', type=str, help='User id filter')
        parser.add_argument('--max-fee', type=int, help='Max number of extension fees to take')
        parser.add_argument('--dry-run', action='store_true', default=False)

    def handle(self, market, start, mins, lp_threshold, ep_threshold, user_ids, max_fee, dry_run, **options):
        src_currency, dst_currency = parse_market_symbol(market)
        start_time = datetime.datetime.fromisoformat(start).astimezone()
        end_time = start_time + datetime.timedelta(minutes=mins)
        lp_threshold = Decimal(lp_threshold)
        ep_threshold = Decimal(ep_threshold or lp_threshold)
        if user_ids:
            user_ids = [int(uid) for uid in str(user_ids).split(',')]
        extension_days = (ir_today() - start_time.date()).days
        if max_fee is not None:
            extension_days = min(extension_days, max_fee)

        # Fetch positions
        positions = (
            Position.objects.select_related('user')
            .prefetch_related('orders')
            .filter(
                src_currency=src_currency,
                dst_currency=dst_currency,
                status=Position.STATUS.liquidated,
                closed_at__gte=start_time,
                closed_at__lt=end_time,
                pnl__lt=0,
            )
        )
        if user_ids:
            positions = positions.filter(user_id__in=user_ids)
            print(f'Applying filter for {len(user_ids)} users')
        print(f'Found {len(positions)} liquidated positions in {market} market')

        def price_filter(position: Position):
            if position.is_short:
                return position.liquidation_price >= lp_threshold and position.exit_price >= ep_threshold
            return position.liquidation_price <= lp_threshold and position.exit_price <= ep_threshold

        positions = list(filter(price_filter, positions))
        print(f'of which {len(positions)} positions meet {lp_threshold} liquidation price criteria')

        # Fetch system fix wallets
        system_fix_src_wallet = Wallet.get_user_wallet(user=SYSTEM_USER_IDS.system_fix, currency=src_currency)
        system_fix_dst_wallet = Wallet.get_user_wallet(user=SYSTEM_USER_IDS.system_fix, currency=dst_currency)

        # Reopen positions
        for position in positions:
            try:
                with transaction.atomic():
                    print(f'* Reopening {position.get_side_display()} position #{position.id} of "{position.user}":')
                    old_pnl: Optional[Decimal] = position.pnl
                    if position.pnl_transaction is None or not old_pnl:
                        print('No PNL transaction found for this position')
                        continue
                    user_wallet = Wallet.objects.select_for_update().get(id=position.pnl_transaction.wallet_id)

                    settlement_orders = [
                        order
                        for order in position.cached_orders
                        if order.channel == Order.CHANNEL.system_margin and order.matched_amount
                    ]
                    if not settlement_orders:
                        print('No system settlement found for this position')
                        continue
                    settlement_amount = sum(
                        (o.matched_amount - (o.fee if o.is_buy else 0) for o in settlement_orders), start=ZERO
                    )
                    settlement_total_price = sum(
                        (o.matched_total_price - (o.fee if o.is_sell else 0) for o in settlement_orders), start=ZERO
                    )
                    print(
                        f'Take back {settlement_amount.normalize():f} {get_currency_codename(src_currency)} and '
                        f'return {settlement_total_price.normalize():f} {get_currency_codename(dst_currency)}'
                    )

                    if user_wallet.active_balance < position.collateral + position.pnl:
                        print(f'Not enough active balance for user {position.user.email} to afford old collateral')
                        position.collateral = user_wallet.active_balance - position.pnl
                    position.pnl = None
                    position.pnl_transaction = None
                    position.closed_at = None
                    position.freezed_at = None
                    position.status = Position.STATUS.open
                    position.cached_orders = [
                        order for order in position.cached_orders if order not in settlement_orders
                    ]
                    position.set_delegated_amount()
                    position.set_earned_amount()
                    position.set_exit_price()
                    position_fee_total = position.extension_fee_amount * extension_days
                    position.collateral -= position_fee_total
                    if position.collateral < 0:
                        position.status = Position.STATUS.expired
                        position.collateral = ZERO
                    position.set_liquidation_price()
                    position.set_status()
                    if position.status != position.STATUS.open:
                        print(f'Reopening this position would lead to status "{position.get_status_display()}"')
                        continue

                    # Fetch pool wallets
                    pool_src_wallet = settlement_orders[0].src_wallet
                    pool_dst_wallet = settlement_orders[0].dst_wallet

                    if dry_run:
                        print(f'Liquidation price is {position.liquidation_price} for liability {position.liability}.')
                        print('Changes are not saved.')
                        continue

                    # Detach settlement orders
                    PositionOrder.objects.filter(position=position, order__in=settlement_orders).delete()
                    # Update position
                    position.collateral += position_fee_total
                    position.set_liquidation_price()
                    position.save()
                    # Return loss
                    user_wallet.create_transaction(
                        tp='manual',
                        amount=-old_pnl,
                        description=f'برگردان زیان موقعیت {position.id} بازار {market} به هدف باز شدن مجدد',
                    ).commit(ref=Transaction.Ref('RevertPositionUserPNL', position.id))
                    # Block collateral
                    user_wallet.block(position.collateral)
                    # Get extension fee
                    for i in range(extension_days):
                        PositionFee.objects.create(
                            position=position, date=start_time.date() + datetime.timedelta(days=i + 1)
                        )
                    # Change old PNL transaction ref module to allow transferring next PNL
                    Transaction.objects.filter(
                        ref_module__in=(
                            Transaction.REF_MODULES['PositionUserPNL'],
                            Transaction.REF_MODULES['PositionPoolPNL'],
                        ),
                        ref_id=position.id,
                    ).update(ref_module=None)
                    # Return assets to pool
                    side_ratio = 1 if position.is_short else -1
                    description = f'برگردان دارایی به اشتباه لیکویید شده موقعیت {position.id} بازار {market}'
                    pool_src_wallet.create_transaction(
                        tp='manual',
                        amount=-settlement_amount * side_ratio,
                        description=description,
                    ).commit(
                        ref=Transaction.Ref('ReturnPoolSrcAsset', position.id),
                    )
                    pool_dst_wallet.create_transaction(
                        tp='manual',
                        amount=settlement_total_price * side_ratio + old_pnl,
                        description=description,
                    ).commit(
                        ref=Transaction.Ref('ReturnPoolDstAsset', position.id),
                    )
                    # Payoff with system fix account
                    system_fix_src_wallet.create_transaction(
                        tp='manual',
                        amount=settlement_amount * side_ratio,
                        description=description,
                        allow_negative_balance=True,
                    ).commit(
                        ref=Transaction.Ref('MarginShadowSrcFix', position.id),
                        allow_negative_balance=True,
                    )
                    system_fix_dst_wallet.create_transaction(
                        tp='manual',
                        amount=-settlement_total_price * side_ratio,
                        description=description,
                        allow_negative_balance=True,
                    ).commit(
                        ref=Transaction.Ref('MarginShadowDstFix', position.id),
                        allow_negative_balance=True,
                    )
                    print('Changes have been submitted successfully.')
            except Exception as e:
                print('Something occurred:', e)
                report_exception()
