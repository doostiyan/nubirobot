
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit

from exchange.accounts.models import BankAccount
from exchange.accounts.userlevels import UserLevelManager
from exchange.base.api import ParseError, api, public_post_api
from exchange.base.decorators import measure_api_execution
from exchange.base.helpers import build_frontend_url, is_url_allowed
from exchange.base.logging import report_exception
from exchange.base.models import Settings
from exchange.base.parsers import parse_bool, parse_choices, parse_int, parse_word
from exchange.base.validators import validate_iban
from exchange.features.models import QueueItem
from exchange.shetab.constants import JIBIT_ID_FEATURE_KEY
from exchange.shetab.handlers.jibit import JibitPip
from exchange.shetab.models import JibitAccount, JibitPaymentId, ShetabDeposit, VandarPaymentId


@ratelimit(key='user_or_ip', rate='180/h', block=True)
@measure_api_execution(api_label='shetabDepositCallback')
@csrf_exempt
def wallets_deposit_shetab_callback(request):
    # TODO block GET requests to this endpoint or return appropriate response for users
    is_devnet = parse_bool(request.GET.get('is_devnet'))
    redirect_url = build_frontend_url(request, '/app/wallet/', is_devnet)
    card_number = None
    card_hash = None
    status = None
    callback_ref_id = None
    order_id = None
    nextpay_id = ''

    gateway = request.GET.get('gateway')
    is_vandar = gateway == 'vandar'

    # Request Parameters
    if not request.POST and not is_vandar:  # vandar call this api with GET method
        return JsonResponse(status=404, data={'message': 'Not found', 'code': 'NotFound'})

    try:
        if not is_vandar:
            post_order_id = parse_word(request.POST.get('order_id'), required=False)
            post_id = parse_word(request.POST.get('id'), required=False)
    except ParseError as ex:
        report_exception()
        return JsonResponse(
            status=400,
            data={
                'code': 'ParseError',
                'message': ex.args[0],
            },
        )

    try:
        # Vandar.io
        if gateway == 'vandar':
            order_id = parse_word(request.GET.get('token'), required=True)
            nextpay_id = order_id
            status = request.GET.get('payment_status') == 'OK'
            if not nextpay_id:
                raise ShetabDeposit.DoesNotExist
            deposit = ShetabDeposit.objects.get(nextpay_id=nextpay_id)

        # jibit.ir
        elif gateway == 'jibit':
            nextpay_id = order_id = parse_word(request.GET.get('refnum'))
            status = request.GET.get('state')
            if not nextpay_id:
                raise ShetabDeposit.DoesNotExist
            deposit = ShetabDeposit.objects.get(nextpay_id=nextpay_id)
        elif gateway == 'jibit_v2':
            nextpay_id = order_id = parse_word(request.POST.get('purchaseId'), required=True)
            status = request.POST.get('status')
            if not nextpay_id:
                raise ShetabDeposit.DoesNotExist
            deposit = ShetabDeposit.objects.get(nextpay_id=nextpay_id)

        # Nobitex Sandbox
        elif gateway == 'nobitex-sandbox' and not settings.IS_PROD:
            if not post_id:
                return render(request, 'wallet/shetab_callback_failure.html', {
                    'nextpay_id': post_id,
                    'redirect_url': redirect_url,
                })

            deposit = ShetabDeposit.objects.get(pk=post_id)
        elif gateway == 'toman':
            nextpay_id = order_id = parse_word(request.POST.get('uuid'), required=True)
            # todo check if status is ok than continue
            if not nextpay_id:
                raise ShetabDeposit.DoesNotExist
            deposit = ShetabDeposit.objects.get(nextpay_id=nextpay_id)

        # Pay.ir
        elif request.GET.get('token'):
            order_id = parse_word(request.GET.get('token'), required=True)
            nextpay_id = order_id
            status = request.GET.get('status')
            if not nextpay_id:
                raise ShetabDeposit.DoesNotExist
            if settings.IS_PROD:
                deposit = ShetabDeposit.objects.get(nextpay_id=nextpay_id)
            else:
                deposit = ShetabDeposit.objects.filter(nextpay_id__endswith='-' + nextpay_id).last()
                if not deposit:
                    raise ShetabDeposit.DoesNotExist

        # PayPing
        elif request.GET.get('clientrefid'):
            client_ref_id = parse_word(request.GET.get('clientrefid'), required=True)
            ref_id = request.GET.get('refid')
            card_hash = request.POST.get('HashedCardNumber')
            if not ref_id or not client_ref_id.startswith('nobitex'):
                return render(request, 'wallet/shetab_callback_failure.html', {
                    'nextpay_id': client_ref_id,
                    'redirect_url': redirect_url,
                })
            order_id = client_ref_id[7:]
            nextpay_id = order_id
            if not nextpay_id:
                raise ShetabDeposit.DoesNotExist
            deposit = ShetabDeposit.objects.get(pk=nextpay_id)
            callback_ref_id = ref_id

        # IDPay
        elif post_order_id and post_id:
            if not post_id or not post_order_id.startswith('nobitex'):
                return render(request, 'wallet/shetab_callback_failure.html', {
                    'nextpay_id': post_id,
                    'redirect_url': redirect_url,
                })
            order_id = post_order_id[7:]
            nextpay_id = post_id
            if not nextpay_id:
                raise ShetabDeposit.DoesNotExist
            deposit = ShetabDeposit.objects.get(pk=order_id, nextpay_id=nextpay_id)

        # Unknown
        else:
            raise ShetabDeposit.DoesNotExist
    except ParseError as ex:
        report_exception()
        return JsonResponse(
            status=400,
            data={
                'code': 'ParseError',
                'message': ex.args[0],
            },
        )

    except ShetabDeposit.DoesNotExist:
        return render(request, 'wallet/shetab_callback_failure.html', {
            'nextpay_id': nextpay_id,
            'redirect_url': redirect_url,
        })
    except ShetabDeposit.MultipleObjectsReturned:
        return render(request, 'wallet/shetab_callback_failure.html', {
            'nextpay_id': nextpay_id,
            'redirect_url': redirect_url,
        })

    # Get lock
    deposit = ShetabDeposit.objects.select_for_update().get(pk=deposit.pk)
    deposit.callback_ref_id = callback_ref_id

    # Custom Redirect Url
    if deposit.next_redirect_url:
        if is_url_allowed(deposit.next_redirect_url, allowed_domains=settings.DEPOSIT_NEXT_REDIRECT_URL_DOMAINS):
            redirect_url = deposit.next_redirect_url
        else:
            redirect_url = build_frontend_url(request, deposit.next_redirect_url, is_devnet)

    # Set extra details sent by gateway (if any)
    if status and card_number:
        deposit.user_card_number = card_number
        deposit.save(update_fields=['user_card_number'])
    if card_hash:
        deposit.user_card_hash = card_hash.lower()
        deposit.save(update_fields=['user_card_hash'])

    # Reject requests if deposit is disabled
    shetab_deposit_backend = Settings.get('shetab_deposit_backend')
    if shetab_deposit_backend == 'disabled':
        return render(request, 'wallet/shetab_callback_reject.html', {
            'order_id': order_id,
            'nextpay_id': nextpay_id,
            'redirect_url': redirect_url,
        })

    # Finalize and commit
    is_in_wizard = 'buy/bank-callback' in redirect_url
    deposit.error_message = ''
    ok = deposit.sync_and_update(request)
    if not ok:
        return render(
            request,
            'wallet/shetab_callback_failure.html',
            {
                'nextpay_id': deposit.nextpay_id,
                'redirect_url': redirect_url,
            },
        )
    add_new_card_url = (
        build_frontend_url(request, '/app/wizard/buy/add-card', is_devnet)
        if is_in_wizard
        else build_frontend_url(request, '/app/profile/', is_devnet)
    )
    return render(
        request,
        'wallet/shetab_callback.html',
        {
            'order_id': deposit.external_order_id,
            'amount': int(deposit.amount),
            'fee': int(deposit.fee),
            'net_amount': int(deposit.transaction.amount),
            'redirect_url': redirect_url,
            'status_code': deposit.status_code,
            'add_card_url': add_new_card_url,
            'card_number': deposit.user_card_number,
        },
    )


