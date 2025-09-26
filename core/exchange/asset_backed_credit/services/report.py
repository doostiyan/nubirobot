import csv
import io
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any, List

import jdatetime
from django.contrib.postgres.aggregates import ArrayAgg
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Prefetch

from exchange.asset_backed_credit.models import (
    CreditReport,
    IncomingAPICallLog,
    ReportAttachment,
    Service,
    SettlementTransaction,
    UserService,
)
from exchange.base.logging import report_event
from exchange.base.models import Currencies
from exchange.market.models import Order

LOCK_URL = '/asset-backed-credit/v1/lock'
UNLOCK_URL = '/asset-backed-credit/v1/unlock'
SETTLEMENT_URL = '/asset-backed-credit/v1/settlement'

FILE_NAME_FORMAT = 'report_{id}_{type}.csv'

LOCK_HEADERS = {
    Service.TYPES.loan: [
        'شماره ملی کاربر',
        'شناسه وام',
        'تاریخ ایجاد',
        'مبلغ وام',
        'مدت وام',
        'بدهی اولیه',
        'بدهی فعلی',
        'وضعیت وام',
        'تاریخ بسته شدن',
        'شناسه درخواست',
    ]
}

UNLOCK_HEADERS = {
    Service.TYPES.loan: [
        'شماره ملی کاربر',
        'شناسه وام',
        'وضعیت وام',
        'شناسه درخواست',
        'تاریخ ارسال',
        'مبلغ آزادسازی',
    ]
}

SETTLE_HEADERS = {
    Service.TYPES.loan: [
        'تاریخ ایجاد',
        'شماره ملی کاربر',
        'شناسه وام',
        'مبلغ وام',
        'بدهی اولیه',
        'بدهی فعلی',
        'مبلغ اقساط',
        'مدت اقساط',
        'هزینه سرویس دهنده',
        'وضعیت وام',
        'شناسه درخواست',
        'مبلغ درخواست تسویه',
        'وضعیت درخواست تسویه',
        'همخوانی مبلغ تسویه',
        'ارز سفارش',
        'مبلغ سفارش',
        'مقدار سفارش',
        'وضعیت سفارش',
        'مقدار مچ شده سفارش',
        'مبلغ مچ شده سفارش',
        'فی سفارش',
        'مبلغ واقعی سفارش',
    ]
}


@transaction.atomic
def generate_requested_reports_attachments():
    for report in CreditReport.objects.filter(status=CreditReport.Status.CREATED).select_for_update(no_key=True):
        try:
            generate_report_attachments(report=report)
        except Exception as e:
            report_event(
                'ABC_REPORT_ERROR: Failed to generate attachments for report',
                extras={'report_id': report.id, 'error': str(e)},
            )
            raise e

def generate_report_attachments(report: CreditReport):
    if report.status != CreditReport.Status.CREATED:
        return

    if not report.service.tp == Service.TYPES.loan:
        report.status = CreditReport.Status.COMPLETED
        report.save(update_fields=['status'])
        return

    if report.type in [CreditReport.Type.ALL, CreditReport.Type.LOCK]:
        _generate_report_lock_attachment(report=report)
    if report.type in [CreditReport.Type.ALL, CreditReport.Type.UNLOCK]:
        _generate_report_unlock_attachment(report=report)
    if report.type in [CreditReport.Type.ALL, CreditReport.Type.SETTLEMENT]:
        _generate_report_settlement_attachment(report=report)
    if report.type in [CreditReport.Type.ALL, CreditReport.Type.SETTLEMENT_MISMATCH]:
        _generate_report_settlement_mismatch_attachment(report=report)

    report.status = CreditReport.Status.COMPLETED
    report.save(update_fields=['status'])


