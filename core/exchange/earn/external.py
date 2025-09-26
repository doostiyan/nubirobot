from decimal import Decimal
from uuid import UUID

import requests
from django.conf import settings

from exchange.asset_backed_credit.models.wallet import Wallet as ABCWallet
from exchange.asset_backed_credit.services.wallet.wallet import WalletService as ABCWalletService
from exchange.base.logging import report_event
from exchange.base.models import Settings

NOBITEX_BASE_URL = 'https://api.nobitex.ir' if settings.IS_PROD else 'https://testnetapi.nobitex.ir'


def get_user_abc_debit_wallets_balances(user_id: UUID) -> dict:
    if Settings.get_flag('earn_get_abc_wallets_by_internal_api'):
        return _get_user_abc_debit_wallets_balances_by_internal_api(user_id=user_id)

    wallets = ABCWalletService.get_user_wallets_with_balances(user_id=user_id, wallet_type=ABCWallet.WalletType.DEBIT)
    return {wallet.currency: wallet.balance for wallet in wallets}


def _get_user_abc_debit_wallets_balances_by_internal_api(user_id: UUID) -> dict:
    url = NOBITEX_BASE_URL + f'/internal/asset-backed-credit/wallets/debit/balances?user_id={user_id}'
    headers = {'Authorization': settings.CORE_INTERNAL_API_JWT_TOKEN, 'Content-Type': 'application/json'}

    try:
        response = requests.get(url, headers=headers, timeout=30)
    except Exception as e:
        report_event('InternalABCWalletBalanceListError', extras={'error': str(e)})
        return {}

    if not response.ok:
        report_event('InternalABCWalletBalanceListError', extras={'response': response.json()})
        return {}

    wallets = response.json().get('wallets', {})
    return {int(currency): Decimal(balance) for currency, balance in wallets.items()}
