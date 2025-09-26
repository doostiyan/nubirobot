import datetime
import json
import re
from decimal import Decimal
from hmac import compare_digest

import jdatetime
from django.conf import settings
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import Case, F, Q, Sum, When
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic import FormView
from django_ratelimit.decorators import ratelimit
from ipware import get_client_ip
from rest_framework import status
from rest_framework.response import Response

from exchange.accounting.models import DepositSystemBankAccount
from exchange.accounts.models import BankAccount, BankCard, User, UserEvent, UserPreference, UserRestriction, UserSms
from exchange.accounts.user_restrictions import UserRestrictionsDescription
from exchange.accounts.userlevels import UserLevelManager
from exchange.accounts.views.auth import check_user_otp
from exchange.base.api import (
    APIView,
    NobitexAPIError,
    ParseError,
    SemanticAPIError,
    api,
    basic_auth_api,
    email_required_api,
    is_request_from_unsupported_app,
    public_api,
    public_post_api,
)
from exchange.base.api_v2 import post_api
from exchange.base.cache import CacheManager
from exchange.base.calendar import ir_now
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.constants import MAX_PRECISION, ZERO
from exchange.base.decorators import measure_api_execution, measure_time_cm
from exchange.base.formatting import get_decimal_places
from exchange.base.functions import serve
from exchange.base.helpers import date_filter, download_csv, get_api_ratelimit, is_from_unsupported_app, paginate
from exchange.base.id_translation import decode_id, encode_id
from exchange.base.ip import ip_mask
from exchange.base.logging import log_time, metric_incr, report_event, report_exception
from exchange.base.models import (
    ALL_CURRENCIES,
    BABYDOGE,
    CURRENCY_CODENAMES,
    EXCHANGE_ADDRESS_TAG_REQUIRED,
    INTEGER_ONLY_TAG_CURRENCIES,
    RIAL,
    SUPPORTED_INVOICE_CURRENCIES,
    TESTING_CURRENCIES,
    Currencies,
    Settings,
    get_currency_codename,
)
from exchange.base.parsers import (
    parse_bool,
    parse_bulk_wallet_transfer,
    parse_choices,
    parse_currency,
    parse_int,
    parse_money,
    parse_multi_choices,
    parse_tag,
    parse_utc_timestamp,
    parse_uuid,
)
from exchange.base.serializers import serialize
from exchange.blockchain.bip39_wallets import BLOCKCHAIN_WALLET_CLASS
from exchange.blockchain.general_blockchain_wallets import GeneralBlockchainWallet
from exchange.blockchain.invoices import decode_invoice
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.blockchain.segwit_address import eth_to_one_address
from exchange.blockchain.validators import validate_crypto_address_v2, validate_memo_v2
from exchange.corporate_banking.models.deposit import CoBankUserDeposit
from exchange.credit.exportables import check_if_user_could_withdraw as credit_check_if_user_could_withdraw
from exchange.direct_debit.models import DirectDeposit
from exchange.features.utils import is_feature_enabled, require_feature
from exchange.market.marketmanager import MarketManager
from exchange.market.models import Order
from exchange.report.views import admin_access
from exchange.security.models import AddressBook
from exchange.shetab.models import ShetabDeposit
from exchange.usermanagement.block import BalanceBlockManager
from exchange.wallet.constants import TRANSACTION_MAX
from exchange.wallet.deposit import refresh_address_deposits, refresh_wallet_deposits
from exchange.wallet.estimator import PriceEstimator
from exchange.wallet.exceptions import TransferException
from exchange.wallet.forms import (
    BalanceTronZWalletForm,
    CreateWalletBIP39Form,
    CreateWalletForm,
    CreateWalletFromColdForm,
    ExtractContractAddressesForm,
    FreezeTronWalletForm,
    MintTronZWalletForm,
    UnfreezeTronWalletForm,
    UpdateDepositForm,
)
from exchange.wallet.functions import create_bulk_transfer, transfer_balance
from exchange.wallet.models import (
    AvailableDepositAddress,
    BankDeposit,
    ConfirmedWalletDeposit,
    Transaction,
    TransactionHistoryFile,
    Wallet,
    WalletBulkTransferRequest,
    WalletDepositAddress,
    WithdrawRequest,
    WithdrawRequestPermit,
    WithdrawRequestRestriction,
)
from exchange.wallet.serializers import serialize_transaction, serialize_wallet_addresses
from exchange.wallet.tasks import export_transaction_history, task_extract_contract_addresses
from exchange.wallet.wallet_manager import WalletTransactionManager
from exchange.wallet.webhooks import (
    BTCBlockcypherWebhookParser,
    BTCBlocknativeWebhookParser,
    ETHBlocknativeWebhookParser,
    XRPLWebhookParser,
    change_hotwallet,
)
from exchange.web_engage.events.deposit_withdraw_events import ShetabGatewayUnavailableWebEngageEvent


def get_user_blocked_withdraws(uid):
    """ Return user blocked balances because of pending withdraws

        # TODO: this should be always zero after change in withdraw processing
    """
    blocked_balances = {}
    active_withdraws = WithdrawRequest.objects.filter(
        transaction__isnull=True,
        wallet__user_id=uid,
    ).exclude(
        status__in=WithdrawRequest.STATUSES_INACTIVE,
    ).values('wallet__currency').annotate(total=Sum('amount'))
    for withdraw in active_withdraws:
        blocked_balances[withdraw['wallet__currency']] = withdraw['total'] or Decimal('0')
    return blocked_balances


def check_user_has_no_order(uid):
    """ Return true if we are sure that this user has no open orders
    """
    user_has_no_order = cache.get(f'user_{uid}_no_order')
    if user_has_no_order:
        user_has_recent_order = cache.get(f'user_{uid}_recent_order')
        if not user_has_recent_order:
            return True
    return False


def get_user_blocked_orders(uid):
    """ Return user blocked balances because of open orders
    """
    blocked_balances = {}
    f_unmatched_amount = F('amount') - F('matched_amount')
    in_orders = Order.objects.filter(
         user_id=uid, status__in=[Order.STATUS.active, Order.STATUS.inactive], trade_type=Order.TRADE_TYPES.spot
    ).exclude(
        pair__isnull=False, matched_amount=0, execution_type=Order.EXECUTION_TYPES.limit,
    ).annotate(
        currency=Case(
            When(order_type=Order.ORDER_TYPES.buy, then=F('dst_currency')),
            When(order_type=Order.ORDER_TYPES.sell, then=F('src_currency')),
        ),
        in_order=Case(
            When(order_type=Order.ORDER_TYPES.buy, then=f_unmatched_amount * F('price')),
            When(order_type=Order.ORDER_TYPES.sell, then=f_unmatched_amount),
        ),
    ).values('currency').annotate(blocked=Sum('in_order'))
    for in_order in in_orders:
        currency = in_order['currency']
        blocked_balances[currency] = in_order['blocked'] or Decimal('0')
    return blocked_balances


def authenticated_wallet_ratelimit_key(group, request):
    wallet_type = 'margin' if request.GET.get('type') == 'margin' else 'spot'

    if request.user.is_authenticated:
        return str(request.user.pk) + wallet_type
    return ip_mask(request.META['REMOTE_ADDR']) + wallet_type


@ratelimit(key=authenticated_wallet_ratelimit_key, rate='20/2m', block=True)
@api
def wallets_list(request):
    """ POST /users/wallets/list
    """
    user = request.user
    uid = user.id
    wallet_type = parse_choices(Wallet.WALLET_TYPE, request.g('type')) or Wallet.WALLET_TYPE.spot
    wallets = Wallet.get_user_wallets(user, wallet_type)

    # Check cache for wallet addresses
    if wallet_type == Wallet.WALLET_TYPE.spot:
        cache_key = 'user_{}_wl_addr'.format(uid)
        cached_wallet_addresses = cache.get(cache_key)
        if not cached_wallet_addresses:
            cached_wallet_addresses = {
                wallet.id: serialize_wallet_addresses(wallet)
                for wallet in wallets
            }
            cache.set(cache_key, cached_wallet_addresses, 3600)
    else:
        cached_wallet_addresses = {}

    # Calculate blocked balances
    if wallet_type == Wallet.WALLET_TYPE.spot:
        block_withdraw = get_user_blocked_withdraws(uid)
        if check_user_has_no_order(uid):
            block_order = {}
        else:
            block_order = get_user_blocked_orders(uid)
        for wallet in wallets:
            wallet.balance_blocked = (
                block_withdraw.get(wallet.currency, Decimal('0')) + block_order.get(wallet.currency, Decimal('0'))
            )

    supported_currencies = set(ALL_CURRENCIES)
    if not is_feature_enabled(user, 'new_coins'):
        supported_currencies -= set(TESTING_CURRENCIES)
    if is_from_unsupported_app(request, feature='percentage_fee'):
        supported_currencies -= {BABYDOGE}

    # Serialize values
    serialized_wallets = []
    for wallet in wallets:
        # Ignore wallets with unknown currencies. This only happens when:
        #   1. An unknown wallet objects is created for a user
        #   2. The running code is not up-to-date and is missing a new currency
        if wallet.currency not in supported_currencies:
            continue

        wallet_dict = cached_wallet_addresses.get(wallet.id) or {}
        wallet_dict['id'] = wallet.id
        wallet_dict['currency'] = get_currency_codename(wallet.currency)
        # Balance
        wallet_dict['balance'] = wallet.balance
        wallet_dict['blockedBalance'] = wallet.balance_blocked
        wallet_dict['activeBalance'] = wallet.balance - wallet.balance_blocked
        # Value
        if wallet.balance < MAX_PRECISION:
            wallet_dict['rialBalance'] = 0
            wallet_dict['rialBalanceSell'] = 0
        else:
            buy_price, sell_price = PriceEstimator.get_price_range(wallet.currency)
            wallet_dict['rialBalance'] = int(buy_price * wallet.balance)
            wallet_dict['rialBalanceSell'] = int(sell_price * wallet.balance)
        serialized_wallets.append(wallet_dict)

    return {
        'status': 'ok',
        'wallets': serialized_wallets,
    }


