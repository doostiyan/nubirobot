from decimal import Decimal
from typing import Dict, Iterable, List, Union

from django.conf import settings
from django.db import transaction

from exchange.accounts.models import User
from exchange.asset_backed_credit.api.parsers import parse_wallet_withdraw_transfers
from exchange.asset_backed_credit.api.serializers import WalletTransferLogCreateResponseSerializer
from exchange.asset_backed_credit.exceptions import (
    InsufficientCollateralError,
    InvalidMarginRatioAfterTransfer,
    PendingSettlementExists,
    PendingTransferExists,
)
from exchange.asset_backed_credit.externals.wallet import WalletProvider
from exchange.asset_backed_credit.models import InternalUser, Wallet, WalletTransferLog
from exchange.asset_backed_credit.models.settlement import SettlementTransaction
from exchange.asset_backed_credit.models.user_service import UserService
from exchange.asset_backed_credit.services.price import PricingService, get_mark_price_partial_balance, get_ratios
from exchange.asset_backed_credit.services.wallet.wallet import WalletMapper, WalletService
from exchange.asset_backed_credit.types import CreditWalletBulkWithdrawCreateRequest
from exchange.base.calendar import ir_now
from exchange.base.constants import ZERO
from exchange.base.models import Settings, get_currency_codename
from exchange.wallet.functions import transfer_balance
from exchange.wallet.models import Transaction as ExchangeTransaction
from exchange.wallet.models import Wallet as ExchangeWallet
from exchange.wallet.models import WalletBulkTransferRequest as ExchangeWalletBulkTransferRequest


@transaction.atomic
def create_withdraw_request(
    user: User, withdraw_data: CreditWalletBulkWithdrawCreateRequest
) -> Union[ExchangeWalletBulkTransferRequest, dict]:
    from exchange.asset_backed_credit.tasks import process_wallet_transfer_log_task, task_process_withdraw_request

    _check_create_withdraw_eligibility(withdraw_data.src_type, user)
    wallets = _get_wallets(user, withdraw_data.transfers.keys(), wallet_type=withdraw_data.src_type)
    _check_wallets_balance(wallets, withdraw_data.transfers)

    transfer_total_balance = _get_request_total_balance(wallets, withdraw_data.transfers)
    _check_margin_ratio(user, transfer_total_balance, wallet_type=WalletMapper.to_wallet_type(withdraw_data.src_type))

    if Settings.get_flag('abc_use_wallet_transfer_internal_api'):
        internal_user = InternalUser.objects.get(uid=user.uid)
        transfer_log = WalletTransferLog.create(
            user=user,
            internal_user=internal_user,
            src_wallet_type=withdraw_data.src_type,
            dst_wallet_type=withdraw_data.dst_type,
            transfer_items=withdraw_data.transfers,
        )
        process_wallet_transfer_log_task.delay(transfer_log.id)
        return WalletTransferLogCreateResponseSerializer(instance=transfer_log).data

    bulk_transfer = ExchangeWalletBulkTransferRequest.objects.create(
        user=user,
        status=ExchangeWalletBulkTransferRequest.STATUS.new,
        src_wallet_type=withdraw_data.src_type,
        dst_wallet_type=withdraw_data.dst_type,
        currency_amounts={currency: str(amount) for currency, amount in withdraw_data.transfers.items()},
    )
    task_process_withdraw_request.delay(bulk_transfer.id)
    return bulk_transfer


def _check_create_withdraw_eligibility(src_type: int, user: User) -> None:
    if ExchangeWalletBulkTransferRequest.has_pending_transfer(user, src_type=src_type):
        raise PendingTransferExists()
    if Settings.get_flag('abc_use_wallet_transfer_internal_api') and WalletTransferLog.has_pending_transfer(
        user, src_wallet_type=src_type
    ):
        raise PendingTransferExists()

    _check_pending_settlement(WalletMapper.to_wallet_type(src_type), user)


