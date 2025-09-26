from django.db import IntegrityError, transaction
from django.db.models import F, Func, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic.detail import SingleObjectMixin
from django_ratelimit.decorators import ratelimit

from exchange.base.api import APIView, NobitexAPIError, SemanticAPIError, email_required_api
from exchange.base.api_v2_1 import paginate
from exchange.base.constants import ZERO
from exchange.base.models import Currencies, get_currency_codename
from exchange.base.parsers import parse_bool, parse_choices, parse_date, parse_int, parse_money
from exchange.base.serializers import serialize_dict_key_choices
from exchange.base.strings import _t
from exchange.pool.errors import (
    DelegateWhenRevokeInProgressException,
    ExceedCapacityException,
    HighDelegationAmountException,
    InsufficientBalanceException,
    InvalidDelegationAmount,
    LowDelegationAmountException,
    NoAccessException,
    PermissionDeniedException,
    UnfilledCapacityAlertDoesNotExist,
    UnfilledCapacityAlertExist,
)
from exchange.pool.models import (
    DelegationRevokeRequest,
    DelegationTransaction,
    LiquidityPool,
    PoolAccess,
    UserDelegation,
    UserDelegationProfit,
)
from exchange.pool.poolmanager import PoolManager
from exchange.usermanagement.block import BalanceBlockManager
from exchange.wallet.models import Wallet


class LiquidityPoolsListView(APIView):
    permission_classes = []

    class StatusFilter:
        all = "all"
        active = "active"
        inactive = "inactive"

    @method_decorator(ratelimit(key="user_or_ip", rate="12/m", method="GET", block=True))
    def get(self, request):
        """API for liquidity pool list

        GET /liquidity-pools/list
        """
        status = parse_choices(self.StatusFilter, self.g("status") or self.StatusFilter.active)
        is_active = True if status == self.StatusFilter.active else False if status == self.StatusFilter.inactive else None
        if request.user.is_authenticated:
            pools = LiquidityPool.get_pools(
                request.user,
                PoolAccess.ACCESS_TYPES.liquidity_provider,
                check_user_has_active_alert=True,
                is_active=is_active,
            )
        else:
            pools = LiquidityPool.get_pools(is_active=is_active)

        pools = pools.in_bulk(field_name='currency')

        return self.response(
            {"status": "ok", "pools": serialize_dict_key_choices(Currencies, pools)},
            opts={"user_type": request.user.user_type, "level": 2} if request.user.is_authenticated else {},
        )


class LiquidityPoolDelegateView(APIView):

    @method_decorator(ratelimit(key='user_or_ip', rate='20/m', method='POST', block=True))
    @method_decorator(email_required_api)
    def post(self, request, id):
        """API for delegate to a liquidity pool

            POST /liquidity-pools/:id/delegations
        """

        amount = parse_money(self.g('amount'), required=True)
        user = request.user

        try:
            with transaction.atomic():
                pool = get_object_or_404(LiquidityPool, id=id, is_active=True)
                user_delegation = pool.create_delegation(user, amount)
        except PermissionDeniedException as ex:
            raise SemanticAPIError(
                message='PermissionDenied',
                description='User is not allowed.',
            ) from ex

        except (IntegrityError, ExceedCapacityException) as ex:
            raise SemanticAPIError(
                message='ExceedPoolCapacity',
                description='Amount is greater than unfilled capacity of the pool',
            ) from ex

        except LowDelegationAmountException as ex:
            raise SemanticAPIError(
                message='LowDelegationAmount',
                description='Amount is lower than the min delegation.',
            ) from ex

        except HighDelegationAmountException as ex:
            raise SemanticAPIError(
                message='HighDelegationAmount',
                description='Amount is greater than the max delegation.',
            ) from ex

        except InsufficientBalanceException as ex:
            raise SemanticAPIError(
                message='InsufficientWalletBalance',
                description='Amount is greater than unlocked wallet balance.',
            ) from ex

        except DelegateWhenRevokeInProgressException as ex:
            raise SemanticAPIError(
                message='DelegateWhenRevokeInProgress',
                description='Cannot delegate when an active revoke is exists.',
            ) from ex

        except NoAccessException as ex:
            raise Http404() from ex

        return self.response({'status': 'ok', 'userDelegation': user_delegation})


