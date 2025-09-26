from collections import defaultdict
from typing import Dict, List

from django.db import DatabaseError, transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from pydantic import ValidationError

from exchange.accounts.models import BankAccount, User
from exchange.base.api import NobitexAPIError, ParseError
from exchange.base.api_v2_1 import internal_post_api
from exchange.base.decorators import measure_api_execution
from exchange.base.http import get_client_ip
from exchange.base.internal.services import Services
from exchange.base.models import Currencies, get_currency_codename
from exchange.base.parsers import parse_bulk_wallet_transfer, parse_int, parse_str, parse_uuid
from exchange.base.serializers import serialize
from exchange.wallet.functions import create_bulk_transfer
from exchange.wallet.internal.constants import MAX_BATCH_TRANSACTION_LENGTH
from exchange.wallet.internal.dtos import WalletParamsDTO
from exchange.wallet.internal.exceptions import NonZeroAmountSum, UserNotFound
from exchange.wallet.internal.permissions import check_bulk_transfer_permission, check_service_wallet_permission
from exchange.wallet.internal.service_transaction import create_batch_service_transaction
from exchange.wallet.internal.types import TransactionInput
from exchange.wallet.internal.withdraw_validations import (
    CheckDailyShabaWithdrawLimitExceededValidation,
    CreditValidation,
    EligibleToWithdrawValidation,
    MaxAmountValidation,
    MinAmountValidation,
    ProviderValidation,
    UserLevelLimitationValidation,
    UserProfileValidation,
    UserRestrictionValidation,
    UserWalletBalanceValidation,
    WithdrawStatusValidation,
)
from exchange.wallet.models import Wallet, WithdrawRequest, WithdrawRequestPermit


@measure_api_execution(api_label='internalCreateBulkTransfer')
@internal_post_api(allowed_services=[Services.ABC])
def internal_bulk_transfer_view(request):
    """API for internal bulk transferring balance between user wallets

    POST /internal/wallets/bulk-transfer
    """

    user_id = parse_uuid(request.g('userId'), required=True)
    data = parse_bulk_wallet_transfer(
        request.g('data'),
        max_len=10,
        wallet_choices=Wallet.WALLET_TYPE,
        required=True,
    )
    check_bulk_transfer_permission(request.service, data['src_type'])
    user = User.objects.filter(uid=user_id).first()

    if not user:
        raise Http404('User not found')

    _, wallet_bulk_transfer = create_bulk_transfer(user, data)
    return {'id': wallet_bulk_transfer.id}


@measure_api_execution(api_label='internalCreateWithdrawRial')
@internal_post_api(allowed_services=[Services.ABC])
def internal_withdraw_rial_view(request):
    user_uid = parse_uuid(request.g('userId'), required=True)
    amount = parse_int(request.g('amount'), required=True)
    shaba_number = parse_str(request.g('shabaNumber'), required=True)
    explanation = parse_str(request.g('explanation'))

    user = get_object_or_404(User, uid=user_uid)
    bank_account = get_object_or_404(
        BankAccount, user=user, shaba_number=shaba_number, confirmed=True, is_deleted=False, is_temporary=False
    )
    wallet = (
        Wallet.objects.select_related().filter(user=user, currency=Currencies.rls, type=Wallet.WALLET_TYPE.spot).first()
    )
    if not wallet:
        raise NobitexAPIError(
            status_code=404,
            message='WalletNotFound',
            description='wallet not found',
        )

    network = 'FIAT_MONEY'
    withdraw_permit = WithdrawRequestPermit.get(user, wallet.currency, amount)

    validations = [
        MaxAmountValidation(user, wallet, shaba_number, amount, bank_account=bank_account, network=network),
        MinAmountValidation(user, wallet, shaba_number, amount, network=network),
        CreditValidation(user, wallet, shaba_number, amount),
        UserWalletBalanceValidation(user, wallet, shaba_number, amount),
        UserRestrictionValidation(user, wallet, shaba_number, amount, withdraw_permit=withdraw_permit),
        ProviderValidation(user, wallet, shaba_number, amount, bank_account=bank_account),
        CheckDailyShabaWithdrawLimitExceededValidation(user, wallet, shaba_number, amount, bank_account=bank_account),
        UserLevelLimitationValidation(user, wallet, shaba_number, amount),
        EligibleToWithdrawValidation(user, wallet, shaba_number, amount, network=network, bank_account=bank_account),
        UserProfileValidation(user, wallet, shaba_number, amount),
        WithdrawStatusValidation(user, wallet, shaba_number, amount, network=network),
    ]
    for validation in validations:
        validation.validate()

    # Everything is OK, create request
    withdraw_request = WithdrawRequest(
        tp=WithdrawRequest.TYPE.normal,
        wallet=wallet,
        target_address=bank_account.display_name,
        target_account=bank_account,
        amount=amount,
        network=network,
        ip=ip if (ip := get_client_ip(request)) else None,
        requester_service=request.service,
        explanations=explanation,
    )
    withdraw_request.save()
    withdraw_request.do_verify()
    if WithdrawRequest.is_user_not_allowed_to_withdraw(user, wallet) and withdraw_permit:
        withdraw_permit.is_active = False
        withdraw_permit.withdraw_request = withdraw_request
        withdraw_permit.save(update_fields=['is_active', 'withdraw_request'])

    return {
        'id': withdraw_request.id,
    }