def _check_pending_settlement(src_wallet_type: int, user: User):
    if SettlementTransaction.has_pending_transaction(user, service_types=Wallet.get_service_types(src_wallet_type)):
        raise PendingSettlementExists()


def _get_wallets(
    user: User, currencies: Iterable[int], should_lock: bool = False, wallet_type=ExchangeWallet.WALLET_TYPE.credit
) -> Dict[int, ExchangeWallet]:
    wallets = ExchangeWallet.objects.filter(
        user=user,
        type=wallet_type,
        currency__in=currencies,
    )
    if should_lock:
        wallets = wallets.select_for_update(no_key=True)

    return {wallet.currency: wallet for wallet in wallets}


def _check_wallets_balance(wallets: Dict[int, ExchangeWallet], wallet_transfers: Dict[int, Decimal]) -> None:
    for currency, amount in wallet_transfers.items():
        wallet = wallets.get(currency)
        if wallet is None or wallet.active_balance < amount:
            raise InsufficientCollateralError(currency=currency, amount=amount)


def _get_request_total_balance(wallets: Dict[int, ExchangeWallet], wallet_transfers: Dict[int, Decimal]) -> Decimal:
    wallets_requested_amount_pair = {wallet: wallet_transfers.get(currency) for currency, wallet in wallets.items()}
    return get_mark_price_partial_balance(wallets_requested_amount_pair)


def _check_margin_ratio(
    user: User, transfer_total_balance: Decimal = ZERO, wallet_type: int = Wallet.WalletType.COLLATERAL
):
    margin_ratio = PricingService(user=user, wallet_type=wallet_type).get_margin_ratio(
        balance_diff=-transfer_total_balance
    )
    if margin_ratio < get_ratios(wallet_type=wallet_type).get('collateral'):
        raise InvalidMarginRatioAfterTransfer()


def process_pending_withdraw_requests():
    from exchange.asset_backed_credit.tasks import process_wallet_transfer_log_task, task_process_withdraw_request

    transfer_log_ids = WalletTransferLog.get_pending_transfer_logs().values_list('id', flat=True)
    for log_id in transfer_log_ids:
        process_wallet_transfer_log_task.delay(log_id)

    withdraw_requests_ids = (
        ExchangeWalletBulkTransferRequest.get_pending_transfers()
        .filter(
            created_at__lte=ir_now() - settings.ABC_WITHDRAW_DELAY,
        )
        .values_list('id', flat=True)
    )
    for withdraw_request_id in withdraw_requests_ids:
        task_process_withdraw_request.delay(withdraw_request_id)


@transaction.atomic
def process_withdraw_request(
    wallet_transfer_id: int,
) -> Union[ExchangeWalletBulkTransferRequest, WalletTransferLog]:
    wallet_bulk_transfer = _get_pending_bulk_transfer_requests(wallet_transfer_id)
    user = wallet_bulk_transfer.user
    _check_pending_settlement(
        user=user, src_wallet_type=WalletMapper.to_wallet_type(wallet_bulk_transfer.src_wallet_type)
    )

    user_services = (
        UserService.get_actives(user=user).select_related('service').select_for_update(of=('self',), no_key=True).all()
    )
    for user_service in user_services:
        user_service.fetch_and_update_debt()

    wallets = _get_wallets(
        user,
        wallet_bulk_transfer.currency_amounts.keys(),
        should_lock=True,
        wallet_type=wallet_bulk_transfer.src_wallet_type,
    )

    try:
        with transaction.atomic():
            transfers = parse_wallet_withdraw_transfers(wallet_bulk_transfer.currency_amounts)
            _check_wallets_balance(wallets, transfers)
            transactions = _transfer_balance(
                user, wallet_bulk_transfer.src_wallet_type, wallet_bulk_transfer.dst_wallet_type, transfers, wallets
            )
            _check_margin_ratio(user, wallet_type=WalletMapper.to_wallet_type(wallet_bulk_transfer.src_wallet_type))
            wallet_bulk_transfer.accept(transactions)
    except InvalidMarginRatioAfterTransfer:
        wallet_bulk_transfer.reject('این درخواست نسبت تعهد را به زیر حد مجاز می‌رساند.')
    except InsufficientCollateralError as ex:
        currency_codename = get_currency_codename(ex.currency)
        wallet_bulk_transfer.reject(f'موجودی ازاد کیف پول {currency_codename} کمتر از مقدار درخواست شده است.')

    return wallet_bulk_transfer


