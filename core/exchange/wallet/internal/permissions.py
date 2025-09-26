from exchange.accounts.constants import SYSTEM_USER_IDS
from exchange.base.api import NobitexAPIError
from exchange.base.internal.services import Services
from exchange.wallet.models import Transaction, Wallet

BULK_TRANSFER_PERMISSIONS = {
    'allowed_src_types': {
        Services.ABC: {Wallet.WALLET_TYPE.credit, Wallet.WALLET_TYPE.debit},
    },
}

ALLOWED_SRC_TYPES = {
    Services.ABC: (Wallet.WALLET_TYPE.credit,),
}

ALLOWED_DST_TYPES = {
    Services.ABC: (Wallet.WALLET_TYPE.spot,),
}

ALLOWED_SYSTEM_USER = {
    Services.ABC: (SYSTEM_USER_IDS.system_abc_insurance_fund,),
}

ALLOWED_TX_TYPE = {
    Services.ABC: (Transaction.TYPE.subset('asset_backed_credit')),
}

ALLOWED_TX_REF_MODULES = {
    Services.ABC: (
        'AssetBackedCreditUserSettlement',
        'AssetBackedCreditProviderSettlement',
        'AssetBackedCreditInsuranceSettlement',
    ),
}


ALLOWED_NEGATIVE_BALANCE_WALLETS = {}


def check_bulk_transfer_permission(service: Services, src_type: Wallet.WALLET_TYPE) -> None:
    if src_type not in BULK_TRANSFER_PERMISSIONS['allowed_src_types'].get(service, ()):
        raise NobitexAPIError(
            status_code=403,
            message='PermissionDenied',
            description=f'Service {service.upper()} is not allowed to transfer funds from wallet'
            f' {Wallet.WALLET_TYPE._display_map[src_type]}',
        )


def check_service_wallet_permission(service, wallet_type):
    if wallet_type not in ALLOWED_SRC_TYPES.get(service, ()):
        raise NobitexAPIError(
            status_code=403,
            message='PermissionDenied',
            description=f'Service {service.upper()} does not have access to wallet with type'
            f' {Wallet.WALLET_TYPE._display_map[wallet_type]}',
        )