@ratelimit(key='user_or_ip', rate='10/h', block=True)
@measure_api_execution(api_label='shetabCreatePaymentID')
@api
def user_payments_ids_create(request):
    """POST /users/payments/create-id
    To create a payment ID (any type), the user must either have an active feature flag (jibit_pip)
    or meet the eligibility criteria defined by the is_eligible_to_bank_id_deposit function.

    If the user wants to create a nobitex_jibit payment ID, they must have
    an active feature flag (nobitex_jibit_ideposit)
    and either explicitly set type to 'nobitex_jibit' or leave it blank.
    """

    user = request.user
    account_type = parse_choices(JibitAccount.ACCOUNT_TYPES, request.g('type', 'nobitex_jibit'))

    user_queue_items = QueueItem.objects.filter(
        user=user, feature__in=[QueueItem.FEATURES.jibit_pip, QueueItem.FEATURES.nobitex_jibit_ideposit]
    )

    pip_queue_item = user_queue_items.filter(feature=QueueItem.FEATURES.jibit_pip).first()
    if not pip_queue_item and UserLevelManager.is_eligible_to_bank_id_deposit(user):
        pip_queue_item = QueueItem.objects.create(
            user=user,
            feature=QueueItem.FEATURES.jibit_pip,
            status=QueueItem.STATUS.done,
        )
    if not pip_queue_item or pip_queue_item.status != QueueItem.STATUS.done:
        return {
            'status': 'failed',
            'code': 'UserLevelRestriction',
            'message': 'UserLevelRestriction',
        }

    ideposit_queue_item = user_queue_items.filter(
        feature=QueueItem.FEATURES.nobitex_jibit_ideposit,
        status=QueueItem.STATUS.done,
    ).first()
    if (
        account_type == JibitAccount.ACCOUNT_TYPES.nobitex_jibit
        and not ideposit_queue_item
        and not UserLevelManager.is_eligible_for_nobitex_id_deposit(user)
    ):
        return {
            'status': 'failed',
            'code': 'PaymentTypeError',
            'message': 'User is not eligible to request this type of destination party',
        }

    if not Settings.is_feature_active(JIBIT_ID_FEATURE_KEY) and account_type == JibitAccount.ACCOUNT_TYPES.jibit:
        return {
            'status': 'failed',
            'code': 'FeatureUnavailable',
            'message': 'Jibit ID deposit is disabled',
        }

    # Bank Account
    iban = request.g('iban')
    if not validate_iban(iban):
        return {
            'status': 'failed',
            'code': 'InvalidIBAN',
            'message': 'Invalid IBAN: "{}"'.format(iban),
        }
    bank_account = BankAccount.objects.filter(
        user=user, shaba_number=iban,
        is_deleted=False, is_temporary=False, confirmed=True,
    ).first()
    if not bank_account:
        return {
            'status': 'failed',
            'code': 'UnknownIBAN',
            'message': 'Unknown IBAN',
        }

    # Check for existing payment id
    payment_id_obj = (
        JibitPaymentId.objects.filter(
            bank_account=bank_account,
            jibit_account__account_type=account_type,
        )
        .order_by('-id')
        .first()
    )
    if payment_id_obj:
        return {
            'status': 'ok',
            'paymentId': payment_id_obj,
        }

    # Issue new payment ID if not exists
    response = JibitPip.get_payment_id(bank_account, account_type)
    if not response:
        return {
            'status': 'failed',
            'code': 'JibitAPIFailed',
            'message': 'Jibit API failed',
        }

    # Create payment ID object and return
    payment_id = response.get('payId')
    jibit_account = JibitPip.parse_destination_account(response, account_type)
    if not payment_id or not jibit_account:
        return {
            'status': 'failed',
            'code': 'JibitAPIInvalid',
            'message': 'Jibit API invalid',
        }
    payment_id_obj = JibitPaymentId.objects.create(
        bank_account=bank_account,
        jibit_account=jibit_account,
        payment_id=payment_id,
    )
    return {
        'status': 'ok',
        'paymentId': payment_id_obj,
    }