def _get_pending_bulk_transfer_requests(wallet_transfer_id: int) -> ExchangeWalletBulkTransferRequest:
    """
    get pending bulk transfer requests of credit wallets

    Parameters:
        - wallet_bulk_transfer_id (int): id of the wallet bulk transfer request
    Returns:
        - ExchangeWalletBulkTransferRequest: the wallet bulk transfer request with the associated user
    Raises:
        - ExchangeWalletBulkTransferRequest.DoesNotExist: if there is no record with the given wallet_bulk_transfer_id
    """
    return (
        ExchangeWalletBulkTransferRequest.get_pending_transfers()
        .select_related('user')
        .select_for_update(of=('self',), no_key=True)
        .get(pk=wallet_transfer_id)
    )


def _transfer_balance(user, src_wallet_type, dst_wallet_type, transfers, wallets) -> List[ExchangeTransaction]:
    transactions = []
    for currency, wallet in wallets.items():
        _, _, _, txs = transfer_balance(
            user=user,
            currency=currency,
            amount=transfers.get(currency),
            src_type=src_wallet_type,
            dst_type=dst_wallet_type,
        )
        transactions.extend(txs)
    return transactions


@transaction.atomic
def process_wallet_transfer_log(transfer_log_id: int):
    if Settings.get_flag('abc_use_wallet_transfer_internal_api'):
        try:
            transfer_log = WalletTransferLog.get_pending_transfer_log(transfer_id=transfer_log_id)
        except WalletTransferLog.DoesNotExist:
            return

        _check_pending_settlement(
            user=transfer_log.user, src_wallet_type=WalletMapper.to_wallet_type(transfer_log.src_wallet_type)
        )

        transfers = {int(currency): Decimal(amount) for currency, amount in transfer_log.transfer_items.items()}
        wallets = _get_wallets(transfer_log.user, transfers.keys(), wallet_type=transfer_log.src_wallet_type)
        _check_wallets_balance(wallets, transfers)

        try:
            transfer_total_balance = _get_request_total_balance(wallets, transfers)
            _check_margin_ratio(
                transfer_log.user,
                transfer_total_balance,
                wallet_type=WalletMapper.to_wallet_type(transfer_log.src_wallet_type),
            )
        except InvalidMarginRatioAfterTransfer as _:
            transfer_log.make_none_retryable(' درخواست نسبت تعهد را به زیر حد مجاز می‌رساند.')
            return

        response_schema, internal_api = WalletProvider.transfer(transfer_log)

        if response_schema:
            transfer_log.update_api_data(
                response_body=response_schema.model_dump(mode='json'),
                response_code=internal_api.get_response_code(),
                external_transfer_id=response_schema.id,
            )
            transfer_log.update_status(WalletTransferLog.STATUS.done)
            WalletService.invalidate_user_wallets_cache(user_id=transfer_log.user.uid)
        else:
            transfer_log.update_api_data(
                response_body=internal_api.get_response_body(),
                response_code=internal_api.get_response_code(),
            )

            if internal_api.has_none_retryable_error():
                _, reason = internal_api.get_none_retryable_error_key_and_reason()
                transfer_log.make_none_retryable(reason)
                return

            transfer_log.update_status(WalletTransferLog.STATUS.pending_to_retry)
