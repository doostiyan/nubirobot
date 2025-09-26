from decimal import Decimal

from django.core.cache import cache
from django.db import transaction
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status

from exchange.asset_backed_credit.utils import is_user_agent_android
from exchange.base.api import APIView, PublicAPIView
from exchange.base.api_v2_1 import paginate
from exchange.base.helpers import is_from_unsupported_app
from exchange.base.models import (
    ALL_CURRENCIES,
    BABYDOGE,
    TESTING_CURRENCIES,
    Currencies,
    Settings,
    get_currency_codename,
)
from exchange.base.parsers import parse_int, parse_money, parse_str
from exchange.features.utils import is_feature_enabled
from exchange.market.models import Order
from exchange.recovery.functions import (
    is_duplicate_tx_hash,
    validate_alphanumeric,
    validate_return_address,
    validate_user_deposit_address,
)
from exchange.recovery.models import RecoveryCurrency, RecoveryNetwork, RecoveryRequest
from exchange.recovery.serializers import serialize_wallet_all_addresses
from exchange.usermanagement.models import BlockedOrderLog
from exchange.wallet.models import Wallet


class RecoveryCurrencyListView(PublicAPIView):

    @method_decorator(ratelimit(key="user_or_ip", rate="20/m", method="GET", block=True))
    def get(self, request):
        """API for currency list

        GET /recovery/currencies/list
        """
        currencies = RecoveryCurrency.objects.all().order_by('-created_at')
        return self.response(
            {
                'status': 'ok',
                'currencies': currencies,
            },
        )


class RecoveryNetworkListView(PublicAPIView):

    @method_decorator(ratelimit(key="user_or_ip", rate="20/m", method="GET", block=True))
    def get(self, request):
        """API for network list

        GET /recovery/networks/list
        """
        networks = RecoveryNetwork.objects.all().order_by('-created_at')
        fee = Settings.get_decimal('recovery_fee')

        return self.response(
            {
                'status': 'ok',
                'fee': fee,
                'networks': networks,
            },
        )


