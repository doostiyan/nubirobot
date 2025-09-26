from decimal import Decimal

from exchange.accounts.models import Notification, UserRestriction
from exchange.base.calendar import ir_now
from exchange.base.crons import CronJob, Schedule
from exchange.base.logging import report_exception
from exchange.credit.helpers import get_user_net_worth, get_user_debt_worth
from exchange.credit.models import CreditPlan


class CreditLimitForAdminNotificationCron(CronJob):
    schedule = Schedule(run_every_mins=10)
    code = 'credit_limit_notification'

    def run(self):
        credit_plans = CreditPlan.objects.filter(expires_at__gt=ir_now())
        for credit_plan in credit_plans:
            try:
                total_user_balance_worth = get_user_net_worth(credit_plan.user.id)
                total_user_debt_worth = get_user_debt_worth(credit_plan.user.id)
                user_assets_worth = total_user_balance_worth - total_user_debt_worth

                def does_user_debt_exceed_ratio(ratio):
                    return user_assets_worth <= Decimal('0') or (
                       total_user_debt_worth > Decimal('0') and total_user_debt_worth / user_assets_worth >= ratio
                    )

                if does_user_debt_exceed_ratio(credit_plan.maximum_withdrawal_percentage):
                    Notification.notify_admins(message=f"عبور از محدودیت برداشت در credit توسط کاربر {credit_plan.user.id}")

                if does_user_debt_exceed_ratio(Decimal('0.66')):
                    UserRestriction.freeze_user(credit_plan.user_id)
                    Notification.notify_admins(message=f"عبور از محدودیت نسبت ۱.۵ دارای به اعتبار کسب شده در credit توسط کاربر {credit_plan.user.id}")

            except Exception as _:
                report_exception()