@ratelimit(key='user_or_ip', rate='5/m', block=True)
@measure_api_execution(api_label='shetabListPaymentIDs')
@api
def user_payments_ids_list(request):
    """ GET /users/payments/ids-list
    """

    user = request.user
    deposit_payment_ids = []

    jibit_payments_query = [Q(bank_account__user=request.user, bank_account__is_deleted=False)]
    if (
        not QueueItem.objects.filter(
            user=user,
            feature=QueueItem.FEATURES.nobitex_jibit_ideposit,
            status=QueueItem.STATUS.done,
        ).exists()
        and not UserLevelManager.is_eligible_for_nobitex_id_deposit(user)
    ):
        jibit_payments_query.append(~Q(jibit_account__account_type=JibitAccount.ACCOUNT_TYPES.nobitex_jibit))

    if not Settings.is_feature_active(JIBIT_ID_FEATURE_KEY):
        jibit_payments_query.append(~Q(jibit_account__account_type=JibitAccount.ACCOUNT_TYPES.jibit))

    deposit_payment_ids += JibitPaymentId.objects.filter(*jibit_payments_query).select_related(
        'bank_account', 'jibit_account'
    )

    if UserLevelManager.is_user_eligible_for_vandar_deposit(user):
        deposit_payment_ids += VandarPaymentId.objects.filter(
            bank_account__user=request.user,
        ).select_related('bank_account', 'vandar_account')

    return {
        'status': 'ok',
        'paymentIds': deposit_payment_ids,
    }


@ratelimit(key='user_or_ip', rate='100/m', method='POST', block=True)
@measure_api_execution(api_label='shetabPaymentCallback')
@public_post_api
def user_payments_callback(request):
    """ POST /users/payments/callback
    """
    JibitPip.create_or_update_jibit_payment(request.POST)
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='5/m', block=True)
def sandbox_gateway(request):
    if settings.IS_PROD:
        raise PermissionDenied()

    gateway = 'nobitex-sandbox'
    deposit_id = parse_int(request.GET.get('depositId'))
    deposit = get_object_or_404(ShetabDeposit, id=deposit_id)
    is_devnet = 'devnet' in request.headers.get('referer', 'other')

    return render(
        request,
        'sandbox_gateway.html',
        {
            'id': deposit.id,
            'amount': deposit.amount,
            'fee': deposit.calculate_fee(),
            'net_amount': deposit.amount - deposit.calculate_fee(),
            'callback_url': reverse('shetab_callback')
            + f'?gateway={gateway}'
            + (f'&is_devnet={is_devnet}' if is_devnet else ''),
        },
    )