@ratelimit(key='user_or_ip', rate=get_api_ratelimit('15/1m'), block=True)
@api
def v2_wallets(request):
    """ POST /v2/wallets
    """
    # Filter user wallets
    user = request.user
    wallet_type = parse_choices(Wallet.WALLET_TYPE, request.g('type')) or Wallet.WALLET_TYPE.spot
    wallets = Wallet.get_user_wallets(user=user, tp=wallet_type)
    currencies = request.g('currencies')
    if currencies:
        currencies = [parse_currency(c) for c in currencies.split(',')]
        wallets = wallets.filter(currency__in=currencies)
    for wallet in wallets:
        wallet.user = user

    if wallet_type == Wallet.WALLET_TYPE.spot:
        # Calculate blocked balances
        if currencies and len(currencies) <= 1:
            block_withdraw = {w.currency: BalanceBlockManager.get_blocked_balance(w) for w in wallets}
            block_order = {w.currency: BalanceBlockManager.get_balance_in_order(w) for w in wallets}
        else:
            block_withdraw = get_user_blocked_withdraws(user.id)
            if check_user_has_no_order(user.id):
                block_order = {}
            else:
                block_order = get_user_blocked_orders(user.id)

        for wallet in wallets:
            wallet.balance_blocked = (
                block_withdraw.get(wallet.currency, Decimal('0')) + block_order.get(wallet.currency, Decimal('0'))
            )

    # Get wallet balances and create response
    data = {}
    for wallet in wallets:
        currency = wallet.currency
        data[CURRENCY_CODENAMES[currency]] = {
            'id': wallet.id,
            'balance': wallet.balance,
            'blocked': wallet.balance_blocked,
        }
    return {
        'status': 'ok',
        'wallets': data,
    }


@ratelimit(key='user_or_ip', rate=get_api_ratelimit('60/2m'), block=True)
@api
def wallets_balance(request):
    user = request.user
    currency = parse_currency(request.g('currency'), required=True)
    wallet = Wallet.get_user_wallet(user, currency, create=False)
    return {
        'status': 'ok',
        'balance': wallet.balance if wallet else ZERO,
    }


@ratelimit(key='user_or_ip', rate='60/2m', block=True)
@api
def wallets_transactions_list(request):
    """ POST /users/wallets/transactions/list
    """
    user = request.user
    wallet_id = parse_int(request.g('wallet'), required=True)
    wallet = get_object_or_404(Wallet, pk=wallet_id, user=user)
    transactions = wallet.transactions.filter(created_at__gte=settings.LAST_ACCESSIBLE_TRANSACTION_DATE).order_by(
        '-created_at',
        '-id',
    )
    transactions = paginate(transactions, request=request, max_page=100, max_page_size=100)
    return {
        'status': 'ok',
        'transactions': transactions,
    }


def validate_transaction_history_range(from_date, to_date):
    if from_date >= to_date:
        raise SemanticAPIError('InvalidPeriod', 'from must be before to.')

    if to_date - from_date > datetime.timedelta(days=settings.TRANSACTION_HISTORY_MAX_DELTA_DAYS):
        raise SemanticAPIError(
            'PeriodTooLong',
            f'to - from must be less than {settings.TRANSACTION_HISTORY_MAX_DELTA_DAYS} days',
        )


@ratelimit(key='user_or_ip', rate='60/60m', block=True)
@api
@transaction.atomic
def user_transaction_history(request):
    """ POST /users/transactions-history
    """

    cursor = connection.cursor()
    # Next line will force postgres planner to use index instead of seq scan
    cursor.execute('SET LOCAL random_page_cost = 0.1;')

    download_as_csv = parse_bool(request.GET.get('download'))
    from_id = parse_int(request.GET.get('from_id'))
    currency = parse_currency(request.GET.get('currency'))
    tps = parse_multi_choices(Transaction.TYPE, request.GET.get('tp'), max_len=25)
    from_date = parse_utc_timestamp(request.GET.get('from'))
    to_date = parse_utc_timestamp(request.GET.get('to'))

    if from_date and to_date:
        validate_transaction_history_range(from_date, to_date)

    # Get transaction, assuming they have balance field
    user_wallets = Wallet.objects.filter(user=request.user)
    if currency:
        user_wallets = user_wallets.filter(currency=currency)

    user_wallets = dict(user_wallets.values_list('id', 'currency'))
    transactions = Transaction.objects.filter(wallet_id__in=user_wallets.keys())

    if from_id:
        from_id = decode_id(from_id)
        # Negative IDs are newer than positive ones, so we need to adjust the query for that.
        if from_id > 0:
            from_id_q = Q(id__gt=from_id) | Q(id__lte=0)
        else:
            from_id_q = Q(id__gt=from_id) & Q(id__lte=0)
        transactions = transactions.filter(from_id_q)
    if tps:
        transactions = transactions.filter(tp__in=tps)
    if not download_as_csv:
        transactions = transactions.filter(created_at__gte=settings.LAST_ACCESSIBLE_TRANSACTION_DATE)
    if from_date:
        transactions = transactions.filter(created_at__gte=from_date)
    if to_date:
        transactions = transactions.filter(created_at__lte=to_date)

    transactions = transactions.order_by('-created_at', '-id').values(
        'id', 'amount', 'description', 'created_at', 'balance', 'tp', 'wallet_id',
    )

    if download_as_csv:
        transactions = transactions[:10000]
        has_next = False
    else:
        with measure_time_cm(metric='transaction_history_pagination'):
            transactions, has_next = paginate(transactions, request=request, check_next=True)

    # Serialize
    if download_as_csv:
        with measure_time_cm(metric='transaction_history_csv'):
            transactions = list(transactions)
    else:
        transactions = list(transactions)

    type_id_map = {v: k for k, v in Transaction.TYPE._identifier_map.items()}

    for tx in transactions:
        tx['id'] = encode_id(tx['id'])
        tx['calculatedFee'] = None
        tx['type'] = Transaction.TYPES_HUMAN_DISPLAY.get(tx['tp'], 'سایر')
        tx['tp'] = type_id_map.get(tx['tp'], 'etc')
        tx['currency'] = CURRENCY_CODENAMES.get(user_wallets[tx['wallet_id']], '').lower()
        tx['created_at'] = serialize(tx['created_at'])
        del tx['wallet_id']

    # JSON or downloadable CSV response
    if download_as_csv:
        headers = ['id', 'created_at', 'type', 'currency', 'amount', 'balance', 'description']
        return download_csv('transactions-history', transactions, headers)

    return JsonResponse({
        'status': 'ok',
        'transactions': transactions,
        'hasNext': has_next,
    }, json_dumps_params={'ensure_ascii': False})


class TransactionHistoryView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='4/m', block=True))
    @method_decorator(ratelimit(key='user_or_ip', rate='30/h', block=True))
    @method_decorator(measure_api_execution(api_label='walletTransactionsHistoryRequest'))
    @method_decorator(email_required_api)
    def post(self, request):
        """POST /users/transactions-history/request"""

        from_date = parse_utc_timestamp(self.g('from'), required=True)
        to_date = parse_utc_timestamp(self.g('to'), required=True)
        currency = parse_currency(self.g('currency'))
        tps = parse_multi_choices(Transaction.TYPE, self.g('tp'), max_len=25)

        validate_transaction_history_range(from_date, to_date)
        user_history_count = TransactionHistoryFile.objects.filter(user=request.user).count()
        if user_history_count >= TransactionHistoryFile.MAX_PER_USER:
            raise SemanticAPIError('MaxTransactionHistoryReached', 'User reached to max transaction history.')

        export_transaction_history.delay(request.user.id, from_date.isoformat(), to_date.isoformat(), currency, tps)
        return JsonResponse(
            {
                'status': 'ok',
                'message': 'Download link will be emailed to the user.',
            }
        )


@ratelimit(key='user_or_ip', rate='5/m', block=True)
@measure_api_execution(api_label='walletTransactionsHistoryDownload')
@api
def download_user_transaction_history(request, pk):
    """GET /users/transactions-history/<int:pk>/download"""

    transaction_history = get_object_or_404(TransactionHistoryFile, pk=pk, user=request.user)
    return serve(
        transaction_history.relative_path,
        document_root=settings.MEDIA_ROOT,
        file_name=transaction_history.file_name,
        force_encoding='utf-8',
    )


@ratelimit(key='user_or_ip', rate='60/2m', block=True)
@api
def wallets_deposits_list(request):
    user = request.user
    wallet = request.g('wallet', 'all')
    days_to_show = 90 if settings.LOAD_LEVEL < 10 else 30
    date_filter_start = now() - datetime.timedelta(days=days_to_show)

    if wallet == 'all':
        user_wallets = Wallet.get_user_wallets(user)
        withdraws = WithdrawRequest.objects.filter(wallet__in=user_wallets)
        # TODO: Change this to use _wallet column
        coin_deposits = (
            ConfirmedWalletDeposit.objects.select_related('transaction', '_wallet')
            .filter(
                _wallet__in=user_wallets,
                created_at__gt=date_filter_start,
            )
            .order_by('-created_at')[:20]
        )

        bank_deposits = (
            BankDeposit.objects.filter(
                user=user,
            )
            .select_related('transaction')
            .exclude(
                status=BankDeposit.STATUS.rejected,
            )
            .order_by('-created_at')[:10]
        )

        shetab_deposits = (
            ShetabDeposit.objects.filter(user=user, status_code__gte=0)
            .select_related('transaction')
            .order_by(
                '-created_at',
            )[:20]
        )

        direct_deposits = (
            DirectDeposit.objects.select_related('contract')
            .filter(
                contract__user=user,
                status__in=(DirectDeposit.USER_VISIBLE_STATUES),
            )
            .order_by('-created_at')[:20]
        )

        cobank_deposits = (
            CoBankUserDeposit.objects.select_related('cobank_statement')
            .filter(
                user=user,
            )
            .order_by('-created_at')[:20]
        )

        deposits = (
            list(coin_deposits)
            + list(bank_deposits)
            + list(shetab_deposits)
            + list(direct_deposits)
            + list(cobank_deposits)
        )
        deposits.sort(key=lambda d: d.effective_date, reverse=True)
        has_next = False
    else:
        wallet = get_object_or_404(Wallet, pk=wallet, type=Wallet.WALLET_TYPE.spot)
        if wallet.user != user:
            raise PermissionDenied

        if wallet.currency == Currencies.rls:
            # TODO: check clients and add shetab deposits here
            deposits = BankDeposit.objects.filter(user=user).select_related('transaction').order_by('-created_at')
            deposits = date_filter(deposits, request=request)
            page_size = 10
        else:
            # TODO: Change this to use _wallet column
            deposits = (
                ConfirmedWalletDeposit.objects.select_related('transaction', '_wallet')
                .filter(
                    _wallet=wallet,
                )
                .order_by('-created_at')
            )
            deposits = date_filter(deposits, request=request, since=date_filter_start)
            page_size = 20
        deposits, has_next = paginate(
            deposits,
            request=request,
            page_size=page_size,
            check_next=True,
            max_page=100,
            max_page_size=100,
        )
        withdraws = WithdrawRequest.objects.filter(wallet=wallet)

    # Final Processing
    withdraws = (
        withdraws.select_related('wallet', 'auto_withdraw')
        .exclude(
            status=WithdrawRequest.STATUS.new,
        )
        .order_by('-created_at')[:20]
    )
    return {
        'status': 'ok',
        'deposits': serialize(deposits, opts={'user': user}),
        'withdraws': serialize(withdraws),
        'hasNext': has_next,
    }


