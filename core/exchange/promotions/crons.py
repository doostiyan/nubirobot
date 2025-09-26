import datetime
import pytz

from exchange.base.crons import CronJob, Schedule
from exchange.base.calendar import ir_today, ir_now


from exchange.promotions.discount import (
    calculate_discount,
    update_status_finished_discount,
    return_remain_amount_in_user_discount,
)


class DiscountUpdateCron(CronJob):
    schedule = Schedule(run_at_times=["01:13"])
    code = "user_discount_calculation_cron"

    def run(self):
        start_date = ir_today() - datetime.timedelta(days=1)

        utc_end_datetime = (
            ir_now().astimezone(pytz.timezone("UTC")).replace(hour=20, minute=30, second=0, microsecond=0)
        )
        utc_start_datetime = utc_end_datetime - datetime.timedelta(days=1)

        print("calculating user_discount ...")
        calculate_discount(start_date, utc_start_datetime, utc_end_datetime)

        print("update discount status and user_discount end_date...")
        update_status_finished_discount(start_date)

        print("update budget remain...")
        return_remain_amount_in_user_discount(start_date)