class LiquidityPoolListDelegationsView(APIView):

    @method_decorator(ratelimit(key='user_or_ip', rate='30/m', method='get', block=True))
    def get(self, request):
        """API for list user delegations
            GET /liquidity-pools/delegations/list
        """

        is_closed = parse_bool(self.g('isClosed', None))
        pool_id = parse_int(self.g('poolId', None))

        user_delegations = request.user.user_delegations.select_related('pool').annotate(
            revoking_balance=Coalesce(Sum(
                'delegation_revoke_request__amount',
                filter=Q(delegation_revoke_request__status=DelegationRevokeRequest.STATUS.new)
            ), ZERO)
        ).order_by('-created_at')

        if pool_id is not None:
            user_delegations = user_delegations.filter(pool_id=pool_id)

        if is_closed is not None:
            user_delegations = user_delegations.filter(closed_at__isnull=not is_closed)

        paginated_result = paginate(user_delegations, self)
        return self.response(
            {
                'status': 'ok',
                'userDelegations': paginated_result['result'],
                'hasNext': paginated_result['hasNext'],
            }
        )


class LiquidityPoolListDelegationTxsView(APIView):

    class DelegationTxOrder:
        newest = '-created_at'
        latest = 'created_at'
        max = '-abs_amount'

    @method_decorator(ratelimit(key='user_or_ip', rate='30/m', method='get', block=True))
    def get(self, request):
        """API for list delegation transactions
            GET /liquidity-pools/delegation-transactions/list
        """

        pool_id = parse_int(self.g('poolId', None))
        user_delegation_id = parse_int(self.g('userDelegationId', None))
        is_revoke = parse_bool(self.g('isRevoke', None))
        from_date = parse_date(self.g('fromDate', None))
        to_date = parse_date(self.g('toDate', None))
        order_by = parse_choices(self.DelegationTxOrder, self.g('order'), required=False)

        if order_by is None:
            order_by = self.DelegationTxOrder.newest

        user = request.user
        delegation_txs = (
            DelegationTransaction.objects
            .filter(user_delegation__user=user)
            .select_related('user_delegation__pool', 'delegation_revoke_request')
        )

        if order_by == self.DelegationTxOrder.max:
            delegation_txs = delegation_txs.annotate(
                abs_amount=Func(F('amount'), function='ABS'),
            )

        delegation_txs = delegation_txs.order_by(order_by)

        if pool_id is not None:
            delegation_txs = delegation_txs.filter(user_delegation__pool_id=pool_id)

        if user_delegation_id is not None:
            delegation_txs = delegation_txs.filter(user_delegation__id=user_delegation_id)

        if is_revoke is not None:
            if is_revoke:
                delegation_txs = delegation_txs.filter(amount__lte=0)
            else:
                delegation_txs = delegation_txs.filter(amount__gte=0)

        if from_date:
            delegation_txs = delegation_txs.filter(created_at__date__gte=from_date)

        if to_date:
            delegation_txs = delegation_txs.filter(created_at__date__lte=to_date)

        paginated_result = paginate(delegation_txs, self)
        return self.response(
            {
                'status': 'ok',
                'delegationTransactions': paginated_result['result'],
                'hasNext': paginated_result['hasNext'],
            }
        )


class UserDelegationProfitsListView(APIView):

    class UserProfitOrder:
        newest = "-to_date"
        latest = "to_date"
        max = "-amount"
        min = "amount"

    @method_decorator(ratelimit(key="user_or_ip", rate="30/m", method="get", block=True))
    def get(self, request):
        """API for list of user profits
        GET /liquidity-pools/delegation-profits/list
        """
        pool_id = parse_int(self.g("poolId", None), required=False)
        order_by = parse_choices(self.UserProfitOrder, self.g("order"), required=False)
        if order_by is None:
            order_by = self.UserProfitOrder.newest

        profits = UserDelegationProfit.objects.filter(user_delegation__user=request.user) \
            .select_related('transaction', 'user_delegation__pool').order_by(order_by)

        if pool_id is not None:
            profits = profits.filter(user_delegation__pool_id=pool_id)

        paginated_result = paginate(profits, self)
        return self.response(
            {
                "status": "ok",
                "delegationProfits": paginated_result["result"],
                "hasNext": paginated_result["hasNext"],
            }
        )


class DelegationRevokeRequestCreateView(SingleObjectMixin, APIView):

    def get_queryset(self):
        return self.request.user.user_delegations.select_for_update().filter(closed_at=None)

    @method_decorator(ratelimit(key="user_or_ip", rate="20/m", method="POST", block=True))
    def post(self, request, **_):
        """API for creating delegation revoke request
        POST /liquidity-pools/delegations/<int:pk>/revoke
        """
        amount = parse_money(self.g("amount"), required=True)

        try:
            with transaction.atomic():
                user_delegation = self.get_object()
                if not user_delegation.pool.is_active:
                    raise NobitexAPIError(
                        status_code=403,
                        message='PermissionDenied',
                        description=f'استخر {_t(get_currency_codename(user_delegation.pool.currency))} غیرفعال است و امکان ثبت درخواست وجود ندارد.',
                    )
                delegation_revoke = PoolManager.create_delegation_revoke_request(user_delegation, amount)

        except LowDelegationAmountException as ex:
            raise SemanticAPIError(
                message="LowDelegationAmount",
                description="Amount is lower than the min delegation.",
            ) from ex

        except HighDelegationAmountException as ex:
            raise SemanticAPIError(
                message="HighDelegationAmount",
                description="Amount is greater than the max delegation.",
            ) from ex

        except (IntegrityError, InvalidDelegationAmount) as ex:
            raise SemanticAPIError(
                message="InvalidDelegationAmount",
                description="More than participation.",
            ) from ex

        return self.response({"status": "ok", "delegationRevokeRequest": delegation_revoke})


