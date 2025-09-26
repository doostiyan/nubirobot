import datetime

from django.db.models import Q
from django.utils.timezone import now
from django_cron import Schedule

from exchange.accounts.models import Notification
from exchange.base.calendar import ir_now
from exchange.base.crons import CronJob
from exchange.base.logging import log_event
from exchange.base.models import RIAL, Settings
from exchange.shetab.handlers.jibit import JibitPip
from exchange.shetab.handlers.vandar import VandarP2P
from exchange.shetab.models import ShetabDeposit
from exchange.wallet.models import Transaction, Wallet


class SyncShetabDepositsCron(CronJob):
    schedule = Schedule(run_every_mins=3)
    code = 'sync_shetab_deposits'

    def run(self):
        print('[CRON] sync_shetab_deposits')

        nw = ir_now()
        deposits = ShetabDeposit.objects.filter(
            broker__in=(ShetabDeposit.BROKER.vandar, ShetabDeposit.BROKER.jibit, ShetabDeposit.BROKER.jibit_v2),
            created_at__lt=nw - datetime.timedelta(minutes=7),
        ).filter(
            Q(status_code=ShetabDeposit.STATUS.pay_new, created_at__gte=nw - datetime.timedelta(minutes=30))
            | Q(status_code=-2, created_at__gte=nw - datetime.timedelta(minutes=16))
        )

        print(f'Syncing {len(deposits)} deposits...')

        results = []
        for deposit in deposits:
            old_status = deposit.status_code
            ok = deposit.sync_and_update(retry=True)
            results.append(ok)
            if deposit.status_code != old_status == ShetabDeposit.STATUS.confirmation_failed:
                message = f'Changed shetab deposit #{deposit.pk} status from {ShetabDeposit.STATUS.confirmation_failed} to {deposit.status_code}'
                log_event(message, level='info', module='shetab', category='notice', runner='cron', details=f'ok: {ok}')

        print(f'Result => Success: {results.count(True)}, Failure: {results.count(False)}')


class SyncJibitDepositCron(CronJob):
    schedule = Schedule(run_every_mins=5)
    code = 'sync_jibit_deposit'

    def run(self):
        print('[CRON] sync_shetab_deposits')
        page = 0
        while True:
            response = JibitPip.get_waiting_for_verify(page)
            if not response or not response.get('content'):
                break
            for deposit in response.get('content'):
                JibitPip.create_or_update_jibit_payment(deposit)
            if response.get('last') is True:
                break
            page += 1


class SyncVandarDepositCron(CronJob):
    schedule = Schedule(run_every_mins=5)
    code = 'sync_vandar_deposit'

    def run(self):
        if not Settings.get_flag('vandar_id_deposit'):
            return

        end = ir_now()
        start = end - datetime.timedelta(hours=2)
        page = 1
        while True:
            response = VandarP2P.fetch_deposits(start, end, page)
            if not response:
                break
            for deposit_data in response:
                VandarP2P.get_or_create_payment(deposit_data)
            page += 1


class CheckInvalidShetabDepositCron(CronJob):
    """Check for validating that all recent invalid ShetabDeposits have a
        valid blocking transactions applied, because this balance should not
        be used by the user and Matcher assume it is handled in users' wallet
        balances.
    """
    schedule = Schedule(run_every_mins=10)
    code = 'check_invalid_shetab_deposit'

    def run(self):
        print('Checking recent invalid ShetabDeposits...')
        recent_invalid_deposits = ShetabDeposit.objects.filter(
            status_code=ShetabDeposit.STATUS.invalid_card,
            created_at__gte=now() - datetime.timedelta(hours=2),
        ).select_related('transaction')
        checks = 0
        for deposit in recent_invalid_deposits:
            checks += 1
            wallet = Wallet.get_user_wallet(deposit.user_id, RIAL)
            if not deposit.transaction:
                Notification.notify_admins(
                    f'Invalid ShetabDeposit with no charge Transaction: #{deposit.id}',
                    title='⭕️ Check Failed',
                    channel='matcher',
                )
                continue
            block_transaction = Transaction.objects.filter(
                wallet=wallet,
                ref_module=Transaction.REF_MODULES['ShetabBlock'],
                ref_id=deposit.pk,
                tp=Transaction.TYPE.manual,
                amount=-deposit.transaction.amount,
                created_at__gt=deposit.transaction.created_at,
            )
            if not block_transaction.exists():
                Notification.notify_admins(
                    f'Invalid ShetabDeposit with no valid block Transaction: #{deposit.id}',
                    title='⭕️ Check Failed',
                    channel='matcher',
                )
        print(f'Checked {checks} deposits.')