@ratelimit(key='user_or_ip', rate='60/2m', block=True)
@api
def wallets_withdraws_list(request):
    user = request.user
    wallet = request.g('wallet', 'all')

    # Filter withdraws
    if wallet == 'all':
        withdraws = WithdrawRequest.objects.filter(wallet__user=user)
    else:
        wallet = get_object_or_404(Wallet, pk=wallet, user=user, type=Wallet.WALLET_TYPE.spot)
        withdraws = WithdrawRequest.objects.filter(wallet=wallet)

    # Create response
    withdraws = withdraws.exclude(status=WithdrawRequest.STATUS.new)
    withdraws = withdraws.select_related('wallet', 'wallet__user').order_by('-created_at')
    withdraws = date_filter(withdraws, request=request)
    withdraws, has_next = paginate(
        withdraws, request=request, page_size=20, check_next=True, max_page=100, max_page_size=100
    )
    return {
        'status': 'ok',
        'withdraws': withdraws,
        'hasNext': has_next,
    }


@ratelimit(key='user_or_ip', rate='50/24h', block=True)
@ratelimit(key='user_or_ip', rate='3/1m', block=True)
@measure_api_execution(api_label='walletRefreshDeposits')
@post_api
def wallets_deposits_refresh(request):
    user = request.user
    wallet_id = parse_int(request.g('wallet'), required=True)
    wallet = get_object_or_404(Wallet, pk=wallet_id, type=Wallet.WALLET_TYPE.spot, user=user)
    refresh_wallet_deposits(wallet, run_now=False)
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='12/h', block=True)
@measure_api_execution(api_label='walletCreateBankDeposit')
@api
@require_feature('bank_manual_deposit')
def wallets_deposit_bank(request):
    user = request.user
    src_bank_account = BankAccount.objects.filter(pk=request.g('srcBankAccount'), user=user).first()
    amount = parse_int(request.g('amount'))
    dst_account_id = parse_int(request.g('dstAccountID'))
    dst_account = None
    receipt_id = request.g('receiptID')
    if dst_account_id:
        dst_account = DepositSystemBankAccount.objects.filter(id=dst_account_id).first()
    if not src_bank_account or not amount or not receipt_id or (dst_account_id and not dst_account):
        return {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'msgUnfilledForm'
        }

    # Check amount
    if amount < settings.NOBITEX_OPTIONS['minBankDeposit']:
        return {
            'status': 'failed',
            'code': 'AmountTooLow',
            'message': 'msgBankAmountLow'
        }
    if amount > settings.NOBITEX_OPTIONS['maxBankDeposit']:
        return {
            'status': 'failed',
            'code': 'AmountTooHigh',
            'message': 'msgBankAmountHigh'
        }

    # Check User level limitation
    deposit_eligibility = UserLevelManager.is_eligible_to_rial_deposit(request.user, amount, is_shetab=False)
    if not deposit_eligibility:
        return {
            'status': 'failed',
            'message': 'RialDepositLimitation',
            'code': deposit_eligibility.message,
        }

    # Create bank deposit object
    bank_deposit = BankDeposit(
        user=request.user,
        receipt_id=receipt_id,
        src_bank_account=src_bank_account,
        dst_bank_account='حساب بانکی',
        dst_system_account=dst_account,
        amount=amount,
    )

    # Check IP to be from Iran
    bank_deposit.fill_ip_from_request(request)
    if not bank_deposit.is_iranian:
        if not UserLevelManager.is_eligible_to_rial_deposit_from_foreign_ip(request.user):
            return {
                'status': 'failed',
                'code': 'UnauthorizedIP',
                'message': 'Please use an Iranian IP for bank deposits.',
            }

    # Validate and convert deposited at date
    date = request.g('depositedAt')
    try:
        deposited_at = jdatetime.datetime.strptime(date, '%Y/%m/%d').date().togregorian()
    except:
        deposited_at = None
    if not deposited_at:
        return {
            'status': 'failed',
            'code': 'InvalidDate',
            'message': 'msgDateInvalid',
        }
    bank_deposit.deposited_at = deposited_at
    bank_deposit.fee = bank_deposit.get_fee()

    # Save deposit
    try:
        with transaction.atomic():
            bank_deposit.save()
    except IntegrityError:
        return {
            'status': 'failed',
            'code': 'ReceiptAlreadyExist',
            'message': 'msgReceiptAlreadyExist',
        }

    return {
        'status': 'ok',
        'bankDeposit': bank_deposit,
    }


@ratelimit(key='user_or_ip', rate='3/m', block=True)
@measure_api_execution(api_label='walletCreateShetabDeposit')
@api
def wallets_deposit_shetab(request):
    user = request.user
    amount = parse_money(request.g('amount'), required=True)
    amount = round(amount)
    next_redirect_url = request.g('nextRedirectUrl') or None

    # Check app version
    if is_request_from_unsupported_app(request):
        raise SemanticAPIError('PleaseUpdateApp', 'Please Update App')

    # Selecting a card for deposit
    input_selected_card = request.g('selectedCard')
    if not input_selected_card or '-' in str(input_selected_card):
        return {
            'status': 'failed',
            'code': 'InvalidBankCard',
            'message': 'Please select a valid card.',
        }
    selected_card = parse_int(input_selected_card, required=True)
    selected_card = BankCard.objects.filter(
        pk=selected_card,
        user=user,
        is_deleted=False,
        is_temporary=False,
        confirmed=True,
    ).first()
    if not selected_card:
        return {
            'status': 'failed',
            'code': 'InvalidBankCard',
            'message': "Invalid bank card '{}', expected ID for an active card.".format(input_selected_card),
        }

    # Check User Restrictions
    if user.is_restricted('ShetabDeposit'):
        return {
            'status': 'failed',
            'code': 'UserDepositRestricted',
            'message': 'ShetabDespoitUnavailable',
        }

    # Check User level limitation
    eligible, details = UserLevelManager.is_eligible_to_rial_deposit(user, amount)
    if not eligible:
        return {
            'status': 'failed',
            'message': 'RialDepositLimitation',
            'code': details,
        }

    # apply ShaparakLimitation after nobitex validation
    if amount > 25_000_000_0:
        return {
            'status': 'failed',
            'message': 'ShaparakLimitation',
            'code': 'سقف واریز در هر تراکنش درگاه بانکی ۲۵ میلیون تومان است.',
        }

    # Special Users
    #  Admin can set a specific gateway for users
    user_specific_gateway = UserPreference.get(user, 'system_shetab_gateway')

    # Select ShetabDeposit Backend
    if user_specific_gateway:
        shetab_deposit_backend = user_specific_gateway
    else:
        shetab_deposit_backend = Settings.get('shetab_deposit_backend')
        # Using nobitex sandbox environment for testing
        if not settings.IS_PROD:
            shetab_deposit_backend = 'nobitex'

    # High Risk User - use special broker
    #  if the user is not completely verified yet, we use a specific broker for her
    #  to prevent legal problems. This consideration is only enabled on production
    #  environment, because we have to use Vandar gateway on testnet as it is the
    #  only gateway that provides testing tokens.
    if settings.IS_PROD and user.user_type < User.USER_TYPES.level2:
        shetab_deposit_backend = Settings.get('shetab_deposit_risky_backend', default=shetab_deposit_backend)

    # Toman gateway error on user have more than 20 cards
    if (
        shetab_deposit_backend == 'toman'
        and BankCard.objects.filter(user=user, is_deleted=False, is_temporary=False, confirmed=True).count() > 20
    ):
        shetab_deposit_backend = Settings.get('shetab_deposit_special_users_backend')

    # Parse Shetab Broker
    if shetab_deposit_backend == 'payir':
        broker = ShetabDeposit.BROKER.payir
    elif shetab_deposit_backend == 'payping':
        broker = ShetabDeposit.BROKER.payping
    elif shetab_deposit_backend == 'idpay':
        broker = ShetabDeposit.BROKER.idpay
    elif shetab_deposit_backend == 'vandar':
        broker = ShetabDeposit.BROKER.vandar
    elif shetab_deposit_backend == 'vandar2step':
        broker = ShetabDeposit.BROKER.vandar2step
    elif shetab_deposit_backend == 'jibit':
        broker = ShetabDeposit.BROKER.jibit
    elif shetab_deposit_backend == 'jibit_v2':
        broker = ShetabDeposit.BROKER.jibit_v2
    elif shetab_deposit_backend == 'nobitex':
        broker = ShetabDeposit.BROKER.nobitex
    elif shetab_deposit_backend == 'toman':
        broker = ShetabDeposit.BROKER.toman
    else:
        ShetabGatewayUnavailableWebEngageEvent(user=user).send()
        return {
            'status': 'failed',
            'code': 'InvalidGateway',
            'message': 'ShetabDespoitUnavailable',
        }

    # Create deposit object
    deposit = ShetabDeposit.objects.create(
        user=user,
        selected_card=selected_card,
        amount=amount,
        broker=broker,
        next_redirect_url=next_redirect_url,
    )

    # Check IP to be from Iran
    deposit.fill_ip_from_request(request)
    deposit.save(update_fields=['ip', 'is_iranian'])
    if not deposit.is_iranian:
        if not UserLevelManager.is_eligible_to_rial_deposit_from_foreign_ip(user):
            deposit.status_code = ShetabDeposit.STATUS.invalid_ip
            deposit.save(update_fields=['status_code'])
            return {
                'status': 'failed',
                'code': 'UnauthorizedIP',
                'message': 'Please use an Iranian IP for shetab deposits.',
            }

    # Send factor request to gateway
    deposit.sync(request)

    return {
        'status': 'ok',
        'deposit': deposit,
    }


