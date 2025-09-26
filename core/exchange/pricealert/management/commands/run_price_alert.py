"""Price Alerter Daemon"""
import time

from django.core.management.base import BaseCommand
from django.db.models import Q

from exchange.market.models import Market
from exchange.pricealert.models import PriceAlert


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        try:
            while True:
                time_start = time.time()
                sent = 0
                for market in Market.get_active_markets():
                    market_price = market.get_last_trade_price()
                    if not market_price:
                        continue
                    # Find active price-based alerts
                    active_alerts = PriceAlert.objects.filter(
                        Q(param_direction=True, param_value__lte=market_price) |
                        Q(param_direction=False, param_value__gte=market_price),
                        tp=PriceAlert.TYPES.price,
                        market=market,
                    )
                    # Send alerts
                    active_alerts = active_alerts.select_related('market', 'user')
                    for alert in active_alerts:
                        alert.send_notification()
                        sent += 1
                total_time = round((time.time() - time_start) * 1000)
                print(f'Sent {sent} alerts.\t\t\t\t[{total_time}ms]')
                time.sleep(60)
        except KeyboardInterrupt:
            print('bye!')