class DelegationRevokeRequestListView(APIView):

    @method_decorator(ratelimit(key="user_or_ip", rate="20/m", method="POST", block=True))
    def get(self, request):
        """API for delegation revoke request list
        GET /liquidity-pools/delegation-revoke-requests/list
        """
        status = parse_choices(DelegationRevokeRequest.STATUS, self.g("status"))
        delegation_revokes = PoolManager.get_delegation_revoke_request_list(request.user, status)
        paginated_result = paginate(delegation_revokes, self)
        return self.response(
            {
                "status": "ok",
                "delegationRevokeRequests": paginated_result["result"],
                "hasNext": paginated_result["hasNext"],
            }
        )


class PoolUnfilledCapacityAlertCreateView(SingleObjectMixin, APIView):

    def get_queryset(self):
        return LiquidityPool.get_pools(
            user=self.request.user, access_type=PoolAccess.ACCESS_TYPES.liquidity_provider, is_active=True,
        )

    @method_decorator(ratelimit(key="user_or_ip", rate="20/m", method="POST", block=True))
    @method_decorator(email_required_api)
    def post(self, request, **_):
        """API for delegation revoke request list
        POST /liquidity-pools/<int:pk>/unfilled-capacity-alert/create
        """

        try:
            with transaction.atomic():
                pool = self.get_object()
                if pool.filled_capacity < pool.capacity + pool.revoked_capacity:
                    raise SemanticAPIError(
                        message="LiquidityPoolHasNotFilled",
                        description="Liquidity pool has not filled.",
                    )

                PoolManager.create_unfilled_capacity_alert(pool, request.user)

        except PermissionDeniedException as ex:
            raise SemanticAPIError(
                message='PermissionDenied',
                description='User is not allowed.',
            ) from ex

        except UnfilledCapacityAlertExist as ex:
            raise SemanticAPIError(
                message="UnfilledCapacityAlertExist",
                description="Unfilled capacity alert exist.",
            ) from ex

        return self.response({"status": "ok"})


class PoolUnfilledCapacityAlertDeleteView(SingleObjectMixin, APIView):

    def get_queryset(self):
        return LiquidityPool.get_pools(
            user=self.request.user, access_type=PoolAccess.ACCESS_TYPES.liquidity_provider, is_active=True,
        )

    @method_decorator(ratelimit(key="user_or_ip", rate="20/m", method="POST", block=True))
    def post(self, request, **_):
        """API for delegation revoke request list
        POST /liquidity-pools/<int:pk>/unfilled-capacity-alert/delete
        """

        try:
            with transaction.atomic():
                pool = self.get_object()
                PoolManager.remove_unfilled_capacity_alert(pool, request.user)
        except UnfilledCapacityAlertDoesNotExist as ex:
            raise SemanticAPIError(
                message="UnfilledCapacityAlertDoesNotExist",
                description="Unfilled capacity alert does not exist.",
            ) from ex

        return self.response({"status": "ok"})


class UserDelegationCalenderView(SingleObjectMixin, APIView):

    def get_queryset(self):
        return UserDelegation.objects.filter(closed_at__isnull=True, user=self.request.user).select_related('pool')

    @method_decorator(ratelimit(key="user_or_ip", rate="20/m", method="GET", block=True))
    def get(self, request, pk):
        """API for calender of user delegation
        GET /liquidity-pools/delegations/<int:pk>/current-calender
        """

        user_delegation: UserDelegation = self.get_object()
        pool = user_delegation.pool

        dates = {
            'start': pool.start_date,
            'end': pool.end_date,
            'profit': pool.profit_date,
        }

        transactions_query = (
            DelegationTransaction.objects
            .filter(user_delegation__id=pk, created_at__date__gte=pool.start_date)
            .values('created_at__date')
            .annotate(amount=Sum('amount'))
            .exclude(amount=0)
            .order_by('created_at__date')
        )
        transactions = [{'amount': tx['amount'], 'date': tx['created_at__date']} for tx in transactions_query]

        initial_balance = user_delegation.balance - sum([tx['amount'] for tx in transactions])
        balances = {'initial': initial_balance}

        return self.response({'status': 'ok', 'dates': dates, 'transactions': transactions, 'balances': balances})
