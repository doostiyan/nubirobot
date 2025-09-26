import datetime
from dataclasses import asdict
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q

from exchange.asset_backed_credit.exceptions import (
    ReconAlreadyProcessedError,
    ServiceNotFoundError,
    SettlementReconError,
)
from exchange.asset_backed_credit.models import DebitSettlementTransaction, Service
from exchange.asset_backed_credit.models.recon import Recon, SettlementRecon
from exchange.asset_backed_credit.types import ReconTransactionData
from exchange.base.calendar import get_earliest_time, ir_now
from exchange.base.decorators import measure_time_cm
from exchange.base.models import Settings

SETTLEMENT_RECON_CHUNK_SIZE = 1000


@measure_time_cm(metric='abc_debit_recon')
def reconcile(recon_date: Optional[datetime.datetime] = None):
    recon_date = recon_date or get_earliest_time(ir_now() - datetime.timedelta(days=1))
    recon = _get_or_create_recon(recon_date)

    if recon.status == Recon.Status.INITIATED:
        run_ftp_process(recon)
    if recon.status == Recon.Status.FILE_TRANSFERRED:
        evaluate_settlements(recon)
    if recon.status == Recon.Status.EVALUATED:
        process_settlements(recon)


def _get_or_create_recon(recon_date: datetime.datetime) -> Recon:
    service = Service.get_matching_active_service(
        provider=settings.ABC_ACTIVE_DEBIT_SERVICE_PROVIDER_ID, tp=Service.TYPES.debit
    )
    if not service:
        raise ServiceNotFoundError(message='No active debit service found!')

    if Recon.objects.filter(
        service=service, recon_date=recon_date, status=Recon.Status.PROCESSED, closed_at__isnull=False
    ).exists():
        raise ReconAlreadyProcessedError()

    recon, _ = Recon.objects.get_or_create(
        service=service,
        recon_date=recon_date,
    )
    return recon


@measure_time_cm(metric='abc_debit_recon_ftp_process')
def run_ftp_process(recon: Recon) -> None:
    if not Settings.get_flag('abc_debit_recon_ftp_process_enabled'):
        return

    file_name = f'PAR{recon.recon_date.strftime("%Y%m%d")}.txt'
    file_path = f'/{recon.recon_date.strftime("%Y-%m-%d")}/{file_name}'
    content = _read_file_content(file_path)

    recon.file.save(file_name, ContentFile(content))
    Recon.objects.filter(pk=recon.pk, status=Recon.Status.INITIATED).update(status=Recon.Status.FILE_TRANSFERRED)
    recon.refresh_from_db()


def _read_file_content(file_path) -> str:
    """
    file_path format is [ABV]YYMMDD.txt ABV examples are NOV (pardakht novin), PAR (parsian)
    """
    from exchange.base.storages import SftpProperties, read_file_from_sftp

    host = settings.ABC_DEBIT_RECON_SFTP_PROPS['host']
    port = settings.ABC_DEBIT_RECON_SFTP_PROPS['port']
    username = settings.ABC_DEBIT_RECON_SFTP_PROPS['username']
    password = settings.ABC_DEBIT_RECON_SFTP_PROPS['password']
    base_dir = settings.ABC_DEBIT_RECON_SFTP_PROPS['base_dir']

    return read_file_from_sftp(sftp_props=SftpProperties(host, port, username, password, base_dir + file_path))


@transaction.atomic
@measure_time_cm(metric='abc_debit_recon_settlements_evaluation')
def evaluate_settlements(recon: Recon) -> None:
    if not Settings.get_flag('abc_debit_recon_settlement_evaluation_enabled'):
        return

    normalized_data = normalize_data(recon)
    if not normalized_data:
        return

    filter_query = Q(
        created_at__gte=recon.recon_date - datetime.timedelta(days=3),
        created_at__lt=recon.recon_date,
        status__in=[
            DebitSettlementTransaction.STATUS.unknown_confirmed,
            DebitSettlementTransaction.STATUS.unknown_rejected,
        ],
    )
    exclude_query = Q(settlementrecon__status=SettlementRecon.Status.SUCCESS)
    settlements = (
        DebitSettlementTransaction.objects.filter(filter_query)
        .exclude(exclude_query)
        .select_for_update(of=('self',), no_key=True)
    )

    settlement_recons: List[SettlementRecon] = []

    for settlement in settlements:
        settlement_recon = SettlementRecon(recon=recon, settlement=settlement)
        settlement_key = _get_settlement_key(settlement.pan, settlement.terminal_id, settlement.trace_id)
        if settlement_key not in normalized_data:
            settlement_recons.append(settlement_recon)
            continue

        recon_transaction_data = normalized_data[settlement_key]
        settlement_recon_status, error_description = _do_compare(settlement, recon_transaction_data)
        if settlement_recon_status != SettlementRecon.Status.SUCCESS:
            settlement_recon.description = error_description
        settlement_recon.status = settlement_recon_status
        settlement_recons.append(settlement_recon)
        del normalized_data[settlement_key]

    SettlementRecon.objects.bulk_create(
        settlement_recons,
        update_conflicts=True,
        unique_fields=['settlement'],
        update_fields=['recon', 'description', 'status'],
        batch_size=SETTLEMENT_RECON_CHUNK_SIZE,
    )

    settlement_recons = []

    for _, recon_transaction_data in normalized_data.items():
        settlement_recon = SettlementRecon(
            recon=recon,
            status=SettlementRecon.Status.NOT_FOUND,
            extra_info=asdict(recon_transaction_data),
            description=f'equivalent settlement for trace_id: {recon_transaction_data.trace_id} not found!',
        )
        settlement_recons.append(settlement_recon)

    SettlementRecon.objects.bulk_create(
        settlement_recons,
        batch_size=SETTLEMENT_RECON_CHUNK_SIZE,
    )

    Recon.objects.filter(pk=recon.pk, status=Recon.Status.FILE_TRANSFERRED).update(status=Recon.Status.EVALUATED)
    recon.refresh_from_db()


