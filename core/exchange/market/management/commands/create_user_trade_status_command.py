from django.core.management import BaseCommand

from exchange.accounts.models import User
from exchange.market.models import UserTradeStatus


class Command(BaseCommand):
    def handle(self, *args, **options):
        users_without_trade_status = User.objects.filter(month_trades_status__isnull=True)
        trade_statuses = [UserTradeStatus(user=user) for user in users_without_trade_status]
        UserTradeStatus.objects.bulk_create(trade_statuses, batch_size=1000)