@ratelimit(key='user_or_ip', rate='30/h', block=True)
@measure_api_execution(api_label='walletGenerateAddress')
@api
@email_required_api
def wallets_generate_address(request):
    """Create blockchain deposit address for a user wallet.

        POST /users/wallets/generate-address
    """
    # Check User level limitation
    user = request.user
    if not UserLevelManager.is_eligible_to_deposit_coin(user):
        return {
            'status': 'failed',
            'code': 'CoinDepositLimitation',
            'message': 'CoinDepositLimitation',
        }

    # Get user wallet
    wallet_pk = request.g('wallet')
    currency = request.g('currency')
    if wallet_pk:
        wallet = get_object_or_404(Wallet, pk=wallet_pk, user=user, type=Wallet.WALLET_TYPE.spot)
    elif currency:
        currency = parse_currency(currency)
        if currency not in ALL_CURRENCIES or (currency in TESTING_CURRENCIES and not is_feature_enabled(user, 'new_coins')):
            return {
                'status': 'failed',
                'code': 'InvalidCurrency',
                'message': 'Currency is not supported yet.',
            }
        wallet = Wallet.get_user_wallet(user, currency)
    else:
        return {
            'status': 'failed',
            'code': 'MissingWallet',
            'message': 'Wallet or currency should be specified.',
        }

    # Parse network and type
    address_type_unparsed = request.g('addressType') or 'default'
    address_type_unparsed = address_type_unparsed.lower()
    network = request.g('network')
    if network is not None:
        network = str(network).upper()
        if network.endswith('-LEGACY'):
            network = network[:-7]
            address_type_unparsed = 'legacy'
    # handle pseudo networks
    contract_address = None
    if network in CurrenciesNetworkName.get_pseudo_network_names() and CurrenciesNetworkName.pseudo_network_support_coin(network, wallet.currency):
        if CurrenciesNetworkName.is_pseudo_network_beta(wallet.currency, network) and not is_feature_enabled(user, 'new_coins'):
            return {
                'status': 'failed',
                'code': 'InvalidCurrency',
                'message': 'Currency is not supported yet.',
            }
        contract_address, network = CurrenciesNetworkName.parse_pseudo_network(wallet.currency, network)

    if network == 'BTCLN':
        return {
            'status': 'failed',
            'code': 'InvalidNetwork',
            'message': 'نسخه‌ی اپلیکیشن شما قدیمی است یا پارامتر‌ها به درستی فرستاده نشده‌اند',
        }
    network = parse_choices(CurrenciesNetworkName, network) or CURRENCY_INFO[wallet.currency]['default_network']
    if address_type_unparsed not in ['default', 'legacy']:
        return {
            'status': 'failed',
            'code': 'AddressTypeInvalid',
            'message': 'Address type is invalid',
        }
    if wallet.currency == Currencies.btc and network == CurrenciesNetworkName.BTC and address_type_unparsed == 'legacy':
        return {
            'status': 'failed',
            'code': 'DepositNotAvailable!',
            'message': 'پشتیبانی از واریز بیت کوین به آدرس های به فرمت لگاسی متوقف شده است میتوانید از آدرس های سگویت استفاده نمایید',
        }
    currency_name = get_currency_codename(wallet.currency)
    network_info = CURRENCY_INFO[wallet.currency]['network_list'].get(network)
    if network_info is None:
        return {
            'status': 'failed',
            'code': 'DepositNotAvailable',
            'message': 'واریز روی شبکه‌ی مورد نظر پشتیبانی نمی‌شود. از واریز روی این شبکه جدا خودداری فرمایید',
        }
    default_deposit_status = 'yes' if network_info.get('deposit_enable', True) else 'no'
    cache_key = f'deposit_enabled_{currency_name}_{network.lower()}'
    if contract_address:
        cache_key += f'_{contract_address}'
    if not Settings.get_trio_flag(
        cache_key,
        default=default_deposit_status,  # all network in network_list filter by withdraw_enable=True
        third_option_value=cache.get(f'binance_deposit_status_{currency_name}_{network}'),
    ):
        return {
            'status': 'failed',
            'code': 'DepositNotAvailable',
            'message': 'واریز روی شبکه‌ی مورد نظر پشتیبانی نمی‌شود. از واریز روی این شبکه جدا خودداری فرمایید',
        }
    address_type = wallet.get_address_type_not_none(network, address_type_unparsed)

    # Generate address
    address = wallet.get_current_deposit_address(create=True, network=network, address_type=address_type, contract_address=contract_address)
    response = {
        'status': 'ok',
        'address': address,
    }
    if network == CurrenciesNetworkName.ONE:
        try:
            response['address'] = eth_to_one_address(address.address)
        except Exception:  # in case of 1- conversion failed 2- address in none in database
            response['address'] = None
    tag = wallet.get_current_deposit_tag(create=True, network=network)
    response['tag'] = tag
    CacheManager.invalidate_user_wallets(user.id)
    return response


@ratelimit(key='user_or_ip', rate='60/2m', block=True)
@measure_api_execution(api_label='walletGetWithdraw')
@api
def withdraws_get(request, withdraw):
    withdraw = get_object_or_404(WithdrawRequest, pk=withdraw, wallet__user=request.user)
    return {
        'status': 'ok',
        'withdraw': withdraw,
    }


@ratelimit(key='user_or_ip', rate='10/h', block=True)
@measure_api_execution(api_label='walletGetWithdrawStatus')
@api
def withdraws_update_status(request, withdraw):
    """ POST /withdraws/<int:withdraw>/update-status
    """
    withdraw = get_object_or_404(WithdrawRequest, pk=withdraw, wallet__user=request.user)

    # Fetch latest payment status
    settlement_manager = withdraw.get_settlement_manager()
    if settlement_manager:
        try:
            settlement_manager.update_status()
        except:
            report_exception()

    return {
        'status': 'ok',
        'withdraw': withdraw,
    }


@ratelimit(key='user_or_ip', rate='10/3m', block=True)
@measure_api_execution(api_label='walletCreateLightningDeposit')
@api
@email_required_api
def wallets_ln_invoice_create(request):
    """ Request a withdraw

        # TODO: Ensure that calls to this API are DB serialized
    """
    from exchange.base.connections import LndClient

    user = request.user
    if not UserLevelManager.is_eligible_to_deposit_coin(user):
        return {
            'status': 'failed',
            'code': 'CoinDepositLimitation',
            'message': 'CoinDepositLimitation'
        }
    wallet = get_object_or_404(Wallet, pk=request.g('wallet'), user=user, type=Wallet.WALLET_TYPE.spot)
    if wallet.user != user:
        raise PermissionDenied
    amount_sat = parse_int(request.g('amount'), required=True)
    if amount_sat < 0:
        return {
            'status': 'failed',
            'code': 'InvalidAmount',
            'message': 'درخواست فرستاده شده در پارامتر amount معتبر نیست',
        }
    if wallet.currency not in SUPPORTED_INVOICE_CURRENCIES:
        return {
            'status': 'failed',
            'code': 'InvalidCurrency',
            'message': 'درخواست فرستاده شده در پارامتر wallet معتبر نیست',
        }
    currency_name = get_currency_codename(wallet.currency)
    network = 'BTCLN'
    if not Settings.get_trio_flag(
        f'deposit_enabled_{currency_name}_{network.lower()}',
        default='yes',  # all network in network_list filter by withdraw_enable=True
        third_option_value=cache.get(f'binance_deposit_status_{currency_name}_{network}'),
    ):
        return {
            'status': 'failed',
            'code': 'CoinDepositDisabled',
            'message': 'CoinDepositDisabled'
        }
    # TODO: this write only for bitcoin
    amount = Decimal(str(amount_sat)) * Decimal('1e-8')
    deposit_info = CURRENCY_INFO[wallet.currency]['network_list'][network].get('deposit_info', {}).get('standard', {})
    deposit_min = Decimal(deposit_info.get('deposit_min', '0'))
    deposit_max = Decimal(deposit_info.get('deposit_max', '0'))
    if not deposit_min <= amount <= deposit_max:
        return {
            'status': 'failed',
            'code': 'InvalidAmount',
            'message': 'مقدار باید بین {} تا {} باشد'.format(
                deposit_min * Decimal('1e8'),
                deposit_max * Decimal('1e8'),
            ),
        }
    try:
        lnd_client = LndClient.get_client()
    except Exception as e:
        report_exception()
        return {
            'status': 'failed',
            'code': 'NotAvailable',
            'message': 'ساخت صورت‌حساب الان امکان پذیر نیست. لطفا بعدا تلاش کنید. در صورت ادامه با پشتیبانی ارتباط بگیرید',
        }
    params = [{
        'amount': amount_sat,
    }, lnd_client.password]
    lnd_invoice = lnd_client.request('add_invoice', params)
    if not lnd_invoice:
        report_event('LND cannot create invoice')
    if lnd_invoice['status'] != 'success':
        report_event('LND cannot create invoice with error', extras={
            'lnd_invoice_status': lnd_invoice['status'],
            'lnd_invoice_code': lnd_invoice['code'],
            'lnd_invoice_message': lnd_invoice['message'],
        })
    lnd_invoice = lnd_invoice['result']
    invoice_hash = lnd_invoice['rHash']
    invoice = lnd_invoice['paymentRequest']
    rial_value = PriceEstimator.get_rial_value_by_best_price(amount, wallet.currency, 'sell')
    deposit = ConfirmedWalletDeposit.objects.create(
        tx_hash=invoice_hash,
        _wallet=wallet,
        amount=amount,
        invoice=invoice,
        rial_value=rial_value
    )
    return {
        'status': 'ok',
        'deposit': deposit,
    }


@ratelimit(key='user_or_ip', rate='60/2m', block=True)
@measure_api_execution(api_label='walletDecodeLightningInvoice')
@api
def wallets_decode_invoice(request):
    user = request.user
    wallet = get_object_or_404(Wallet, pk=request.g('wallet'), user=user, type=Wallet.WALLET_TYPE.spot)
    if wallet.user != user:
        raise PermissionDenied
    invoice = request.g('invoice')
    dec_inv = decode_invoice(invoice, wallet.currency)
    if not dec_inv:
        return {
            'status': 'failed',
            'code': 'InvalidInvoice',
            'message': 'درخواست فرستاده شده در پارامتر invoice معتبر نیست',
        }
    amount = dec_inv['amount']
    address = dec_inv['address']
    network = dec_inv['network']

    default_withdraw_fee = CURRENCY_INFO[wallet.currency]['network_list'][network]['withdraw_fee']
    fee = Settings.get(
        'withdraw_fee_{}_{}'.format(get_currency_codename(wallet.currency), network.lower()),
        default_withdraw_fee,
    )
    # if address == '02b45e6448588de24daf7c773a674ecbcd3cce3bf2cf27428d1ddbf1e6ca034684':
    #     fee = "0"
    return {
        'status': 'ok',
        'amount': amount,
        'address': address,
        'date': dec_inv['date'],
        'fee': fee,
    }


def restrict_coin_withdrawal(user):
    UserRestriction.add_restriction(
        user=user,
        restriction=UserRestriction.RESTRICTION.WithdrawRequestCoin,
        considerations='ایجاد محدودیت یک ساعته برداشت رمز ارز به علت لاگین با دستگاه جدید',
        duration=datetime.timedelta(hours=1),
        description=UserRestrictionsDescription.NEW_DEVICE_LOGIN,
    )
    if user.mobile and Settings.get_flag('send_new_device_sms_notification'):
        UserSms.objects.create(
            user=user,
            tp=UserSms.TYPES.new_device_withdrawal_restriction_notif,
            to=user.mobile,
            text='۱ساعت',
            template=UserSms.TEMPLATES.new_device_withdrawal_restriction_notif,
        )


def is_withdraw_sms_not_required(withdraw_request, api_request):
    return (
        withdraw_request.is_rial
        and not is_from_unsupported_app(api_request, 'remove_rial_otp')
        and Settings.get_flag('remove_rial_otp')
    )


