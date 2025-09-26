from django.core.management.base import BaseCommand

from exchange.base.models import Settings
from exchange.xchange.trade_collector import TradeCollector


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        TradeCollector().run()
        Settings.set('is_active_collect_trades_from_market_maker_cron', 'yes')
