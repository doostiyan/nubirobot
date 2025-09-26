import datetime
from django.core.management import BaseCommand
from tqdm import tqdm
from django.db.models import Q
from exchange.portfolio.functions import get_last_day_of_month_jalali, get_withdraws_in_range, get_total_cached_data, \
    get_deposits_in_range
from exchange.portfolio.models import UserTotalDailyProfit, UserTotalMonthlyProfit
import jdatetime


class Command(BaseCommand):
    help = 'Update withdraw or deposit in portfolio user profit model!' \
           ' default is Daily and update withdraws. Use --monthly to calc Monthly profits' \
           ' and use --deposit parameter to update deposits values'

    def add_arguments(self, parser):
        parser.add_argument('--from')
        parser.add_argument('--to')
        parser.add_argument(
            '--monthly',
            action='store_true',
            help='Calculate Monthly profits instead of Daily',
        )
        parser.add_argument(
            '--deposit',
            action='store_true',
            help='Update deposit values instead of withdraws',
        )

    def handle(self, *args, **options):
        from_date = datetime.datetime.strptime(options['from'], '%Y-%m-%d') if options['from'] else None
        to_date = datetime.datetime.strptime(options['to'], '%Y-%m-%d') if options['to'] else datetime.date.today()
        success_count = 0
        updated_count = 0
        if not from_date:
            self.stdout.write(self.style.ERROR(f'The parameter --from is required!'))
            return

        profit_query = Q(report_date__gte=from_date, report_date__lte=to_date)
        if options['monthly']:
            all_monthly_profits = UserTotalMonthlyProfit.objects.filter(profit_query)\
                .select_related('user').order_by('report_date')
            last_profit = all_monthly_profits.last()
            if not last_profit:
                self.stdout.write(self.style.ERROR('There is no MonthlyProfit record in this range!'))
                return
            j_last_profit_date = jdatetime.datetime.fromgregorian(date=last_profit.report_date)
            to_date_data = j_last_profit_date.replace(day=get_last_day_of_month_jalali(j_last_profit_date)).togregorian()

            if options['deposit']:
                data = get_withdraws_in_range(from_date, to_date_data)
            else:
                data = get_deposits_in_range(from_date, to_date_data)

            items_count = len(all_monthly_profits)
            for profit in tqdm(all_monthly_profits):
                j_report_date = jdatetime.datetime.fromgregorian(date=profit.report_date)
                from_date = j_report_date.replace(day=1).togregorian() - datetime.timedelta(days=1)
                to_date = j_report_date.replace(day=get_last_day_of_month_jalali(j_report_date)).togregorian()
                total_amount = get_total_cached_data(data, profit.user.id, from_date, to_date)
                if total_amount:
                    if options['deposit']:
                        profit.total_deposit = total_amount
                    else:
                        profit.total_withdraw = total_amount
                    profit.save()
                    updated_count += 1
                success_count += 1
            final_message = f'Successfully process {success_count} item from {items_count} and ' \
                            f'update {updated_count}'
        else:
            if options['deposit']:
                data = get_deposits_in_range(from_date, to_date)
            else:
                data = get_withdraws_in_range(from_date, to_date)
            all_daily_profits = list(UserTotalDailyProfit.objects.filter(profit_query).order_by('report_date'))
            items_count = len(all_daily_profits)
            if not items_count:
                self.stdout.write(self.style.ERROR('There is no DailyProfit record in this range!'))
                return
            users = set([x.user_id for x in all_daily_profits])
            for user_id in tqdm(users):
                last_profit_date = None
                profits = [profit for profit in all_daily_profits if profit.user_id == user_id]
                for profit in profits:
                    report_date = profit.report_date
                    if last_profit_date and not last_profit_date == report_date - datetime.timedelta(days=1):
                        total_amount = get_total_cached_data(data, user_id, last_profit_date, report_date)
                    else:
                        total_amount = get_total_cached_data(data, user_id, report_date, report_date)
                    if total_amount:
                        if options['deposit']:
                            profit.total_deposit = total_amount
                        else:
                            profit.total_withdraw = total_amount
                        profit.save()
                        updated_count += 1
                    success_count += 1
                    last_profit_date = report_date
            final_message = f'Successfully process {success_count} item from {items_count} and ' \
                            f'update {updated_count} for {len(users)} users'

        self.stdout.write(self.style.SUCCESS(final_message))
