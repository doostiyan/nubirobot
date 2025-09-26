from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

from django.conf import settings
from django.contrib.postgres.aggregates import ArrayAgg
from django.db import transaction
from django.db.models import F, Sum

from exchange.asset_backed_credit.exceptions import InternalAPIError
from exchange.asset_backed_credit.externals.withdraw import RialWithdrawRequestAPI, RialWithdrawRequestSchema
from exchange.asset_backed_credit.models import SettlementTransaction
from exchange.asset_backed_credit.models.withdraw_request import ProviderWithdrawRequestLog
from exchange.asset_backed_credit.services.providers.provider import Provider
from exchange.asset_backed_credit.services.providers.provider_manager import ProviderManager
from exchange.base.logging import report_event
from exchange.base.models import Settings
from exchange.wallet.models import WithdrawRequest as ExchangeWithdrawRequest


@dataclass
class WithdrawInfo:
    provider: Provider
    amount: Decimal
    settlement_ids: List[int]


def create_provider_withdraw_requests():
    provider_settlements = _get_provider_settlements()
    for provider_settlement in provider_settlements:
        with transaction.atomic():
            withdraw_info = _get_withdraw_info(provider_settlement)
            if withdraw_info is None:
                continue

            if Settings.get_flag('abc_use_rial_withdraw_request_internal_api'):
                _create_withdraw_request_by_internal_api(withdraw_info)
            else:
                _create_and_verify_withdraw_request(withdraw_info)


def _get_provider_settlements():
    return (
        SettlementTransaction.objects.filter(
            user_withdraw_transaction__isnull=False,
            provider_deposit_transaction__isnull=False,
        )
        .exclude(provider_withdraw_request_log__isnull=False)
        .exclude(provider_withdraw_requests__isnull=False)
        .annotate(
            provider=F('user_service__service__provider'),
        )
        .values('provider')
        .annotate(
            total_amount=Sum('amount'),
            transaction_list=ArrayAgg('id'),
        )
    )


def _get_withdraw_info(settlement_item: Dict) -> Optional[WithdrawInfo]:
    provider_id = settlement_item.get('provider')
    amount = settlement_item.get('total_amount')
    if not provider_id or not amount or amount <= 0:
        report_event(
            message='ABC: provider or amount is not acceptable to create withdraw request',
            extras={'provider_id': provider_id, 'amount': amount},
        )
        return None

    provider = _get_provider_by_id(provider_id)
    if not provider:
        return None

    return WithdrawInfo(provider=provider, amount=amount, settlement_ids=settlement_item['transaction_list'])


def _create_withdraw_request_by_internal_api(withdraw_info: WithdrawInfo):
    withdraw_log = ProviderWithdrawRequestLog.objects.create(
        provider=withdraw_info.provider.id, amount=withdraw_info.amount
    )

    SettlementTransaction.objects.filter(id__in=withdraw_info.settlement_ids).update(
        provider_withdraw_request_log=withdraw_log
    )


def _create_and_verify_withdraw_request(withdraw_info: WithdrawInfo):
    withdraw_requests = _create_withdraw_request(provider=withdraw_info.provider, amount=withdraw_info.amount)
    _verify_requests(withdraw_requests)

    for settlement in SettlementTransaction.objects.filter(id__in=withdraw_info.settlement_ids):
        settlement.provider_withdraw_requests.add(*withdraw_requests)


def _create_withdraw_request(provider: Provider, amount: Decimal) -> List[ExchangeWithdrawRequest]:
    _amount = amount if amount < 1_000_000_000_0 else 950_000_000_0

    withdraw_request: ExchangeWithdrawRequest = ExchangeWithdrawRequest.objects.create(
        amount=_amount,
        wallet=provider.rial_wallet,
        explanations=_get_explanation(provider=provider),
        target_account=provider.bank_account,
    )
    withdraw_request.amount = amount
    return withdraw_request.split_if_needed()


def _verify_requests(withdraw_requests: List[ExchangeWithdrawRequest]):
    for withdraw_request in withdraw_requests:
        withdraw_request.do_verify()


def settle_provider_withdraw_request_logs():
    for withdraw_request in ProviderWithdrawRequestLog.objects.filter(status=ProviderWithdrawRequestLog.STATUS_CREATED):
        provider = _get_provider_by_id(withdraw_request.provider)
        if not provider:
            continue

        try:
            result = RialWithdrawRequestAPI().request(
                data=RialWithdrawRequestSchema(
                    user_id=provider.account.uid,
                    amount=withdraw_request.amount,
                    iban=provider.bank_account.shaba_number,
                    explanation=_get_explanation(provider=provider),
                ),
                idempotency=withdraw_request.uuid,
            )
        except InternalAPIError:
            continue

        withdraw_request.external_id = result.id
        withdraw_request.status = ProviderWithdrawRequestLog.STATUS_DONE
        withdraw_request.save(update_fields=['external_id', 'status', 'updated_at'])


def _get_explanation(provider) -> str:
    exp = 'تسویه نهایی با سرویس دهنده'
    f'({provider.name})'
    f'با شناسه‌ی '
    f'{provider.id}'
    f' در سرویس اعتبار ریالی'

    return exp


def _get_provider_by_id(provider_id) -> Optional[Provider]:
    provider = ProviderManager.get_provider_by_id(provider_id)

    if not provider:
        report_event('ABC: ProviderNotFound', extras={'provider_id': provider_id})
        return None

    if not provider.bank_account or not provider.bank_account.shaba_number:
        if settings.IS_PROD:
            report_event('ABC: ProviderBankAccountNotFound', extras={'provider_id': provider_id})
        return None

    return provider