@ratelimit(key='user_or_ip', rate='10/3m', block=True)
@measure_api_execution(api_label='walletRequestWithdraw')
@api
def wallets_withdraw(request):
    """ Request a withdraw

        # TODO: Ensure that calls to this API are DB serialized
    """
    from exchange.wallet.withdraw_method import AutomaticWithdrawMethod

    user = request.user
    wallet = get_object_or_404(Wallet, pk=request.g('wallet'), user=user, type=Wallet.WALLET_TYPE.spot)

    if wallet.currency in TESTING_CURRENCIES and not is_feature_enabled(user, 'new_coins'):
        return {
            'status': 'failed',
            'code': 'InvalidCurrency',
            'message': 'Currency is not supported yet.',
        }

    if wallet.is_crypto_currency and user.has_new_unknown_login(duration=datetime.timedelta(seconds=100)):
        restrict_coin_withdrawal(user)
        return {
            'status': 'failed',
            'code': 'WithdrawUnavailableNewDevice',
            'message': 'به دلیل شناسایی ورود با دستگاه یا مرورگر جدید و افزایش امنیت حساب کاربری شما،'
                       ' امکان برداشت رمزارز از حساب کاربری شما به مدت یک ساعت محدود شده است.'
        }

    invoice = request.g('invoice')
    if invoice:
        dec_inv = decode_invoice(invoice, wallet.currency)
        if not dec_inv:
            return {
                'status': 'failed',
                'code': 'InvalidInvoice',
                'message': 'درخواست فرستاده شده در پارامتر invoice معتبر نیست',
            }
        amount = dec_inv['amount']
        if not amount:
            return {
                'status': 'failed',
                'code': 'InvalidInvoice',
                'message': 'مقدار صورتحساب خالی تنظیم شده است. لطفا مقدار برداشت را در زمان ساخت invoice بگذارید.',
            }
        network = dec_inv['network']
        default_withdraw_fee = CURRENCY_INFO[wallet.currency]['network_list'][network]['withdraw_fee']
        fee = Settings.get(
            'withdraw_fee_{}_{}'.format(get_currency_codename(wallet.currency), network.lower()),
            default_withdraw_fee,
        )
        target_address = dec_inv['address']
        if target_address == '02b45e6448588de24daf7c773a674ecbcd3cce3bf2cf27428d1ddbf1e6ca034684':
            return {
                'status': 'failed',
                'code': 'InvalidInvoice',
                'message': 'به جای انتقال داخلی لایتنینگ نوبیتکس از شبکه عادی با فی صفر استفاده نمایید.',
            }
        amount = amount + Decimal(fee)
    else:
        amount = parse_money(request.g('amount'), required=True)
        target_address = request.g('address')
        network = None

    if not credit_check_if_user_could_withdraw(request.user.id, wallet.currency, amount,):
        return {
            'status': 'failed',
            'code': 'WithdrawUnavailableCreditDebt',
            'message': 'با توجه به اعتبار vip دریافت شده، ایجاد درخواست برداشت ممکن نیست.'
        }

    explanations = request.g('explanations', '')
    no_tag = parse_bool(request.g('noTag'))
    tag = request.g('tag')
    network_input = request.g('network')
    # handle pseudo networks
    contract_address = None
    if network_input in CurrenciesNetworkName.get_pseudo_network_names() and CurrenciesNetworkName.pseudo_network_support_coin(network_input, wallet.currency):
        if CurrenciesNetworkName.is_pseudo_network_beta(wallet.currency, network_input) and not is_feature_enabled(user, 'new_coins'):
            return {
                'status': 'failed',
                'code': 'InvalidCurrency',
                'message': 'Currency is not supported yet.',
            }
        contract_address, network_input = CurrenciesNetworkName.parse_pseudo_network(wallet.currency, network_input)
    otp = request.headers.get('x-totp')

    if network_input == 'BTCLN' and not invoice:
        return {
            'status': 'failed',
            'code': 'InvalidInvoice',
            'message': 'نسخه‌ی اپلیکیشن شما قدیمی است یا پارامتر‌ها به درستی فرستاده نشده‌اند',
        }
    withdraw_permit = None
    if WithdrawRequest.is_user_not_allowed_to_withdraw(user, wallet):
        withdraw_permit = WithdrawRequestPermit.get(request.user, wallet.currency, amount)
        if not withdraw_permit:
            metric_incr(
                'metric_withdraw_count',
                labels=(wallet.get_currency_display(), network or network_input, 'RestrictedRequest'),
            )
            return {
                'status': 'failed',
                'code': 'WithdrawUnavailable',
                'message': 'WithdrawUnavailable',
            }

    # Target Address Validation
    target_address = str(target_address or '').strip()
    if not target_address:
        return {'status': 'failed', 'code': 'MissingTargetAddress', 'message': 'آدرس مقصد وارد نشده است'}
    if wallet.currency == RIAL:
        network = 'FIAT_MONEY'
        bank_account = get_object_or_404(
            BankAccount, user=user, pk=target_address,
            confirmed=True, is_deleted=False, is_temporary=False)
        target_address = bank_account.display_name
        if bank_account.bank_id == 998 and not Settings.get_json_object('withdraw_id', {}).get('jibit_withdraw_enabled'):
            return {
                'status': 'failed',
                'code': 'JibitPaymentIdDeactived',
                'message': 'برداشت شناسه دار جیبیت فعال نمی باشد.'
            }

        if (
            bank_account.bank_id == BankAccount.BANK_ID.vandar and
            not Settings.get_json_object('withdraw_id', {}).get('vandar_withdraw_enabled')
        ):
            return {
                'status': 'failed',
                'code': 'VandarPaymentIdDeactivated',
                'message': 'Vandar withdraw is disabled.',
            }
    else:
        bank_account = None
        if network is None:
            is_valid, network = validate_crypto_address_v2(target_address, wallet.currency, network=network_input)
            if not is_valid:
                return {'status': 'failed', 'code': 'InvalidTargetAddress', 'message': 'لطفا آدرس را بررسی کنید یا شبکه را به درستی انتخاب نمایید'}
            if network == 'BSC' and not network_input:
                return {
                    'status': 'failed',
                    'code': 'InvalidTargetAddress',
                    'message': 'لطفا آدرس را بررسی کنید یا شبکه را به درستی انتخاب نمایید',
                }
            if network_input and network_input != network:
                return {
                    'status': 'failed',
                    'code': 'InvalidTargetAddress',
                    'message': 'آدرس برای شبکه‌ای که در پارامتر network فرستاده شده نیست',
                }
        if not AddressBook.is_address_ok_to_withdraw(user, target_address, network, tag):
            return {
                'status': 'failed',
                'code': 'NotWhitelistedTargetAddress',
                'message': 'Target address is not whitelisted to withdraw!'
            }

    is_vandar = bank_account and bank_account.bank_id == BankAccount.BANK_ID.vandar

    # Check withdraw for currency/network is enabled
    if not CURRENCY_INFO.get(wallet.currency, {}).get('network_list', {}).get(network, {}).get('withdraw_enable', True):
        metric_incr(f'metric_withdraw_count__{wallet.get_currency_display()}_{network}_WithdrawCurrencyUnavailable')
        return {'status': 'failed', 'code': 'WithdrawCurrencyUnavailable', 'message': 'WithdrawCurrencyUnavailable'}
    # Check if withdrawal for this currency is temporary disabled
    currency_name = get_currency_codename(wallet.currency)
    flag_key = 'withdraw_enabled_{}_{}'.format(currency_name, network.lower())
    if contract_address:
        flag_key += f'_{contract_address}'
    if not Settings.get_trio_flag(
        flag_key,
        default='yes',  # all network in network_list filter by withdraw_enable=True
        third_option_value=cache.get(f'binance_withdraw_status_{currency_name}_{network}'),
    ):
        return {
            'status': 'failed',
            'code': '{}WithdrawDisabled'.format(currency_name.upper()),
            'message': 'Withdrawals for {} is temporary disabled'.format(currency_name.upper()),
        }
    # Check Address Tag
    if wallet.is_address_tag_required(network=network) and not no_tag:
        if not validate_memo_v2(memo=tag, currency=wallet.currency, network=network):
            metric_incr(f'metric_withdraw_count__{wallet.get_currency_display()}_{network}_TagError')
            return {
                'status': 'failed',
                'code': 'InvalidAddressTag',
                'message': 'Invalid Tag',
            }
        # TODO This is a HotFix and should be replaced with more proper way for handling xrp tag max value
        if network == 'XRP':
            MAX_XRP_TAG_VALUE = 2 ** 32
            tag = parse_int(tag)
            if tag >= MAX_XRP_TAG_VALUE:
                metric_incr(f'metric_withdraw_count__{wallet.get_currency_display()}_{network}_TagError')
                return {
                    'status': 'failed',
                    'code': 'InvalidAddressTag',
                    'message': 'Invalid Tag',
                }
        is_integer = wallet.currency in INTEGER_ONLY_TAG_CURRENCIES
        tag = parse_tag(tag, is_integer) or None
        if not tag:
            metric_incr(f'metric_withdraw_count__{wallet.get_currency_display()}_{network}_TagError')
            return {
                'status': 'failed',
                'code': 'MissingAddressTag',
                'message': 'A tag parameter is required for withdrawals of this coin.',
            }
    elif wallet.is_address_tag_required(network=network) and no_tag:
        # TODO: Bellow line of code must be change with network parameter
        exchanges_address = EXCHANGE_ADDRESS_TAG_REQUIRED.get(wallet.currency)
        if exchanges_address and target_address in exchanges_address:
            metric_incr(f'metric_withdraw_count__{wallet.get_currency_display()}_{network}_TagError')
            return {
                'status': 'failed',
                'code': 'ExchangeRequiredTag',
                'message': 'ExchangeRequiredTag',
            }
        if tag:
            metric_incr(f'metric_withdraw_count__{wallet.get_currency_display()}_{network}_TagError')
            return {
                'status': 'failed',
                'code': 'RedundantTag',
                'message': 'Redundant Tag',
            }
        tag = None
    else:
        tag = None

    # Verify otp
    is_2fa_enabled = user.requires_2fa
    are_2fa_and_otp_required = AddressBook.are_2fa_and_otp_required(
        user=user,
        address=target_address,
        network=network,
        tag=tag,
        is_crypto_currency=wallet.is_crypto_currency,
    )

    if are_2fa_and_otp_required and user.user_type >= User.USER_TYPES.level2 and not wallet.is_rial \
        and not is_2fa_enabled:
        return {
            'status': 'failed',
            'code': 'PleaseEnable2FA',
            'message': 'لطفاً ابتدا شناسایی دوعاملی را برای حساب خود فعال کنید.',
        }
    if is_2fa_enabled and are_2fa_and_otp_required and not check_user_otp(otp, user):
        metric_incr(f'metric_withdraw_count__{wallet.get_currency_display()}_{network}_Invalid2FA')
        return {'status': 'failed', 'code': 'Invalid2FA', 'message': 'msgInvalid2FA'}

    # Check User level limitation
    if not UserLevelManager.is_eligible_to_withdraw(user, wallet.currency, amount, network):
        return {'status': 'failed', 'code': 'WithdrawAmountLimitation', 'message': 'WithdrawAmountLimitation'}
    if amount > wallet.active_balance:
        return {'status': 'failed', 'code': 'InsufficientBalance', 'message': 'Insufficient Balance'}
    if not WithdrawRequest.check_user_limit(user, wallet.currency):
        return {'status': 'failed', 'code': 'WithdrawLimitReached', 'message': 'msgWithdrawLimitReached'}

    # Check minimum withdraw amount
    min_withdraw_amount = AutomaticWithdrawMethod.get_withdraw_min(
        wallet.currency, network=network, contract_address=contract_address
    )
    withdraw_fee = AutomaticWithdrawMethod.get_withdraw_fee(wallet.currency, network=network, contract_address=contract_address)
    if withdraw_fee is not None:
        min_withdraw_amount = max(min_withdraw_amount, withdraw_fee)
    if amount < min_withdraw_amount:
        return {'status': 'failed', 'code': 'AmountTooLow', 'message': 'msgAmountTooLow'}

    # Check maximum withdraw amount
    max_withdraw_amount = AutomaticWithdrawMethod.get_withdraw_max(wallet.currency, network, contract_address)

    if wallet.currency == RIAL:
        if is_vandar:
            max_withdraw_amount = Settings.get_decimal('vandar_max_withdrawal', '500_000_000_0')
        else:
            max_withdraw_amount = Decimal(Settings.get_value('max_rial_withdrawal', max_withdraw_amount))

    if amount > max_withdraw_amount:
        return {'status': 'failed', 'code': 'AmountTooHigh', 'message': 'msgAmountTooHigh'}

    if wallet.currency != RIAL:
        max_decimal_places = Decimal(CURRENCY_INFO.get(wallet.currency, {}).get('network_list', {}).get(network, {}).get('withdraw_integer_multiple', '0.00000001'))
        try:
            max_decimal_places = int(f"{max_decimal_places:.3E}".split('E-')[1])  # to export number of decimals after point
        except IndexError:
            max_decimal_places = 0
        decimals_after_point = get_decimal_places(amount)
        if decimals_after_point > max_decimal_places:
            return {'status': 'failed', 'code': 'InvalidAmount', 'message': f'Coin maximum decimal places is {max_decimal_places}'}

    # Check if the user has valid mobile code which is required for withdraw
    if not user.get_verification_profile().has_verified_mobile_number:
        return {
            'status': 'failed',
            'code': 'InvalidMobileNumber',
            'message': 'Verified mobile number is required for withdraw.',
        }

    if wallet.is_rial:
        if not is_vandar and not WithdrawRequest.can_withdraw_shaba(wallet=wallet, target_account=bank_account, amount=amount):
            return {
                'status': 'failed',
                'code': 'ShabaWithdrawCannotProceed',
                'message': 'Shaba withdraw cannot proceed. Daily Shaba withdraw limit Exceeded.',
            }

        if is_vandar and not UserLevelManager.is_eligible_to_vandar_withdraw(user):
            return {
                'status': 'failed',
                'code': 'VandarWithdrawNotEnabled',
                'message': 'Vandar withdraw is not available for this user.',
            }

    withdraw_creation_flag = f'withdraw_creation_{get_currency_codename(wallet.currency)}_{network.lower()}'
    if contract_address:
        withdraw_creation_flag += f'_{contract_address}'
    if not Settings.get_flag(
        withdraw_creation_flag,
        default='yes',  # by default withdraw creation is active
    ):
        return {
            'status': 'failed',
            'code': 'NewWithdrawSuspended',
            'message': 'به‌دلیل شلوغی شبکه، ثبت برداشت رمزارز موقتا امکان‌پذیر نیست؛ لطفا بعدا دوباره تلاش کنید',
        }
    # Everything is OK, create request
    ip = get_client_ip(request)
    ip = ip[0] if ip else None
    withdraw_request = WithdrawRequest(
        wallet=wallet,
        target_address=target_address,
        target_account=bank_account,
        amount=amount,
        explanations=explanations,
        tag=tag,
        network=network,
        ip=ip,
        invoice=invoice,
        contract_address=contract_address,
        fee=withdraw_fee,
    )
    if is_withdraw_sms_not_required(withdraw_request, request):
        withdraw_request.is_otp_required = False
    withdraw_request.save()

    if withdraw_permit:
        withdraw_permit.mark_as_used(withdraw_request)

    metric_incr(f'metric_withdraw_count__{wallet.get_currency_display()}_{network}_new')

    return {
        'status': 'ok',
        'withdraw': withdraw_request,
    }


