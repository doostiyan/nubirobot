import uuid
from functools import lru_cache
from typing import Optional

from django.db import transaction

from exchange.asset_backed_credit.exceptions import (
    CardExpiredError,
    CardInactiveError,
    CardNotFoundError,
    CardRestrictedError,
    DebitCardTransactionServiceTemporaryUnavailable,
    InvalidIPError,
    ServiceMismatchError,
    SettlementError,
)
from exchange.asset_backed_credit.models import (
    Card,
    CardTransactionFeeSetting,
    CardTransactionLimit,
    DebitSettlementTransaction,
    IncomingAPICallLog,
    InternalUser,
    Service,
    UserService,
)
from exchange.asset_backed_credit.services.debit.limits import check_card_transaction_limits
from exchange.asset_backed_credit.services.providers.provider_manager import provider_manager
from exchange.asset_backed_credit.services.user_service import check_margin_ratio
from exchange.asset_backed_credit.types import (
    MTI,
    TransactionRequest,
    TransactionResponse,
    bank_switch_status_code_mapping,
)
from exchange.base.models import Settings


@transaction.atomic
def create_transaction(request: TransactionRequest, client_ip: str) -> TransactionResponse:
    card = get_card(request.pan, client_ip)

    mti = request.mti
    if mti == MTI.REQUESTED:
        status_code = _initiate_payment(request, card)
    elif mti == MTI.CONFIRMED:
        status_code = _confirm_payment(request)
    elif mti == MTI.REJECTED:
        status_code = _reject_payment(request, card)
    else:
        raise NotImplementedError()

    return TransactionResponse(
        status=status_code,
        pan=request.pan,
        rid=request.rid,
        rrn=request.rrn,
        trace=request.trace_id,
    )


def get_card(pan: str, client_ip: str, skip_status=False) -> Card:
    service = get_service(client_ip)
    card = (
        Card.objects.select_for_update(of=('self',), no_key=True)
        .filter(pan=pan, user_service__service=service)
        .select_related('user', 'user_service')
        .first()
    )
    if card is None:
        raise CardNotFoundError

    if not skip_status:
        check_card_status(card)

    return card


def check_card_status(card: Card):
    if card.status == Card.STATUS.restricted:
        raise CardRestrictedError
    if card.status == Card.STATUS.expired:
        raise CardExpiredError
    if card.status != Card.STATUS.activated:
        raise CardInactiveError


@lru_cache(maxsize=8)
def get_service(client_ip: str) -> Service:
    provider = provider_manager.get_provider_by_ip(client_ip)
    service = Service.get_matching_active_service(provider.id, Service.TYPES.debit)

    if not service:
        raise ServiceMismatchError(f'The selected service does not exist for debit provider {provider.id}')

    return service


def _initiate_payment(request: TransactionRequest, card: Card) -> str:
    if not Settings.get_flag('abc_debit_card_initiate_transaction_enabled', default='yes'):
        raise DebitCardTransactionServiceTemporaryUnavailable

    amount = request.amount

    check_card_transaction_limits(card, amount)

    existing_settlement = DebitSettlementTransaction.objects.filter(
        pan=request.pan, trace_id=request.trace_id, terminal_id=request.terminal_id
    ).first()
    if existing_settlement is not None:
        if existing_settlement.status == DebitSettlementTransaction.STATUS.initiated:
            return bank_switch_status_code_mapping['DUPLICATE_TRANSACTION']
        else:
            return bank_switch_status_code_mapping['UNAUTHORIZED_TRANSACTION']

    InternalUser.get_lock(card.user.pk)
    check_margin_ratio(user=card.user, amount=amount, service_type=Service.TYPES.debit)

    CardTransactionLimit.add_card_transaction(card, amount)
    fee_amount = CardTransactionFeeSetting.get_fee_amount(level=card.setting, amount=amount)
    card.user_service.update_debt(amount + fee_amount)
    DebitSettlementTransaction.create(
        user_service=card.user_service,
        amount=amount,
        fee_amount=fee_amount,
        status=DebitSettlementTransaction.STATUS.initiated,
        pan=request.pan,
        rrn=request.rrn,
        trace_id=request.trace_id,
        terminal_id=request.terminal_id,
        rid=request.rid,
    )
    return bank_switch_status_code_mapping['SUCCESS']


