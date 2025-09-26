from decimal import Decimal

from django.db import transaction

from exchange.accounts.models import UserSms
from exchange.asset_backed_credit.exceptions import SettlementNeedsLiquidation
from exchange.asset_backed_credit.externals.notification import notification_provider
from exchange.asset_backed_credit.models import Service, SettlementTransaction
from exchange.asset_backed_credit.services.wallet.balance import get_total_wallet_balance
from exchange.base.formatting import format_money
from exchange.base.models import RIAL, Currencies


def settle_pending_settlements():
    from exchange.asset_backed_credit.tasks import task_settlement_settle_user

    pending_settlements = (
        SettlementTransaction.get_pending_user_settlements().order_by('created_at').values_list('id', flat=True)
    )
    for settlement_id in pending_settlements:
        task_settlement_settle_user.delay(settlement_id)


def settle(settlement_id: int):
    try:
        with transaction.atomic():
            settlement = (
                SettlementTransaction.objects.select_related('user_service', 'user_service__service')
                .select_for_update(of=('self', 'user_service'), no_key=True)
                .get(id=settlement_id)
            )

            if settlement.user_withdraw_transaction is not None:
                return

            settlement.create_transactions()
            wallet_rial_balance = get_total_wallet_balance(
                user_id=settlement.user_service.user.uid,
                exchange_user_id=settlement.user_service.user.id,
                wallet_type=Service.get_related_wallet_type(settlement.user_service.service.tp),
                dst_currency=RIAL,
            )
            settlement.update_remaining_rial_wallet_balance(wallet_rial_balance)
        _send_notification(settlement)
    except SettlementNeedsLiquidation:
        from exchange.asset_backed_credit.tasks import task_settlement_liquidation

        task_settlement_liquidation.delay(settlement_id)


def _send_notification(settlement: SettlementTransaction):
    if not settlement.transaction_datetime:
        return

    user = settlement.user_service.user
    provider_name = settlement.user_service.service.get_provider_display()
    service_name = settlement.user_service.service.get_tp_display()
    service_type = settlement.user_service.service.tp
    amount = format_money(money=settlement.amount, currency=Currencies.rls)

    notif_text = (
        f'مقدار '
        f'{amount}'
        f' تومان از وثیقه‌ی '
        f'{service_name}'
        f' به‌درخواست '
        f'{provider_name}'
        f' تبدیل و تسویه شد.'
    )

    notification_provider.send_notif(user=user, message=notif_text)

    if service_type == Service.TYPES.debit:
        user_first_name = user.first_name if user.first_name else 'کاربر'
        remaining_amount = format_money(
            money=Decimal(settlement.remaining_rial_wallet_balance), currency=Currencies.rls
        )
        notification_provider.send_sms(
            user=user,
            text=user_first_name + '\n' + amount + '\n' + remaining_amount,
            tp=UserSms.TYPES.abc_debit_settlement,
            template=UserSms.TEMPLATES.abc_debit_settlement,
        )
    else:
        notification_provider.send_sms(
            user=user,
            tp=UserSms.TYPES.abc_liquidate_by_provider,
            text=amount + '\n' + service_name + '\n' + provider_name,
            template=UserSms.TEMPLATES.abc_liquidate_by_provider,
        )

    if service_type != Service.TYPES.debit and user.is_email_verified:
        notification_provider.send_email(
            to_email=user.email,
            template='abc/abc_liquidate_by_provider',
            data={
                'provider_name': provider_name,
                'service_name': service_name,
                'amount': amount,
            },
        )