def normalize_data(recon: Recon) -> Dict[str, ReconTransactionData]:
    with recon.file.open('r') as file:
        transactions = file.readlines()

    normalized_transactions = {}

    for trx in transactions:
        trx = trx.rstrip()
        if not trx or len(trx) == 0:
            raise SettlementReconError()
        trx = _normalize_transaction(trx.strip())
        if trx.trace_id in normalized_transactions:
            raise SettlementReconError()
        key = _get_settlement_key(trx.pan, trx.terminal_id, trx.trace_id)
        normalized_transactions[key] = trx

    return normalized_transactions


def _get_settlement_key(pan: str, terminal_id: str, trace_id: str) -> str:
    return pan + '-' + terminal_id + '-' + trace_id


def _normalize_transaction(record: str):
    record_segments = record.split('/')
    transaction_tag = record_segments[0]

    return ReconTransactionData(
        date=transaction_tag[:6].strip(),
        time=transaction_tag[6:12].strip(),
        pos_condition_code=transaction_tag[12:14].strip(),
        trace_id=transaction_tag[14:20].strip(),
        account_number=record_segments[4].strip(),
        amount=int(record_segments[5].strip()),
        amount_type=record_segments[6].strip(),
        pr_code=record_segments[7].strip(),
        terminal_id=record_segments[9].strip(),
        acquirer_institution_code=record_segments[15].strip(),
        pan=record_segments[17].strip(),
        acquirer_institution=record_segments[23].strip(),
        issuer_institution=record_segments[24].strip(),
    )


def _do_compare(
    settlement: DebitSettlementTransaction, recon_transaction_data: ReconTransactionData
) -> Tuple[SettlementRecon.Status, Optional[str]]:
    if settlement.amount != recon_transaction_data.amount:
        error_description = (
            f'invalid amount -> settlement_amount: {settlement.amount}, recon_amount: {recon_transaction_data.amount}'
        )
        return SettlementRecon.Status.INVALID_AMOUNT, error_description
    if settlement.status != DebitSettlementTransaction.STATUS.unknown_confirmed:
        error_description = f'invalid status -> settlement_status: {settlement.status}'
        # TODO: we should know about the adjusted transactions
        return SettlementRecon.Status.INVALID_STATUS, error_description

    return SettlementRecon.Status.SUCCESS, None


@transaction.atomic
@measure_time_cm(metric='abc_debit_recon_settlements_process')
def process_settlements(recon: Recon) -> None:
    if not Settings.get_flag('abc_debit_recon_settlement_process_enabled'):
        return

    _reconcile_settlements(recon)
    _reverse_old_settlements(recon)
    Recon.objects.filter(pk=recon.pk, status=Recon.Status.EVALUATED, closed_at__isnull=True).update(
        status=Recon.Status.PROCESSED, closed_at=ir_now()
    )


def _reconcile_settlements(recon: Recon) -> None:
    settlement_ids = SettlementRecon.objects.filter(recon=recon, status=SettlementRecon.Status.SUCCESS).values_list(
        'settlement_id', flat=True
    )
    filter_query = Q(
        created_at__gte=recon.recon_date - datetime.timedelta(days=3),
        created_at__lt=recon.recon_date,
        status__in=[
            DebitSettlementTransaction.STATUS.unknown_confirmed,
            DebitSettlementTransaction.STATUS.unknown_rejected,
        ],
    )
    DebitSettlementTransaction.objects.filter(Q(id__in=settlement_ids) & filter_query).update(
        status=DebitSettlementTransaction.STATUS.confirmed
    )


def _reverse_old_settlements(recon: Recon) -> None:
    from exchange.asset_backed_credit.tasks import task_reverse_debit_payment

    if not Settings.get_flag('abc_debit_recon_settlement_process_reverse_enabled'):
        return

    settlements = DebitSettlementTransaction.objects.filter(
        created_at__lt=recon.recon_date - datetime.timedelta(days=3),
        status=DebitSettlementTransaction.STATUS.unknown_confirmed,
    )

    for settlement in settlements.iterator(chunk_size=SETTLEMENT_RECON_CHUNK_SIZE):
        task_reverse_debit_payment.delay(settlement.id)

    # TODO: in future we should settle unknown_rejected transactions or not found