@measure_api_execution(api_label='internalWalletsList')
@internal_post_api(allowed_services=[Services.ABC], _idempotent=False)
@transaction.non_atomic_requests
def internal_list_wallets_view(request):
    """API for internals get wallet list

    POST /internal/wallets/list
    """

    data: List[Dict[str, str]] = request.data

    serializer = WalletParamsDTO(data=data, many=True, max_length=100)
    if not serializer.is_valid():
        raise NobitexAPIError(
            status_code=400,
            message='IllegalArgument',
            description=str(serializer.errors),
        )
    validated_data = serializer.validated_data

    for wallet_params in validated_data:
        check_service_wallet_permission(request.service, wallet_params.get('type'))

    wallets = Wallet.get_wallets_by_params(validated_data)

    grouped_wallets = defaultdict(list)
    for wallet in wallets:
        uid = wallet.user.uid
        grouped_wallets[str(uid)].append(
            {
                'userId': str(wallet.user.uid),
                'currency': get_currency_codename(wallet.currency),
                'type': Wallet.WALLET_TYPE._display_map[wallet.type].lower(),
                'balance': str(wallet.balance),
                'blockedBalance': str(wallet.balance_blocked),
                'activeBalance': str(wallet.balance - wallet.balance_blocked),
            }
        )
    return grouped_wallets


@measure_api_execution(api_label='internalCreateBatchTransactions')
@internal_post_api(allowed_services=[Services.ABC], _idempotent=True)
def internal_batch_transaction_view(request):
    """API for internal batch transaction

    POST /internal/transactions/batch-create
    """
    data = request.data
    if not data:
        raise ParseError('Missing list value')

    if not isinstance(data, list):
        raise ParseError('Invalid list')

    if len(data) > MAX_BATCH_TRANSACTION_LENGTH:
        raise ParseError(f'List is too long, max len is {MAX_BATCH_TRANSACTION_LENGTH}')

    try:
        batch_transaction_data = [TransactionInput.model_validate(tx) for tx in data]
    except ValidationError as ex:
        raise ParseError(ex.errors()[0]['msg']) from ex

    try:
        result, has_error = create_batch_service_transaction(request.service, batch_transaction_data)
    except UserNotFound as ex:
        raise NobitexAPIError(
            status_code=404,
            message='UserNotFound',
            description=f'Users with id of {ex.args[0]} are not found',
        ) from ex
    except NonZeroAmountSum as ex:
        raise NobitexAPIError(
            status_code=412,
            message='NonZeroSumAmount',
            description='Sum of transaction amounts should be zero',
        ) from ex
    except DatabaseError as ex:
        raise NobitexAPIError(
            status_code=423,
            message='LockedWallet',
            description='Some wallets are locked, try again',
        ) from ex

    serialized_result = serialize(result)

    if has_error:
        return JsonResponse(
            status=422,
            data=serialized_result,
            safe=False,
        )

    return serialized_result
