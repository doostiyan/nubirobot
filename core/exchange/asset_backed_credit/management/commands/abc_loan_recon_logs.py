import csv
import os
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

import jdatetime
from django.contrib.postgres.aggregates import ArrayAgg
from django.core.management.base import BaseCommand
from django.db import transaction

from exchange.asset_backed_credit.models import IncomingAPICallLog, Service, SettlementTransaction, UserService
from exchange.base.models import Currencies
from exchange.market.models import Order


@dataclass
class OrderSchema:
    id: int
    currency: str
    amount: Decimal
    price: Decimal
    status: str
    matched_amount: Decimal
    matched_total_price: Decimal
    fee: Decimal
    actual_amount: Decimal


class Command(BaseCommand):
    help = "get initiated loan services info"

    INIT_LOGS_FILE_NAME = os.path.join(tempfile.gettempdir(), 'abc_loan_init_logs.csv')
    UNLOCK_LOGS_FILE_NAME = os.path.join(tempfile.gettempdir(), 'abc_loan_unlock_logs.csv')
    SETTLEMENT_LOGS_FILE_NAME = os.path.join(tempfile.gettempdir(), 'abc_loan_settlement_logs.csv')

    def add_arguments(self, parser):
        parser.add_argument('--type', type=str, help='Type of report', required=False)
        parser.add_argument('--start-date', type=str, help='Start date in YYYY-MM-DD', required=False)
        parser.add_argument('--end-date', type=str, help='End date in YYYY-MM-DD', required=False)

    @transaction.atomic
    def handle(self, *args, **options):
        rtype = options['type'] if options['type'] else None
        if rtype and rtype not in ('lock', 'unlock', 'settle'):
            self.stdout.write(self.style.ERROR('Invalid value for type, choices are [lock, unlock, settle]'))
            return

        j_start_date = options['start_date'] if options['start_date'] else None
        if j_start_date:
            try:
                start_date = jdatetime.datetime.strptime(j_start_date, '%Y-%m-%d')
                start_date = jdatetime.datetime.togregorian(start_date)
            except ValueError:
                self.stdout.write(self.style.ERROR('Invalid start-date input'))
                return
        else:
            start_date = None

        j_end_date = options['end_date'] if options['end_date'] else None
        if j_end_date:
            try:
                end_date = jdatetime.datetime.strptime(j_end_date, '%Y-%m-%d')
                end_date = jdatetime.datetime.togregorian(end_date)
            except ValueError:
                self.stdout.write(self.style.ERROR('Invalid start-date input'))
                return
        else:
            end_date = None

        try:
            service = Service.objects.get(provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan)
        except Service.DoesNotExist:
            self.stdout.write('invalid service.')
            return

        user_services = UserService.objects.select_related('user').filter(
            service=service,
            status__in=[UserService.STATUS.initiated, UserService.STATUS.settled],
        )

        if rtype == 'lock':
            return self._log_initiated_services(user_services, start_date, end_date)
        if rtype == 'unlock':
            return self._log_unlocks_on_loans(user_services, start_date, end_date)
        if rtype == 'settle':
            return self._log_settlement_transactions(user_services, start_date, end_date)

        # log all reports
        self._log_initiated_services(user_services)
        self._log_unlocks_on_loans(user_services)
        self._log_settlement_transactions(user_services)

    def _log_initiated_services(self, user_services, start_date=None, end_date=None):
        self.stdout.write(self.style.SUCCESS(f'logging initiated loans...'))

        api_logs = IncomingAPICallLog.objects.select_related('user').filter(
            provider=Service.PROVIDERS.vency,
            service=Service.TYPES.loan,
            api_url='/asset-backed-credit/v1/lock',
            status=IncomingAPICallLog.STATUS.success,
        )

        if start_date:
            api_logs = api_logs.filter(created_at__gte=start_date)
        if end_date:
            api_logs = api_logs.filter(created_at__lte=end_date)

        api_logs = api_logs.values(
            'user__national_code',
            'created_at',
            'request_body',
        )

        unique_ids = set([log['request_body'].get('uniqueIdentifier') for log in api_logs])
        user_services = user_services.filter(external_id__in=unique_ids)

        user_services = user_services.values(
            'id',
            'user__national_code',
            'initial_debt',
            'current_debt',
            'external_id',
            'created_at',
            'closed_at',
            'status',
        )

        self.stdout.write(self.style.SUCCESS(f'loans lock count: {len(user_services)}'))

        logs = []
        for user_service in user_services:
            try:
                _id = user_service['id']
                national_code = user_service['user__national_code']
                init_debt = user_service['initial_debt']
                current_debt = user_service['current_debt']
                loan_id = user_service['external_id']
                if user_service['created_at']:
                    created_at = jdatetime.datetime.fromgregorian(datetime=user_service['created_at']).strftime(
                        '%Y-%m-%d'
                    )
                else:
                    created_at = ''
                if user_service['closed_at']:
                    closed_at = jdatetime.datetime.fromgregorian(datetime=user_service['closed_at']).strftime(
                        '%Y-%m-%d'
                    )
                else:
                    closed_at = ''
                status = UserService.STATUS._display_map.get(user_service['status'], '')

                logs.append(
                    (
                        national_code,
                        str(int(init_debt)),
                        str(int(current_debt)),
                        str(loan_id),
                        created_at,
                        closed_at,
                        status,
                    )
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'failed to append user-service: {user_service}'))
                self.stdout.write(self.style.ERROR(str(e)))

        with open(self.INIT_LOGS_FILE_NAME, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                ['NATIONAL_CODE', 'INIT_DEBT', 'CURRENT_DEBT', 'LOAN_ID', 'CREATED_AT', 'CLOSED_AT', 'STATUS']
            )
            writer.writerows(logs)

        self.stdout.write(self.style.SUCCESS(f'logged initiated loans successfully.'))
        self.stdout.write(self.style.SUCCESS(f'logged {len(user_services)} rows in {self.INIT_LOGS_FILE_NAME}'))
        self.stdout.write('\n')

    def _log_unlocks_on_loans(self, user_services, start_date=None, end_date=None):
        self.stdout.write(self.style.SUCCESS(f'logging unlocked calls...'))

        loans_by_users = defaultdict(list)
        for user_service in user_services.values(
            'id',
            'user__national_code',
            'initial_debt',
            'current_debt',
            'external_id',
            'created_at',
            'closed_at',
            'status',
        ):
            loans_by_users[user_service['user__national_code']].append(user_service)

        loans_by_users = {
            k: sorted(v, key=lambda us: us['created_at'], reverse=True) for k, v in loans_by_users.items()
        }

        api_logs = IncomingAPICallLog.objects.select_related('user_service', 'user').filter(
                provider=Service.PROVIDERS.vency,
                service=Service.TYPES.loan,
                api_url='/asset-backed-credit/v1/unlock',
                status=IncomingAPICallLog.STATUS.success,
        )
        if start_date:
            api_logs = api_logs.filter(created_at__gte=start_date)
        if end_date:
            api_logs = api_logs.filter(created_at__lte=end_date)

        api_logs = api_logs.values(
            'user__national_code',
            'created_at',
            'request_body',
        )

        self.stdout.write(self.style.SUCCESS(f'loan unlock count: {len(api_logs)}'))

        logs = []
        for api_log in api_logs:
            national_code = api_log['user__national_code']
            created_at = api_log['created_at']
            amount = api_log['request_body'].get('amount')
            try:
                related_loan = [loan for loan in loans_by_users[national_code] if created_at >= loan['created_at']][0]
                external_id = related_loan['external_id']
                status = UserService.STATUS._display_map.get(related_loan['status'], '')
            except (IndexError, TypeError):
                external_id = None
                status = None

            logs.append(
                (
                    jdatetime.datetime.fromgregorian(datetime=created_at).strftime('%Y-%m-%d'),
                    national_code,
                    external_id,
                    amount,
                    status,
                    api_log['request_body'].get('trackId'),
                )
            )

        with open(self.UNLOCK_LOGS_FILE_NAME, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['CREATED_AT', 'NATIONAL_CODE', 'LOAN_ID', 'AMOUNT', 'LOAN_STATUS', 'TRACK_ID'])
            writer.writerows(logs)

        self.stdout.write(self.style.SUCCESS(f'logged unlock calls successfully.'))
        self.stdout.write(self.style.SUCCESS(f'logged {len(logs)} rows in {self.UNLOCK_LOGS_FILE_NAME}'))
        self.stdout.write('\n')

    def _log_settlement_transactions(self, user_services, start_date=None, end_date=None):
        self.stdout.write(self.style.SUCCESS(f'logging settlement calls...'))
        user_services = user_services.values(
            'id',
            'user__national_code',
            'initial_debt',
            'current_debt',
            'principal',
            'installment_amount',
            'installment_period',
            'provider_fee_amount',
            'external_id',
            'created_at',
            'closed_at',
            'status',
        )

        ids = [us['id'] for us in user_services]

        loans_by_users = defaultdict(list)
        for user_service in user_services:
            loans_by_users[user_service['user__national_code']].append(user_service)

        user_services = {user_service['id']: user_service for user_service in user_services}
        loans_by_users = {
            k: sorted(v, key=lambda us: us['created_at'], reverse=True) for k, v in loans_by_users.items()
        }

        api_logs = IncomingAPICallLog.objects.select_related('user_service', 'user').filter(
            provider=Service.PROVIDERS.vency,
            service=Service.TYPES.loan,
            api_url='/asset-backed-credit/v1/settlement',
            status=IncomingAPICallLog.STATUS.success,
        )

        if start_date:
            api_logs = api_logs.filter(created_at__gte=start_date)
        if end_date:
            api_logs = api_logs.filter(created_at__lte=end_date)

        api_logs = api_logs.values(
            'user__national_code',
            'created_at',
            'request_body',
        )

        self.stdout.write(self.style.SUCCESS(f'loan settlement count: {len(api_logs)}'))

        for api_log in api_logs:
            national_code = api_log['user__national_code']
            created_at = api_log['created_at']
            related_loan = [loan for loan in loans_by_users[national_code] if created_at >= loan['created_at']][0]
            user_services[related_loan['id']]['track_id'] = api_log['request_body']['trackId']

        settlements = (
            SettlementTransaction.objects.filter(
                user_service_id__in=ids,
                status__in=[SettlementTransaction.STATUS.confirmed, SettlementTransaction.STATUS.unknown_confirmed],
            )
            .annotate(orders_ids=ArrayAgg('orders__id'))
            .values('user_service_id', 'status', 'created_at', 'amount', 'orders_ids')
        )

        order_ids = []
        for settlement in settlements:
            for order in settlement['orders_ids']:
                if order:
                    order_ids.append(order)

        orders = Order.objects.filter(id__in=order_ids).values(
            'id',
            'src_currency',
            'dst_currency',
            'price',
            'amount',
            'status',
            'matched_amount',
            'matched_total_price',
            'fee',
        )

        orders = {
            order['id']: OrderSchema(
                id=order['id'],
                currency=order['src_currency'],
                amount=order['amount'],
                price=order['price'],
                status=order['status'],
                matched_amount=order['matched_amount'],
                matched_total_price=order['matched_total_price'],
                fee=order['fee'],
                actual_amount=order['matched_total_price'] - order['fee'],
            )
            for order in orders
        }

        settlement_logs = []
        for settlement in settlements:
            created_at = settlement['created_at']
            user_service = user_services[settlement['user_service_id']]
            national_code = user_service['user__national_code']
            loan_id = user_service['external_id']
            loan_initial_debt = int(user_service['initial_debt'])
            loan_current_debt = int(user_service['current_debt'])
            loan_principal = int(user_service['principal'] or 0)
            loan_installment = int(user_service['installment_amount'] or 0)
            loan_period = int(user_service['installment_period'] or 0)
            loan_provider_fee = int(user_service['provider_fee_amount'] or 0)
            loan_status = UserService.STATUS._display_map.get(user_service['status'], '')
            track_id = user_service.get('track_id', '')
            settlement_amount = int(settlement['amount'])
            order_ids = [oid for oid in settlement['orders_ids'] if oid]
            settlement_amount_is_ok = (
                settlement_amount == loan_installment or settlement_amount == loan_installment + loan_provider_fee
            )

            if order_ids:
                for order_id in order_ids:
                    order = orders[order_id]

                    settlement_logs.append(
                        (
                            jdatetime.datetime.fromgregorian(datetime=created_at).strftime('%Y-%m-%d'),
                            national_code,
                            loan_id,
                            loan_initial_debt,
                            loan_current_debt,
                            loan_principal,
                            loan_installment,
                            loan_period,
                            loan_provider_fee,
                            loan_status,
                            settlement_amount,
                            settlement_amount_is_ok,
                            track_id,
                            Currencies._display_map.get(order.currency, None),
                            order.price,
                            order.amount,
                            order.status,
                            order.matched_amount,
                            order.matched_total_price,
                            order.fee,
                            order.actual_amount,
                        )
                    )
            else:
                settlement_logs.append(
                    (
                        jdatetime.datetime.fromgregorian(datetime=created_at).strftime('%Y-%m-%d'),
                        national_code,
                        loan_id,
                        loan_initial_debt,
                        loan_current_debt,
                        loan_principal,
                        loan_installment,
                        loan_period,
                        loan_provider_fee,
                        loan_status,
                        settlement_amount,
                        settlement_amount_is_ok,
                        track_id,
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                    )
                )

        with open(self.SETTLEMENT_LOGS_FILE_NAME, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                [
                    'CREATED_AT',
                    'NATIONAL_CODE',
                    'LOAN_ID',
                    'LOAN_INITIAL_DEBT',
                    'LOAN_CURRENT_DEBT',
                    'LOAN_PRINCIPAL',
                    'LOAN_INSTALLMENT',
                    'LOAN_PERIOD',
                    'LOAN_PROVIDER_FEE',
                    'LOAN_STATUS',
                    'SETTLEMENT_AMOUNT',
                    'SETTLEMENT_IS_OK',
                    'TRACK_ID',
                    'ORDER_CURRENCY',
                    'ORDER_PRICE',
                    'ORDER_AMOUNT',
                    'ORDER_STATUS',
                    'ORDER_MATCHED_AMOUNT',
                    'ORDER_MATCHED_TOTAL_PRICE',
                    'ORDER_FEE',
                    'ORDER_ACTUAL_TOTAL_PRICE',
                ]
            )
            writer.writerows(settlement_logs)

        self.stdout.write(self.style.SUCCESS(f'logged settlement calls successfully.'))
        self.stdout.write(self.style.SUCCESS(f'logged {len(settlement_logs)} rows in {self.SETTLEMENT_LOGS_FILE_NAME}'))
        self.stdout.write('\n')