@ratelimit(key='user_or_ip', rate='30/h', block=True)
@measure_api_execution(api_label='walletConfirmWithdraw')
@api
def wallets_withdraw_confirm(request):
    withdraw_id = parse_int(request.g('withdraw'), required=True)
    withdraw_request = (
        WithdrawRequest.objects.select_related('wallet').select_for_update(of=('self',)).get(pk=withdraw_id)
    )
    user = request.user
    if withdraw_request.wallet.user != user:
        raise PermissionDenied

    duration_between_withdraw_request_and_confirm = int((ir_now() - withdraw_request.created_at).total_seconds() * 1000)

    new_withdraw_permit = None
    if WithdrawRequest.is_user_not_allowed_to_withdraw(user, withdraw_request.wallet):
        used_withdraw_permit = WithdrawRequestPermit.objects.filter(
            user=request.user, withdraw_request=withdraw_request, is_active=False
        ).first()
        new_withdraw_permit = (
            WithdrawRequestPermit.get(request.user, withdraw_request.currency, withdraw_request.amount)
            if used_withdraw_permit is None
            else None
        )
        if new_withdraw_permit is None and used_withdraw_permit is None:
            raise NobitexAPIError(message='WithdrawUnavailable', description='WithdrawUnavailable', status_code=403)

    are_2fa_and_otp_required = AddressBook.are_2fa_and_otp_required(
        user=withdraw_request.wallet.user,
        address=withdraw_request.target_address,
        network=withdraw_request.network,
        tag=withdraw_request.tag,
        is_crypto_currency=withdraw_request.wallet.is_crypto_currency)

    rial_otp_required = True
    if is_withdraw_sms_not_required(withdraw_request, request):
        rial_otp_required = False

    if are_2fa_and_otp_required and rial_otp_required:
        otp = request.g('otp')
        is_valid = withdraw_request.verify_otp(otp)

        validity = 'validOTP' if is_valid else 'invalidOTP'
        try:
            log_time(
                f'withdraw_request_to_confirm_duration__{validity}',
                duration_between_withdraw_request_and_confirm,
            )
        except Exception:
            report_exception()

        if not is_valid:
            return {
                'status': 'failed',
            }

    if not UserLevelManager.is_eligible_to_withdraw(
        user, withdraw_request.currency, withdraw_request.amount, withdraw_request.network
    ):
        return {
            'status': 'failed',
            'code': 'WithdrawAmountLimitation',
            'message': 'WithdrawAmountLimitation'
        }

    if withdraw_request.amount > withdraw_request.wallet.active_balance:
        return {'status': 'failed', 'code': 'InsufficientBalance', 'message': 'Insufficient Balance'}
    if withdraw_request and withdraw_request.wallet.is_rial and not withdraw_request.can_withdraw_shaba(
        wallet=withdraw_request.wallet, amount=withdraw_request.amount, target_account=withdraw_request.target_account):
        return {
            'status': 'failed',
            'code': 'ShabaWithdrawCannotProceed',
            'message': 'Shaba withdraw cannot proceed. Daily Shaba withdraw limit Exceeded.',
        }
    withdraw_request.do_verify()
    if new_withdraw_permit:
        new_withdraw_permit.mark_as_used(withdraw_request)
    metric_incr(
        f'metric_withdraw_count__{withdraw_request.wallet.get_currency_display()}_{withdraw_request.network}_confirmed'
    )

    return {
        'status': 'ok',
        'withdraw': withdraw_request,
    }


@ratelimit(key='user_or_ip', rate='20/h', block=True)
@measure_api_execution(api_label='walletDirectConfirmWithdraw')
@public_api
def wallets_withdraw_direct_confirm(request, withdraw, token):
    try:
        withdraw_request: WithdrawRequest = (
            WithdrawRequest.objects.select_related('wallet')
            .select_for_update(of=('self',))
            .filter(pk=withdraw, token=token)
            .first()
        )
    except ValidationError:
        withdraw_request = None
    if withdraw_request and withdraw_request.wallet.is_rial and not withdraw_request.can_withdraw_shaba(
        wallet=withdraw_request.wallet, amount=withdraw_request.amount, target_account=withdraw_request.target_account):
        return render(request, 'wallet/withdraw_confirm_failure.html', {'status': 'shaba_limited'})
    if not withdraw_request or withdraw_request.is_expired or withdraw_request.amount > withdraw_request.wallet.active_balance:
        return render(request, 'wallet/withdraw_confirm_failure.html', {'status': 'bad_request'})
    if not UserLevelManager.is_eligible_to_withdraw(
        withdraw_request.wallet.user, withdraw_request.currency, withdraw_request.amount, withdraw_request.network
    ):
        return render(request, 'wallet/withdraw_confirm_failure.html', {'status': 'limited'})
    withdraw_request.do_verify()
    return render(request, 'wallet/withdraw_confirm_success.html', {})


@ratelimit(key='user_or_ip', rate='10/m', block=True)
@ratelimit(key='user_or_ip', rate='60/h', block=True)
@measure_api_execution(api_label='walletCancelWithdraw')
@api
def wallets_withdraw_canceled(request):
    """Cancel a withdraw request.

        POST /users/wallets/withdraw-cancel
    """
    withdraw_id = parse_int(request.g('withdraw'), required=True)
    withdraw_request = get_object_or_404(
        WithdrawRequest,
        pk=withdraw_id,
        wallet__user=request.user,
    )

    if settings.WITHDRAW_ENABLE_CANCEL:
        canceled = withdraw_request.cancel_request()
    else:
        canceled = False
    if not canceled:
        return {
            'status': 'failed',
            'code': 'NotCancelable',
            'message': 'Withdraw is not cancelable',
        }
    return {
        'status': 'ok',
        'withdraw': withdraw_request,
    }