class RecoveryRequestView(APIView):

    @method_decorator(ratelimit(key='user_or_ip', rate='20/m', method='get', block=True))
    def get(self, request):
        """recovery list

        GET /recovery/recovery-requests
        """
        recovery_id = parse_int(self.g('recoveryId', None))
        recovery_requests = RecoveryRequest.objects.filter(user=request.user).order_by('-created_at')

        if recovery_id is not None:
            recovery_requests = recovery_requests.filter(id=recovery_id)
        paginated_result = paginate(recovery_requests, self)
        return self.response(
            {
                'status': 'ok',
                'recoveryRequests': paginated_result['result'],
                'hasNext': paginated_result['hasNext'],
            }
        )

    @method_decorator(ratelimit(key="user_or_ip", rate="1/m", method="POST", block=True))
    def post(self, request, **_):
        """ recovery request creation

        POST /recovery/recovery-requests
        """
        if is_user_agent_android(request) and not is_user_agent_android(request, min_version='7.2.0'):
            return JsonResponse(
                {'status': 'failed', 'code': 'PleaseUpdateApp', 'message': 'Please Update App'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        amount = parse_money(self.g('amount'), required=True)
        currency_id = parse_int(self.g('currency'), required=True)
        network_id = parse_int(self.g('network'), required=True)
        deposit_address = parse_str(self.g('depositAddress'), required=True)
        deposit_tag = parse_str(self.g('depositTag'))
        deposit_hash = parse_str(self.g('depositHash'), required=True)
        return_address = parse_str(self.g('returnAddress'), required=True)
        return_tag = parse_str(self.g('returnTag'))

        if not request.user.email:
            return JsonResponse({
                'status': 'failed',
                'code': 'EmailRequired',
                'message': 'User has no email.',
            }, status=422)

        if not RecoveryCurrency.objects.filter(id=currency_id).exists():
            return JsonResponse({
                'status': 'failed',
                'code': 'InvalidCurrency',
                'message': 'Invalid currency value.',
            }, status=400)

        recovery_network = RecoveryNetwork.objects.filter(id=network_id).first()
        if not recovery_network:
            return JsonResponse({
                'status': 'failed',
                'code': 'InvalidNetwork',
                'message': 'Invalid network value.',
            }, status=400)

        if not validate_user_deposit_address(request.user, deposit_address):
            return JsonResponse({
                'status': 'failed',
                'code': 'InvalidDepositAddress',
                'message': 'Invalid deposit address.',
            }, status=400)

        if deposit_tag and not validate_alphanumeric(deposit_tag):
            return JsonResponse({
                'status': 'failed',
                'code': 'InvalidDepositTag',
                'message': 'Invalid deposit tag value.',
            }, status=400)

        if return_tag and not validate_alphanumeric(return_tag):
            return JsonResponse({
                'status': 'failed',
                'code': 'InvalidReturnTag',
                'message': 'Invalid return tag value.',
            }, status=400)

        if not validate_return_address(return_address):
            return JsonResponse({
                'status': 'failed',
                'code': 'InvalidReturnAddress',
                'message': 'Invalid return Address.',
            }, status=400)

        if is_duplicate_tx_hash(tx_hash=deposit_hash):
            return JsonResponse({
                'status': 'failed',
                'code': 'DuplicateDepositHash',
                'message': 'Duplicate deposit hash.',
            }, status=422)
        fee = Settings.get_decimal('recovery_fee')
        # RecoveryNetwork is allways available, we checked it before this line:
        fee = recovery_network.fee or fee
        if not fee:
            return JsonResponse({
                'status': 'failed',
                'code': 'TryAgainLater',
                'message': 'Try again later.',
            }, status=422)
        tether_wallet = Wallet.get_user_wallet(self.request.user, Currencies.usdt)
        if tether_wallet.active_balance < fee:
            return JsonResponse({
                'status': 'failed',
                'code': 'InsufficientBalance',
                'message': 'Insufficient balance.',
            }, status=422)
        with transaction.atomic():
            block_order = Order.objects.create(
                user=request.user,
                src_currency=Currencies.usdt,
                dst_currency=Currencies.rls,
                description='کسر کارمزد بازیابی',
                channel=Order.CHANNEL.system_block,
                order_type=Order.ORDER_TYPES.sell,
                price=Decimal(90_000_000_000_0),
                status=Order.STATUS.active,
                amount=fee,
            )
            recovery = RecoveryRequest.objects.create(
                block_order=block_order,
                amount=amount,
                user=request.user,
                currency_id=currency_id,
                network_id=network_id,
                contract='',
                return_address=return_address,
                return_tag=return_tag or None,
                deposit_address=deposit_address,
                deposit_hash=deposit_hash,
                deposit_tag=deposit_tag or None,
            )
            BlockedOrderLog.add_blocked_order_log(block_order)
        cache.set(f'user_{request.user.id}_recent_order', True, 100)
        cache.set(f'user_{request.user.id}_no_order', False, 60)
        return self.response({"status": "ok",
                              "recoveryRequest": recovery,
                              })


class CheckRecoveryRequestView(APIView):

    @method_decorator(ratelimit(key='user_or_ip', rate='20/m', method='get', block=True))
    def get(self, request):
        """API for Checking Hash

        GET /recovery/recovery-requests/check-hash
        """
        deposit_hash = parse_str(self.g('depositHash'), required=True)
        exists = is_duplicate_tx_hash(tx_hash=deposit_hash)
        return self.response(
            {
                'status': 'ok',
                'exists': exists,
            }
        )


class RejectRecoveryRequestView(APIView):

    @method_decorator(ratelimit(key='user_or_ip', rate='20/m', method='POST', block=True))
    def post(self, request, id):
        """API for reject recovery request

        POST /recovery/recovery-requests/:id/reject
        """
        result = None
        recovery_request = RecoveryRequest.objects.filter(
            user=request.user,
            id=id,
            status__in=RecoveryRequest.STATUSES_CANCELABLE).first()
        if recovery_request:
            result = recovery_request.cancel_by_user()
        if not result:
            return JsonResponse({
                'status': 'failed',
                'code': 'InvalidRecoveryRequest',
                'message': 'Invalid Recovery Request.',
            }, status=422)
        return self.response(
            {
                'status': 'ok',
                'recoveryRequest': recovery_request,
            }
        )


class GetAllAvailableDepositAddresses(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='20/m', method='get', block=True))
    def get(self, request):
        """API for getting all addresses of wallets

        GET /recovery/recovery-requests/all-deposit-addresses
        """
        user = request.user
        wallet_type = Wallet.WALLET_TYPE.spot
        wallets = Wallet.get_user_wallets(user, wallet_type)

        wallet_addresses = {wallet.id: serialize_wallet_all_addresses(wallet) for wallet in wallets}

        supported_currencies = set(ALL_CURRENCIES)
        if not is_feature_enabled(user, 'new_coins'):
            supported_currencies -= set(TESTING_CURRENCIES)
        if is_from_unsupported_app(request, feature='percentage_fee'):
            supported_currencies -= {BABYDOGE}

        serialized_wallets = []
        for wallet in wallets:
            if wallet.currency not in supported_currencies:
                continue
            wallet_dict = wallet_addresses.get(wallet.id, {})
            wallet_dict['currency'] = get_currency_codename(wallet.currency)
            serialized_wallets.append(wallet_dict)

        return JsonResponse(
            {
                'status': 'ok',
                'wallets': serialized_wallets,
            }
        )


class GetRejectReasonsView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='20/m', method='GET', block=True))
    def get(self, request, id):
        """API for reject recovery request

        GET /recovery/recovery-requests/:id/reject-reasons
        """
        result = None
        recovery_request = (
            RecoveryRequest.objects.select_related('reject_reason')
            .prefetch_related('reject_reason__reasons')
            .filter(user=request.user, id=id, status=RecoveryRequest.STATUS.rejected)
            .first()
        )
        if recovery_request:
            result = list(recovery_request.reject_reason.reasons.all().values_list('description', flat=True))
        if not result:
            return JsonResponse(
                {
                    'status': 'failed',
                    'code': 'InvalidRecoveryRequest',
                    'message': 'Invalid Recovery Request.',
                },
                status=422,
            )
        return JsonResponse(
            {
                'status': 'ok',
                'rejectReasons': result,
            }
        )
