""" Shetab Module Serializers """
from typing import Union

from exchange.base.serializers import register_serializer
from exchange.shetab.models import JibitPaymentId, ShetabDeposit, VandarPaymentId


@register_serializer(model=ShetabDeposit)
def serialize_shetab_deposit(shetab_deposit, opts):
    statuses = {102030: 'shetabInvalidCard', 102040: 'shetabRefunded', 1: 'success', 0: 'new'}
    user = opts.get('user') or shetab_deposit.user
    return {
        'id': shetab_deposit.pk,
        'username': user.username,
        'amount': shetab_deposit.amount,
        'fee': shetab_deposit.fee,
        'nextpay_id': shetab_deposit.nextpay_id,
        'status': statuses.get(shetab_deposit.status_code, 'failed'),
        'gateway': shetab_deposit.get_broker_display(),
        'next': shetab_deposit.get_pay_redirect_url(),
        'depositType': 'shetabDeposit',
        'date': shetab_deposit.effective_date,
        'transaction': shetab_deposit.transaction,
        'confirmed': shetab_deposit.is_status_done,
    }

@register_serializer(model=JibitPaymentId)
@register_serializer(model=VandarPaymentId)
def serialize_deposit_payment_id(payment: Union[JibitPaymentId, VandarPaymentId], opts=None):
    return {
        'id': payment.id,
        'accountId': payment.bank_account.id,
        'bank': payment.bank_account.get_bank_id_display(),
        'iban': payment.bank_account.shaba_number,
        'destinationBank': payment.deposit_account.get_bank_display(),
        'destinationIban': payment.deposit_account.iban,
        'destinationOwnerName': payment.deposit_account.owner_name,
        'destinationAccountNumber': payment.deposit_account.account_number,
        'paymentId': payment.payment_id,
        'type': payment.type,
    }