@ratelimit(key='user_or_ip', rate=get_api_ratelimit('10/10m'), block=True)
@measure_api_execution(api_label='walletConvertBalance')
@api
def wallets_convert(request):
    """Convert Funds

        POST /users/wallets/convert
    """
    # Source Client Detection
    ua = request.headers.get('user-agent') or 'unknown'
    channel = MarketManager.detect_order_channel(ua, is_convert=True)

    # Check app version
    if is_request_from_unsupported_app(request):
        return Response({'status': 'failed', 'code': 'PleaseUpdateApp', 'message': 'Please Update App'}, status=422)

    # Check User Restrictions
    if request.user.is_restricted('Trading'):
        return {'status': 'failed', 'code': 'TradingUnavailable', 'message': 'TradingUnavailable'}

    # Parse currencies to convert
    sources = request.g('srcCurrency')
    dst_currency = parse_currency(request.g('dstCurrency'), required=True)
    if not sources:
        return {
            'status': 'failed',
            'message': 'srcCurrecny parameter is required',
            'code': 'RequiredParameter'
        }
    sources = [parse_currency(src, required=True) for src in sources.split(',')]

    # Convert (Place conversion orders)
    wallets = Wallet.get_user_wallets(user=request.user, tp=Wallet.WALLET_TYPE.spot).filter(
        currency__in=sources).exclude(balance=Decimal('0'))
    for wallet in wallets:
        MarketManager.create_sell_whole_balance_order(wallet, dst_currency, channel=channel)
    return {
        'status': 'ok',
    }


class TransferBalance(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='10/m', method='POST'))
    @method_decorator(measure_api_execution(api_label='walletTransferBalance'))
    def post(self, request):
        """API for transferring balance between user wallets

            POST /wallets/transfer
        """
        currency = parse_currency(self.g('currency'), required=True)
        amount = parse_money(self.g('amount'), required=True)
        src_type = parse_choices(Wallet.WALLET_TYPE, self.g('src'), required=True)
        dst_type = parse_choices(Wallet.WALLET_TYPE, self.g('dst'), required=True)

        if src_type in [Wallet.WALLET_TYPE.credit, Wallet.WALLET_TYPE.debit]:
            raise NobitexAPIError(
                status_code=200,
                message='InvalidSrc',
                description=f"{self.g('src')} wallet type is not allowed in srcType",
            )
        if dst_type == Wallet.WALLET_TYPE.debit:
            raise NobitexAPIError(
                status_code=200,
                message='InvalidDst',
                description="debit wallet type is not allowed in dstType",
            )

        try:
            src_wallet, dst_wallet, _, _ = transfer_balance(request.user, currency, amount, src_type, dst_type)
        except TransferException as ex:
            raise NobitexAPIError(ex.code, ex.message) from ex

        return self.response(
            {
                'status': 'ok',
                'srcWallet': src_wallet,
                'dstWallet': dst_wallet,
            }
        )


class BulkTransferBalance(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='10/m', method='POST'))
    @method_decorator(measure_api_execution(api_label='walletBulkTransferBalance'))
    def post(self, request):
        """API for bulk transferring balance between user wallets

        POST /wallets/bulk-transfer
        """

        data = parse_bulk_wallet_transfer(request.data, max_len=20, wallet_choices=Wallet.WALLET_TYPE, required=True)
        if data['src_type'] in [Wallet.WALLET_TYPE.credit, Wallet.WALLET_TYPE.debit]:
            raise NobitexAPIError(
                status_code=422,
                message='InvalidSrc',
                description=f"{request.data['srcType']} wallet type is not allowed in srcType",
            )
        if data['dst_type'] == Wallet.WALLET_TYPE.debit:
            raise NobitexAPIError(
                status_code=422,
                message='InvalidDst',
                description="debit wallet type is not allowed in dstType",
            )

        result, _ = create_bulk_transfer(request.user, data)
        return self.response(
            {
                'status': 'ok',
                'result': serialize(result, opts={'no_deposit_addresses': True}),
            },
        )


class WalletBulkTransferRequestsListView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='20/m', method='GET'))
    @method_decorator(measure_api_execution(api_label='walletBulkTransferRequestList'))
    def get(self, request):
        src_type = parse_choices(Wallet.WALLET_TYPE, self.g('srcType'), required=False)
        dst_type = parse_choices(Wallet.WALLET_TYPE, self.g('dstType'), required=False)
        transfer_requests = WalletBulkTransferRequest.objects.filter(user=request.user).order_by('-created_at')

        if src_type is not None:
            transfer_requests = transfer_requests.filter(src_wallet_type=src_type)

        if dst_type is not None:
            transfer_requests = transfer_requests.filter(dst_wallet_type=dst_type)

        paginated_result, has_next = paginate(transfer_requests, request=self, check_next=True)
        return self.response({'status': 'ok', 'result': paginated_result, 'hasNext': has_next})


#####################
# Webhooks API
#####################
@csrf_exempt
@require_http_methods(["POST"])
def btc_blockcypher_webhook(request):
    if request.GET.get('secret') != settings.BLOCKCYPHER_WEBHOOK_SECRET:
        return HttpResponse(status=401)

    tx_info = json.loads(request.body)
    return BTCBlockcypherWebhookParser(currency=Currencies.btc).webhook_parse(tx_info)


@require_http_methods(["POST"])
def ltc_blockcypher_webhook(request):
    if request.GET.get('secret') != settings.BLOCKCYPHER_WEBHOOK_SECRET:
        return HttpResponse(status=401)

    tx_info = json.loads(request.body)
    return BTCBlockcypherWebhookParser(currency=Currencies.ltc).webhook_parse(tx_info)


@public_post_api
def doge_blockcypher_webhook(request):
    if request.GET.get('secret') != settings.BLOCKCYPHER_WEBHOOK_SECRET:
        return HttpResponse(status=401)

    tx_info = json.loads(request.body)
    return BTCBlockcypherWebhookParser(currency=Currencies.doge).webhook_parse(tx_info)


@basic_auth_api
def btc_blocknative_webhook(request, username, password):
    if username != settings.BLOCKNATIVE_WEBHOOK_USERNAME or not compare_digest(password, settings.BLOCKNATIVE_WEBHOOK_SECRET):
        report_event("[BlockNative Webhook]: basic authentication failed")
        return HttpResponse(status=400)

    tx_info = json.loads(request.body)
    return BTCBlocknativeWebhookParser(currency=Currencies.btc).webhook_parse(tx_info)


@basic_auth_api
def eth_blocknative_webhook(request, username, password):
    if username != settings.BLOCKNATIVE_WEBHOOK_USERNAME or not compare_digest(password, settings.BLOCKNATIVE_WEBHOOK_SECRET):
        report_event("[BlockNative Webhook]: basic authentication failed")
        return HttpResponse(status=400)

    tx_info = json.loads(request.body)
    return ETHBlocknativeWebhookParser(currency=Currencies.eth).webhook_parse(tx_info)


@public_post_api
def xrpl_webhook(request):
    if request.GET.get('secret') != settings.XRPL_WEBHOOK_SECRET:
        return HttpResponse(status=401)

    tx_info = json.loads(request.body)
    return XRPLWebhookParser(currency=Currencies.xrp).webhook_parse(tx_info)


class CreateWalletBIP39View(FormView, UserPassesTestMixin):
    template_name = 'wallet/wallet_create.html'
    form_class = CreateWalletBIP39Form

    def test_func(self):
        return admin_access(self.request.user)

    def form_valid(self, form):
        currency = int(form.cleaned_data['currency'])
        xpub = form.cleaned_data['xpub']
        number = int(form.cleaned_data['number'])
        wallet_name = form.cleaned_data['wallet_name']
        base_index = form.cleaned_data['base_index'] or 0

        method = BLOCKCHAIN_WALLET_CLASS.get(currency)
        if not method:
            msg = '{} is not in active currencies yet!'.format(currency)
            form.add_error('currency', msg)
            return super().form_invalid(form)
        method.create_wallets(xpub, number, wallet_name, base_index)
        return self.render_to_response(self.get_context_data(result=True, result_msg='Wallets are successfully created.'))


class CreateWalletFromColdView(FormView, UserPassesTestMixin):
    template_name = 'wallet/wallet_create_from_cold.html'
    form_class = CreateWalletFromColdForm

    def test_func(self):
        return admin_access(self.request.user)

    def form_valid(self, form):
        currency = int(form.cleaned_data['currency'])
        token = form.cleaned_data['token']
        wallet_name = form.cleaned_data['wallet_name']

        result_msg = GeneralBlockchainWallet.create_wallet_from_cold(token=token, currency=currency, wallet_name=wallet_name)
        return self.render_to_response(self.get_context_data(result=True, result_msg=result_msg))


class CreateWalletView(FormView, UserPassesTestMixin):
    template_name = 'wallet/wallet_create.html'
    form_class = CreateWalletForm

    def test_func(self):
        return admin_access(self.request.user)

    def form_valid(self, form):
        currency = int(form.cleaned_data['currency'])
        addresses = form.cleaned_data['addresses']
        wallet_name = form.cleaned_data['wallet_name']
        addresses = addresses.replace(' ', '').replace('[', '').replace(']', '').replace('"', '').replace('\'', '')
        addresses = re.split('[\n,]', addresses)
        for address in addresses:
            address = "".join(address.split())
            if not address or len(address) == 0:
                continue
            try:
                AvailableDepositAddress.objects.get(currency=currency, address=address)
            except AvailableDepositAddress.DoesNotExist:
                AvailableDepositAddress.objects.create(
                    currency=currency,
                    address=address,
                    description="{}".format(wallet_name)
                )
        return self.render_to_response(self.get_context_data(result=True, result_msg='Wallets are successfully created.'))


class FreezeTronWalletView(FormView, UserPassesTestMixin):
    template_name = 'wallet/tron_wallet_freeze.html'
    form_class = FreezeTronWalletForm

    def test_func(self):
        return admin_access(self.request.user)

    def form_valid(self, form):
        resource = form.cleaned_data['resource']
        receiver_account = form.cleaned_data['receiver_account']
        amount = int(form.cleaned_data['amount'])

        method = BLOCKCHAIN_WALLET_CLASS.get(Currencies.trx)
        if not method:
            msg = "{} is not in active currencies yet!".format(get_currency_codename(Currencies.trx))
            form.add_error('currency', msg)
            return super().form_invalid(form)
        response = method.freeze_wallet(amount, resource, receiver_account)
        print(response)
        if response.get('status') != 'success':
            m = "Error: {}".format(response.get('error'))
            print(m)
            return self.render_to_response(self.get_context_data(error=True, error_msg=m))
        return self.render_to_response(
            self.get_context_data(result=True, result_msg='Successfully freeze the hot wallet.')
        )


