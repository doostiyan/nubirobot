from django_ratelimit.decorators import ratelimit

from exchange.accounting.models import DepositSystemBankAccount
from exchange.base.api import api


@ratelimit(key='user_or_ip', rate='60/1m', block=True)
@api
def deposit_system_bank_account(request):

    return {
        'status': 'ok',
        'accounts': DepositSystemBankAccount.objects.filter(is_private=False),
    }
