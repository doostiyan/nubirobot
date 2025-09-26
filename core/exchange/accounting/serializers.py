from exchange.accounting.models import DepositSystemBankAccount
from exchange.base.serializers import register_serializer


@register_serializer(model=DepositSystemBankAccount)
def serialize_deposit_system_bank_account(account, opts=None):
    iban = account.iban_number
    if iban.startswith('IR') and len(iban) == 26:
        iban = f'{iban[:7]} **** {iban[-4:]}'
    else:
        iban = '****'
    return {
        'id': account.pk,
        'shaba': iban,
        'bank': account.get_bank_id_display(),
    }