class UnfreezeTronWalletView(FormView, UserPassesTestMixin):
    template_name = 'wallet/tron_wallet_unfreeze.html'
    form_class = UnfreezeTronWalletForm

    def test_func(self):
        return admin_access(self.request.user)

    def form_valid(self, form):
        resource = form.cleaned_data['resource']
        receiver_account = form.cleaned_data['receiver_account']

        method = BLOCKCHAIN_WALLET_CLASS.get(Currencies.trx)
        if not method:
            msg = "{} is not in active currencies yet!".format(get_currency_codename(Currencies.trx))
            form.add_error('currency', msg)
            return super().form_invalid(form)
        response = method.unfreeze_wallet(resource, receiver_account)
        if response.get('status') != 'success':
            m = "Error: {}".format(response.get('error'))
            print(m)
            return self.render_to_response(self.get_context_data(error=True, error_msg=m))
        return self.render_to_response(
            self.get_context_data(result=True, result_msg='Successfully unfreeze the hot wallet.')
        )


class MintTronZWalletView(FormView, UserPassesTestMixin):
    template_name = 'wallet/tronz_wallet_mint.html'
    form_class = MintTronZWalletForm

    def test_func(self):
        return admin_access(self.request.user)

    def form_valid(self, form):
        currency = int(form.cleaned_data['currency'])
        amount = int(form.cleaned_data['amount'])

        method = BLOCKCHAIN_WALLET_CLASS.get(Currencies.trx)
        if not method:
            msg = "{} is not in mint-able currencies yet!".format(get_currency_codename(Currencies.trx))
            form.add_error('currency', msg)
            return super().form_invalid(form)
        response = method.mint_wallet(amount, currency)
        if response.get('status') != 'success':
            m = "Error: {}".format(response.get('error'))
            print(m)
            return self.render_to_response(self.get_context_data(error=True, error_msg=m))
        return self.render_to_response(
            self.get_context_data(result=True, result_msg='Successfully mint to the hot wallet.')
        )


class BalanceTronZWalletView(FormView, UserPassesTestMixin):
    template_name = 'wallet/tronz_wallet_balance.html'
    form_class = BalanceTronZWalletForm

    def test_func(self):
        return admin_access(self.request.user)

    def form_valid(self, form):
        currency = int(form.cleaned_data['currency'])

        method = BLOCKCHAIN_WALLET_CLASS.get(Currencies.trx)
        if not method:
            msg = "{} is not in z-address currencies yet!".format(get_currency_codename(Currencies.trx))
            form.add_error('currency', msg)
            return super().form_invalid(form)
        response = method.ztron_balance_wallet(currency)
        if response.get('status') != 'success':
            m = "Error: {}".format(response.get('error'))
            print(m)
            return self.render_to_response(self.get_context_data(error=True, error_msg=m))
        return self.render_to_response(
            self.get_context_data(result=True, result_msg=response)
        )


class UpdateDepositWallet(FormView, UserPassesTestMixin):
    template_name = 'wallet/update_deposit.html'
    form_class = UpdateDepositForm

    def test_func(self):
        return admin_access(self.request.user)

    def form_valid(self, form):
        email = form.cleaned_data['email']
        currency = int(form.cleaned_data['currency'])

        addresses = WalletDepositAddress.objects.filter(currency=currency, wallet__user__email=email)
        for address in addresses:
            refresh_address_deposits(address)
        return self.render_to_response(
            self.get_context_data(result=True, result_msg='Successfully send the refresh request for the wallet. If it still doesn\'t update inform technical teams.')
        )


@api
@ratelimit(key='user_or_ip', rate='180/h', block=True)
def internal_transfer_receipt(request):
    uid = parse_uuid(request.g('uid'), required=True)
    withdraw = WithdrawRequest.objects.select_related('wallet').filter(
        status__in=WithdrawRequest.STATUSES_COMMITED,
        uid=uid
    ).first()
    if not withdraw:
        return {
            'status': 'failed',
            'code': 'InvalidUID',
            'message': 'Invalid UID',
        }
    receipt = {
        'date': withdraw.created_at,
        'currency': get_currency_codename(withdraw.wallet.currency),
        'amount': withdraw.amount.quantize(
            settings.NOBITEX_OPTIONS['minWithdraws'].get(withdraw.wallet.currency, Decimal('0.01'))
        ),
        'to': withdraw.target_address,
        'tag': withdraw.tag,
    }
    return {
        'status': 'ok',
        'receipt': receipt,
    }


class ExtractContractAddressesView(FormView, UserPassesTestMixin):
    template_name = 'wallet/extract_contract_addresses.html'
    form_class = ExtractContractAddressesForm

    def test_func(self):
        return admin_access(self.request.user)

    def form_valid(self, form):
        network = form.cleaned_data['network']
        currency = form.cleaned_data['currency'] or None
        gas_price = form.cleaned_data['gas_price'] or None
        threshold = form.cleaned_data['threshold']
        address_type = int(form.cleaned_data['address_type'])

        if currency is not None:
            currency = int(currency)

        if gas_price is not None:
            gas_price = int(gas_price)

        if threshold is not None:
            threshold = Decimal(threshold)
        else:
            threshold = Decimal('100')

        task_extract_contract_addresses.delay(network, gas_price=gas_price, threshold=threshold, currency=currency, address_type=address_type)
        return self.render_to_response(
            self.get_context_data(result=True,
                                  result_msg='Successfully send the extract task.')
        )


@public_post_api
def hot_wallet_creation(request):
    def _validate_crypto_address_v2(address, currency, network):
        if network.upper() == 'ONE' and address.startswith('0x'):
            address = eth_to_one_address(address)
        return validate_crypto_address_v2(address, currency, network)

    secret = request.g('secret')
    if not compare_digest(secret, settings.HOT_SYMMETRIC_KEY):
        report_event("[HotWallet Webhook]: basic authentication failed")
        return JsonResponse({
            'status': 'failed',
            'code': 'Unauthorized',
            'message': 'Unauthorized Request',
        }, status=status.HTTP_401_UNAUTHORIZED)

    old_addr = request.g('oldAddress')
    new_addr = request.g('newAddress')
    network = request.g('network')

    try:
        currency = CurrenciesNetworkName.NETWORKS_NATIVE_CURRENCY[network.upper()]
    except KeyError:
        report_exception()
        return JsonResponse({
            'status': 'failed',
            'code': 'BadRequest',
            'message': 'Network not found',
        }, status=status.HTTP_400_BAD_REQUEST)
    old_address_valid, _ = _validate_crypto_address_v2(old_addr, currency=currency, network=network)
    if not old_address_valid:
        report_event("[HotWallet Webhook]: Old address not validated")
        return JsonResponse(
            {
                'status': 'failed',
                'code': 'BadRequest',
                'message': 'Old address is not valid',
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    new_address_valid, _ = _validate_crypto_address_v2(new_addr, currency=currency, network=network)
    if not new_address_valid:
        report_event("[HotWallet Webhook]: New address not validated")
        return JsonResponse(
            {
                'status': 'failed',
                'code': 'BadRequest',
                'message': 'New address is not valid',
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        change_hotwallet(old_addr, new_addr, currency, network)
    except Exception as e:
        report_exception()
        return JsonResponse({
            'status': 'failed',
            'code': 'UnknownError',
            'message': 'Cannot change addresses correctly.',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return JsonResponse(
        {'status': 'ok'},
        status=status.HTTP_200_OK,
    )


def get_users_wallets(uids, currency, tp, create):
    wallets = (
        Wallet.objects.filter(user_id__in=uids, currency=currency, type=tp)
        .distinct('user_id')
        .in_bulk(field_name='user_id')
    )
    if not create:
        return wallets
    wallets_to_create = [Wallet(user_id=uid, currency=currency, type=tp) for uid in uids if uid not in wallets]
    try:
        new_wallets = {wallet.user_id: wallet for wallet in Wallet.objects.bulk_create(wallets_to_create)}
    except IntegrityError as e:
        raise ParseError('some User IDs are invalid.')
    return {**wallets, **new_wallets}


@post_api
@ratelimit(key='user_or_ip', rate='60/m', block=True)
@transaction.non_atomic_requests
def create_bulk_transactions(request):
    user = request.user
    if user.is_user_considered_in_production_test:
        wallet_type = parse_choices(Wallet.WALLET_TYPE, request.g('type')) or Wallet.WALLET_TYPE.spot
        user_ids = request.g('user_ids')
        if not user_ids:
            return JsonResponse(
                {
                    'status': 'failed',
                    'code': 'UserIdInvalid',
                    'message': 'No user ID provided.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            currency = parse_currency(request.g('currency'), required=True)
        except ParseError as e:
            return JsonResponse(
                {
                    'status': 'failed',
                    'code': 'CurrencyInvalid',
                    'message': str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            amount = parse_money(request.g('amount'), required=True)
        except ParseError as e:
            return JsonResponse(
                {
                    'status': 'failed',
                    'code': 'AmountInvalid',
                    'message': str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        create = request.g('create', False)
        user_ids = set([parse_int(uid) for uid in user_ids.split(',')])
        try:
            user_wallets_dict = get_users_wallets(uids=user_ids, currency=currency, tp=wallet_type, create=create)
        except ParseError as e:
            return JsonResponse(
                {
                    'status': 'failed',
                    'code': 'UserIdsInvalid',
                    'message': str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        unavailable_uids = []
        user_events = []
        for uid in user_ids:
            wallet = user_wallets_dict.get(uid, None)
            if wallet:
                with transaction.atomic():
                    wallet_tx_manager = WalletTransactionManager(wallet)
                    remained_amount = amount
                    description = f"افزایش دستی موجودی کیف {request.g('currency')} کاربر با آیدی {wallet.user_id}"
                    while remained_amount > Decimal('0.0'):
                        _amount = min(remained_amount, TRANSACTION_MAX)
                        wallet_tx_manager.add_transaction(tp='manual', amount=_amount, description=description)
                        remained_amount -= _amount
                    wallet_tx_manager.commit()
                user_events.append(
                    UserEvent(
                        user=user, action=UserEvent.ACTION_CHOICES.add_manual_transaction, description=description
                    )
                )
            else:
                unavailable_uids.append(uid)
        UserEvent.objects.bulk_create(user_events)
        wallets = Wallet.objects.filter(currency=currency, user_id__in=user_wallets_dict, type=wallet_type)
        wallets_response = [
            {'user_id': wallet.user_id, 'wallet_id': wallet.id, 'balance': wallet.balance} for wallet in wallets
        ]
        unavailable_uids_response = [{'user_id': uid, 'wallet_id': None, 'balance': None} for uid in unavailable_uids]
        return JsonResponse(
            {'currency': request.g('currency'), 'wallets': [*wallets_response, *unavailable_uids_response]},
            status=status.HTTP_200_OK,
        )
    return JsonResponse(
        {
            'status': 'failed',
            'code': 'PermissionDenied',
            'message': 'مجوز ثبت درخواست وجود ندارد.',
        },
        status=status.HTTP_403_FORBIDDEN,
    )