def _generate_report_lock_attachment(report: CreditReport):
    logs = _get_logs(report=report, url=LOCK_URL)
    rows = []
    for log in logs:
        try:
            national_code = log['user__national_code']
            principal = log['user_service__principal']
            installment_period = log['user_service__installment_period']
            init_debt = log['user_service__initial_debt']
            current_debt = log['user_service__current_debt']
            created_at = log['user_service__created_at']
            closed_at = log['user_service__closed_at']
            unique_id = log['user_service__account_number']
            status = UserService.Status(log['user_service__status']).name

            if created_at:
                created_at = jdatetime.datetime.fromgregorian(datetime=created_at).strftime('%Y-%m-%d')
            else:
                created_at = ''

            if closed_at:
                closed_at = jdatetime.datetime.fromgregorian(datetime=closed_at).strftime('%Y-%m-%d')
            else:
                closed_at = ''
            rows.append(
                (
                    national_code,
                    unique_id,
                    created_at,
                    str(int(principal)),
                    str(installment_period),
                    str(int(init_debt)),
                    str(int(current_debt)),
                    status,
                    closed_at,
                )
            )
        except Exception as e:
            error_row = tuple(['error'] * len(LOCK_HEADERS[report.service.tp]))
            rows.append(error_row)
            report_event(
                'ABC_REPORT_ERROR',
                extras={
                    'report_id': report.id,
                    'log_id': log.id,
                    'user_service_id': log['user_service__id'],
                    'error': str(e),
                },
            )

    _attach_report_as_file(
        report=report,
        headers=LOCK_HEADERS[report.service.tp],
        rows=rows,
        file_name=FILE_NAME_FORMAT.format(id=report.id, type='lock'),
        attachment_type=ReportAttachment.AttachmentType.LOCK,
    )


def _generate_report_unlock_attachment(report: CreditReport):
    logs = _get_logs(report=report, url=UNLOCK_URL)

    rows = []
    for log in logs:
        try:
            national_code = log['user__national_code']
            created_at = log['created_at']
            amount = log['request_body'].get('amount')
            account_number = log['user_service__account_number']
            status = UserService.Status(log['user_service__status']).name

            rows.append(
                (
                    national_code,
                    account_number,
                    status,
                    log['request_body'].get('trackId'),
                    jdatetime.datetime.fromgregorian(datetime=created_at).strftime('%Y-%m-%d'),
                    amount,
                )
            )
        except Exception as e:
            error_row = tuple(['error'] * len(UNLOCK_HEADERS[report.service.tp]))
            rows.append(error_row)
            report_event(
                'ABC_REPORT_ERROR',
                extras={
                    'report_id': report.id,
                    'log_id': log.id,
                    'user_service_id': log['user_service__id'],
                    'error': str(e),
                },
            )

    _attach_report_as_file(
        report=report,
        headers=UNLOCK_HEADERS[report.service.tp],
        rows=rows,
        file_name=FILE_NAME_FORMAT.format(id=report.id, type='unlock'),
        attachment_type=ReportAttachment.AttachmentType.UNLOCK,
    )


def _generate_report_settlement_attachment(report: CreditReport):
    incoming_logs = _get_logs(report=report, url=SETTLEMENT_URL)
    settlements = _get_settlements(report, incoming_logs)
    logs_list = _build_settlement_logs(settlements, incoming_logs, mismatch_only=False)
    if len(logs_list) == 0:
        error_row = tuple(['error'] * len(SETTLE_HEADERS[report.service.tp]))
        logs_list.append(error_row)
        report_event(
            'ABC_REPORT_ERROR_SETTLEMENT',
            extras={
                'report_id': report.id,
                'reason': 'Input logs and settlements data are not in sync',
            },
        )

    _attach_report_as_file(
        report=report,
        headers=SETTLE_HEADERS[report.service.tp],
        rows=logs_list,
        file_name=FILE_NAME_FORMAT.format(id=report.id, type='settlement'),
        attachment_type=ReportAttachment.AttachmentType.SETTLEMENT,
    )


def _generate_report_settlement_mismatch_attachment(report: CreditReport):
    incoming_logs = _get_logs(report=report, url=SETTLEMENT_URL)
    settlements = _get_settlements(report, incoming_logs)
    logs_list = _build_settlement_logs(settlements, incoming_logs, mismatch_only=True)
    if len(logs_list) == 0:
        error_row = tuple(['error'] * len(SETTLE_HEADERS[report.service.tp]))
        logs_list.append(error_row)
        report_event(
            'ABC_REPORT_ERROR_SETTLEMENT',
            extras={
                'report_id': report.id,
                'reason': 'Input logs and settlements data are not in sync',
            },
        )

    _attach_report_as_file(
        report=report,
        headers=SETTLE_HEADERS[report.service.tp],
        rows=logs_list,
        file_name=FILE_NAME_FORMAT.format(id=report.id, type='settlement_mismatch'),
        attachment_type=ReportAttachment.AttachmentType.SETTLEMENT_MISMATCH,
    )

