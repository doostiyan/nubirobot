from django_cron import Schedule

from exchange.base.crons import CronJob
from exchange.features.models import QueueItem
from exchange.portfolio.services import enable_portfolios


class ActiveDailyUserPortfolio(CronJob):
    schedule = Schedule(run_at_times=['23:55'])
    code = 'active_daily_user_portfolio'

    def run(self):
        """Activate portfolios for users in feature queue"""
        queue_items = QueueItem.objects.filter(
            feature=QueueItem.FEATURES.portfolio,
            status=QueueItem.STATUS.waiting,
        ).order_by('created_at')
        user_ids = tuple(queue_items.values_list('user_id', flat=True)[:4000])
        enable_portfolios(user_ids)
        queue_items.filter(user_id__in=user_ids).update(status=QueueItem.STATUS.done)
