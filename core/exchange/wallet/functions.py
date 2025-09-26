from typing import List, Tuple

from django.db.transaction import atomic

from exchange.asset_backed_credit.currencies import ABCCurrencies
from exchange.asset_backed_credit.models.wallet import Wallet as ABCWallet
from exchange.audit.models import ExternalWallet, ExternalWithdraw
from exchange.base.api import NobitexAPIError
from exchange.base.helpers import get_symbol_from_currency_code
from exchange.base.logging import report_event
from exchange.base.models import MARGIN_CURRENCIES, Currencies, get_currency_codename
from exchange.base.money import money_is_zero
from exchange.base.parsers import WalletBulkTransferData
from exchange.blockchain.explorer import BlockchainExplorer
from exchange.wallet.exceptions import TransferException
from exchange.wallet.models import AvailableHotWalletAddress, Wallet, WalletBulkTransferRequest
from exchange.wallet.types import TransferResult


def external_withdraw_log(currency):
    network = 'TRX' if currency == Currencies.trx else 'BNB'
    wallet_address = AvailableHotWalletAddress.objects.filter(currency=currency)
    print('wallet_address', wallet_address)
    for wallet in wallet_address:
        transactions_info = {}
        try:
            transactions_info = BlockchainExplorer.get_wallet_transactions(wallet.address, currency, network=network)
        except Exception as e:
            print('Failed to get transactions from API server: {}'.format(str(e)))
            report_event('Failed to get transactions from API server: {}'.format(str(e)),
                         level='error', module='transactions', category='general',
                         runner='withdraw', details='Address: {}'.format(wallet.address)
                         )
        if not transactions_info:
            continue
        for tx_info in transactions_info:
            if tx_info.address != wallet.address:
                continue
            tx_hash = tx_info.hash
            created_at = tx_info.timestamp
            from_addr = tx_info.address
            amount = tx_info.value
            tag = tx_info.tag
            try:
                ExternalWithdraw.objects.get(currency=currency, tx_hash=tx_hash, destination=from_addr)
            except ExternalWithdraw.DoesNotExist:
                ExternalWithdraw.objects.create(
                    created_at=created_at,
                    source=ExternalWallet.objects.get_or_create(
                        name='Hot {} {}'.format(get_currency_codename(currency).upper(), from_addr),
                        currency=currency,
                        tp=ExternalWallet.TYPES.hot,
                    )[0],
                    destination=from_addr,
                    tx_hash=tx_hash,
                    tag=tag,
                    currency=currency,
                    amount=amount,
                )


@atomic(savepoint=False)
def transfer_balance(user, currency, amount, src_type, dst_type):
    if dst_type == Wallet.WALLET_TYPE.credit and currency not in ABCCurrencies.get_active_currencies():
        raise TransferException(
            'UnsupportedCoin',
            f'Cannot transfer {get_symbol_from_currency_code(currency)} to credit wallet',
        )

    if dst_type == Wallet.WALLET_TYPE.debit and currency not in ABCCurrencies.get_active_currencies(
        ABCWallet.WalletType.DEBIT
    ):
        raise TransferException(
            'UnsupportedCoin',
            f'Cannot transfer {get_symbol_from_currency_code(currency)} to debit wallet',
        )

    if dst_type == Wallet.WALLET_TYPE.margin and currency not in MARGIN_CURRENCIES:
        raise TransferException(
            'UnsupportedCoin',
            f'Cannot transfer {get_symbol_from_currency_code(currency)} to margin wallet',
        )

    if money_is_zero(amount):
        raise TransferException('InvalidAmount', 'Amount must be positive')

    if src_type == dst_type:
        raise TransferException('SameDestination', 'Dst wallet must be different from src wallet')

    wallets = {
        wallet.type: wallet
        for wallet in Wallet.get_user_wallets(user)
        .select_for_update(no_key=True)
        .filter(
            currency=currency,
            type__in=[src_type, dst_type],
        )
        .order_by('id')
    }

    src_wallet = wallets.get(src_type)
    if not src_wallet and src_type != Wallet.WALLET_TYPE.spot:  # Treat like spot actually exists
        raise TransferException('WalletNotFound', 'Src wallet not found')

    if not src_wallet or amount > src_wallet.active_balance:
        raise TransferException('InsufficientBalance', 'Amount cannot exceed active balance')

    dst_wallet = wallets.get(dst_type) or Wallet.get_user_wallet(user, currency, dst_type)
    if not dst_wallet:
        raise TransferException('WalletNotFound', 'Dst wallet not found')

    src_transaction = src_wallet.create_transaction(
        tp='transfer', amount=-amount, description=f'انتقال به کیف‌پول {Wallet.WALLET_VERBOSE_TYPE[dst_type]}'
    )
    dst_transaction = dst_wallet.create_transaction(
        tp='transfer',
        amount=amount,
        description=f'انتقال از کیف‌پول {Wallet.WALLET_VERBOSE_TYPE[src_type]}',
        allow_negative_balance=True,
    )

    src_transaction.commit()
    dst_transaction.commit(allow_negative_balance=True)

    # TODO: remove on #158 being merged
    src_wallet.refresh_from_db()
    dst_wallet.refresh_from_db()
    return src_wallet, dst_wallet, amount, [src_transaction, dst_transaction]


def create_bulk_transfer(user, data: WalletBulkTransferData) -> Tuple[List[TransferResult], WalletBulkTransferRequest]:
    result = []
    transactions = []
    try:
        for currency, amount in data['transfers'].items():
            src_wallet, dst_wallet, amount, _transactions = transfer_balance(
                user,
                currency,
                amount,
                data['src_type'],
                data['dst_type'],
            )
            result.append(
                {
                    'srcWallet': src_wallet,
                    'dstWallet': dst_wallet,
                    'amount': amount,
                },
            )
            transactions.extend(_transactions)
    except TransferException as ex:
        raise NobitexAPIError(ex.code, ex.message, status_code=422) from ex

    wallet_bulk_transfer_request = WalletBulkTransferRequest.objects.create(
        user=user,
        status=WalletBulkTransferRequest.STATUS.done,
        src_wallet_type=data['src_type'],
        dst_wallet_type=data['dst_type'],
        currency_amounts={c: str(a) for c, a in data['transfers'].items()},
    )
    wallet_bulk_transfer_request.transactions.set(transactions)
    return result, wallet_bulk_transfer_request