def _get_logs(report: CreditReport, url: str):
    logs = IncomingAPICallLog.objects.filter(
        provider=report.service.provider,
        service=report.service.tp,
        api_url=url,
        status=IncomingAPICallLog.STATUS.success,
    )

    if report.start_date:
        logs = logs.filter(created_at__gte=report.start_date)
    if report.end_date:
        logs = logs.filter(created_at__lt=report.end_date)

    logs = logs.values(
        'user__national_code',
        'created_at',
        'request_body',
        'user_service__id',
        'user_service__initial_debt',
        'user_service__current_debt',
        'user_service__principal',
        'user_service__installment_amount',
        'user_service__installment_period',
        'user_service__provider_fee_amount',
        'user_service__account_number',
        'user_service__created_at',
        'user_service__status',
        'user_service__closed_at',
    ).order_by('created_at')
    return logs


def _is_log_corresponding_to_settlement(log, settlement):
    created_at_diff = abs(log['created_at'] - settlement.created_at)
    if (
        int(log['request_body'].get('amount')) != int(settlement.amount)
        or log['user_service__id'] != settlement.user_service.id
        or log['created_at'] < settlement.created_at
        or created_at_diff > timedelta(seconds=1)
    ):
        return False
    return True


def _attach_report_as_file(
    report: CreditReport, headers: list, rows: list, file_name: str, attachment_type: ReportAttachment.AttachmentType
):
    csv_content = _generate_csv_content(headers, rows)
    ReportAttachment.objects.create(
        report=report, attachment_type=attachment_type, file=ContentFile(csv_content, name=file_name)
    )


def _generate_csv_content(headers: List[str], rows: List[List[Any]]) -> str:
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

    writer.writerow(headers)
    writer.writerows(rows)

    csv_content = csv_buffer.getvalue()
    csv_buffer.close()

    return csv_content


def _get_settlements(report: CreditReport, logs):
    user_service_ids = [log['user_service__id'] for log in logs if log['user_service__id'] is not None]

    settlements_qs = SettlementTransaction.objects.filter(user_service_id__in=user_service_ids)
    if report.start_date:
        settlements_qs = settlements_qs.filter(created_at__gte=report.start_date)
    if report.end_date:
        settlements_qs = settlements_qs.filter(created_at__lt=report.end_date)

    orders_qs = Order.objects.only(
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

    settlements = (
        settlements_qs.select_related('user_service')
        .prefetch_related(Prefetch('orders', queryset=orders_qs))
        .order_by('created_at')
    )

    return settlements


def _build_settlement_logs(settlements, logs, mismatch_only=False):
    settlement_logs = []

    if len(logs) != len(settlements):
        return settlement_logs

    for index, settlement in enumerate(settlements):
        log = logs[index]
        if not _is_log_corresponding_to_settlement(log, settlement):
            return settlement_logs

        us = settlement.user_service

        settlement_amount = int(settlement.amount)
        installment = int(us.installment_amount or 0)
        provider_fee = int(us.provider_fee_amount or 0)
        settlement_amount_is_ok = settlement_amount == installment or settlement_amount == installment + provider_fee

        if mismatch_only and settlement_amount_is_ok:
            continue

        base_row = [
            jdatetime.datetime.fromgregorian(datetime=settlement.created_at).strftime('%Y-%m-%d'),
            log.get('user__national_code'),
            us.account_number,
            int(us.principal or 0),
            int(us.initial_debt),
            int(us.current_debt),
            installment,
            int(us.installment_period or 0),
            provider_fee,
            UserService.Status(us.status).name,
            log['request_body'].get('trackId', ''),
            settlement_amount,
            SettlementTransaction.STATUS._display_map.get(settlement.status, ''),
            settlement_amount_is_ok,
        ]

        related_orders = settlement.orders.all()
        if related_orders:
            for order in related_orders:
                row = base_row + [
                    Currencies._display_map.get(order.src_currency),
                    order.price,
                    order.amount,
                    order.status,
                    order.matched_amount,
                    order.matched_total_price,
                    order.fee,
                    order.matched_total_price - order.fee,
                ]
                settlement_logs.append(tuple(row))
        else:
            settlement_logs.append(tuple(base_row + [''] * 8))

    return settlement_logs
