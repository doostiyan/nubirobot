""" Command: check_db """
import time
from decimal import Decimal

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Q

from exchange.market.models import Market, Order


class Command(BaseCommand):
    help = 'Check DB performance and connection quality.'

    def handle(self, *args, **kwargs):
        iterations = 10

        # Simple query to check connection
        start_time = time.time()
        for _ in range(iterations):
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
        avg_time = (time.time() - start_time) * 1000 / iterations
        print(f'Simple Query:\t{avg_time:.3f} ms')

        # Check GetOrders Query
        market = Market.by_symbol('BTCIRT')
        orderbook_symbol = 'orderbook_' + market.symbol
        price_range_low = cache.get(orderbook_symbol + '_last_active_buy') or Decimal('0')
        price_range_high = cache.get(orderbook_symbol + '_last_active_sell')
        if not price_range_low or not price_range_high:
            self.stdout.write(
                self.style.ERROR(f'Cannot get price range from orderbook cache. ({price_range_low}/{price_range_high})')
            )
            return
        start_time = time.time()
        orders = (
            Order.objects.filter(
                src_currency=market.src_currency,
                dst_currency=market.dst_currency,
                status=Order.STATUS.active,
            )
            .filter(
                Q(execution_type__in=Order.MARKET_EXECUTION_TYPES)
                | (
                    ~Q(execution_type__in=Order.MARKET_EXECUTION_TYPES)
                    & (
                        Q(order_type=Order.ORDER_TYPES.sell, price__lte=price_range_high)
                        | Q(order_type=Order.ORDER_TYPES.buy, price__gte=price_range_low)
                    )
                ),
            )
            .defer(
                'src_currency',
                'dst_currency',
                'status',
                'description',
                'client_order_id',
            )
        )
        orders = list(orders.order_by('created_at'))
        total_time = (time.time() - start_time) * 1000
        print(f'Fetched {len(orders)} orders in {total_time:.3f} ms')