def _confirm_payment(request: TransactionRequest) -> str:
    existing_settlement = (
        DebitSettlementTransaction.objects.filter(
            pan=request.pan, trace_id=request.trace_id, terminal_id=request.terminal_id
        )
        .select_for_update(of=('self',), no_key=True)
        .first()
    )
    if existing_settlement is None:
        raise SettlementError()

    if (
        existing_settlement.status == DebitSettlementTransaction.STATUS.confirmed
        or existing_settlement.status == DebitSettlementTransaction.STATUS.unknown_confirmed
    ):
        return bank_switch_status_code_mapping['DUPLICATE_TRANSACTION']
    if existing_settlement.status == DebitSettlementTransaction.STATUS.unknown_rejected:
        return bank_switch_status_code_mapping['UNAUTHORIZED_TRANSACTION']

    existing_settlement.confirm(request.amount)
    return bank_switch_status_code_mapping['SUCCESS']


def _reject_payment(request: TransactionRequest, card: Card) -> str:
    existing_settlement = (
        DebitSettlementTransaction.objects.filter(
            pan=request.pan, trace_id=request.trace_id, terminal_id=request.terminal_id
        )
        .select_for_update(of=('self',), no_key=True)
        .first()
    )
    if existing_settlement is None:
        raise SettlementError()

    if existing_settlement.status == DebitSettlementTransaction.STATUS.unknown_rejected:
        return bank_switch_status_code_mapping['DUPLICATE_TRANSACTION']
    if (
        existing_settlement.status == DebitSettlementTransaction.STATUS.confirmed
        or existing_settlement.status == DebitSettlementTransaction.STATUS.unknown_confirmed
    ):
        return bank_switch_status_code_mapping['UNAUTHORIZED_TRANSACTION']

    CardTransactionLimit.add_card_transaction(card, -request.amount)
    card.user_service.update_current_debt(-(request.amount + existing_settlement.fee_amount))
    existing_settlement.reject(request.amount)
    return bank_switch_status_code_mapping['SUCCESS']


def reverse_payment(settlement_id: int) -> DebitSettlementTransaction:
    settlement = (
        DebitSettlementTransaction.objects.select_for_update(
            of=(
                'self',
                'user_service',
            ),
            no_key=True,
        )
        .select_related('user_service')
        .get(id=settlement_id)
    )
    settlement.create_reverse_transactions()
    settlement.user_service.update_current_debt(-settlement.amount)
    return settlement


def log(client_ip: str, path: str, pan: str, request_data: dict, response_data: dict, response_status_code: int):
    service: Optional[Service] = None
    user_service: Optional[UserService] = None
    try:
        service = get_service(client_ip)
        if pan:
            card = get_card(pan, client_ip, skip_status=True)
            user_service = card.user_service
        else:
            user_service = None
    except (InvalidIPError, ServiceMismatchError, CardNotFoundError):
        pass
    status = _get_api_call_status(response_data)
    IncomingAPICallLog.create(
        api_url=path,
        status=status,
        service=service.tp if service else None,
        user=user_service.user if user_service else None,
        internal_user=user_service.internal_user if user_service else None,
        user_service=user_service if user_service else None,
        response_code=response_status_code,
        provider=service.provider if service else None,
        uid=uuid.uuid4(),
        request_body=request_data,
        response_body=response_data,
    )


def _get_api_call_status(response_data):
    return (
        IncomingAPICallLog.STATUS.success
        if 'RespCode' in response_data and response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']
        else IncomingAPICallLog.STATUS.failure
    )
