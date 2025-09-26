import datetime

import jdatetime
from django_cron import Schedule

from exchange.base.calendar import ir_today
from exchange.base.crons import CronJob
from exchange.portfolio.services import DailyPortfolioGenerator, MonthlyPortfolioGenerator, delete_old_daily_user_profit


class SaveDailyUserProfit(CronJob):
    schedule = Schedule(run_at_times=['00:05'])
    code = 'save_daily_user_profit'

    def run(self):
        """Create user daily and monthly profit records

        Every night, calculate and save user's profit during last day
        Every first day of shamsi month, calculate and save user's profit during last shamsi month
        Finally, delete older profit records
        """
        yesterday = ir_today() - datetime.timedelta(days=1)
        DailyPortfolioGenerator(report_date=yesterday).create_users_profits()

        if jdatetime.datetime.now().day == 1:
            MonthlyPortfolioGenerator(report_date=yesterday).create_users_profits()

        delete_old_daily_user_profit()
