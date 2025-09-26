from datetime import timedelta
from decimal import ROUND_DOWN, Decimal
from typing import Iterable, Optional

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, OuterRef, Sum
from django.utils import timezone

from exchange.accounts.models import Notification, User
from exchange.accounts.userlevels import UserLevelManager
from exchange.base.models import AMOUNT_PRECISIONS_V2, get_currency_codename
from exchange.pool.errors import (
    InsufficientBalanceException,
    InvalidDelegationAmount,
    LowDelegationAmountException,
    UnfilledCapacityAlertDoesNotExist,
    UnfilledCapacityAlertExist,
)
from exchange.pool.models import (
    DelegationRevokeRequest,
    DelegationTransaction,
    LiquidityPool,
    PermissionDeniedException,
    PoolMinimumAvailableRatioAlert,
    PoolUnfilledCapacityAlert,
    UserDelegation,
)


class PoolManager:
    @classmethod
    def _get_maximum_withdrawal_amount_in_user_delegation_wallet(cls, user_delegation: UserDelegation) -> Decimal:
        """
        this function calculates all delegations for a user delegation wallet(all transaction and revoked request)
        """
        delegation_revoke_total = (
            DelegationRevokeRequest.objects.filter(
                user_delegation=user_delegation, status=DelegationRevokeRequest.STATUS.new
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )
        return user_delegation.balance - delegation_revoke_total

    @classmethod
    def create_delegation_revoke_request(cls, user_delegation: UserDelegation, amount: int) -> DelegationRevokeRequest:
        """
        This function creates revoke request on user delegation wallet.

        Raises:
        LowDelegationAmountException: Amount is lower than the limit
        InvalidDelegationAmount: Amount is higher than your delegations
        """
        amount = amount.quantize(AMOUNT_PRECISIONS_V2[user_delegation.pool.currency], ROUND_DOWN)
        max_amount = cls._get_maximum_withdrawal_amount_in_user_delegation_wallet(user_delegation)

        if amount < min(user_delegation.pool.min_delegation, max_amount):
            raise LowDelegationAmountException()

        if amount > max_amount:
            raise InvalidDelegationAmount()
        delegation_revoke = DelegationRevokeRequest.objects.create(user_delegation=user_delegation, amount=amount)
        delegation_revoke.notify_on_new()
        return delegation_revoke

    @classmethod
    def get_delegation_revoke_request_list(
        cls, user: User, status: Optional[int] = None
    ) -> Iterable[DelegationRevokeRequest]:
        """
        This function returns revoke request list with status filter.
        """
        delegation_revoke_requests = (
            DelegationRevokeRequest.objects.select_related("user_delegation")
            .filter(user_delegation__user_id=user.id)
            .order_by("-created_at")
        )
        if status is not None:
            delegation_revoke_requests = delegation_revoke_requests.filter(status=status)

        return delegation_revoke_requests

    @classmethod
    def _settle_delegation_revoke_request(cls, delegation_revoke_request: DelegationRevokeRequest) -> None:
        """
        If a pool has enough capacity for revoked requests, this function paid them.
        """
        with transaction.atomic():
            delegation_transaction = DelegationTransaction.objects.create(
                user_delegation=delegation_revoke_request.user_delegation,
                amount=-delegation_revoke_request.amount,
            )
            delegation_revoke_request.status = DelegationRevokeRequest.STATUS.paid
            delegation_revoke_request.delegation_transaction = delegation_transaction
            delegation_revoke_request.save(update_fields=["status", "delegation_transaction"])

    @classmethod
    def check_delegation_revoke_request(cls, pool_id: Optional[int] = None) -> None:
        """
        This function helps signal and cron for paying revoked requests
        """
        delegation_revoke_requests = DelegationRevokeRequest.objects.select_for_update().filter(
            status=DelegationRevokeRequest.STATUS.new
        )
        if pool_id:
            delegation_revoke_requests = delegation_revoke_requests.filter(user_delegation__pool_id=pool_id)

        delegation_revoke_requests = delegation_revoke_requests.select_related(
            "user_delegation", "user_delegation__pool"
        ).order_by("created_at")

        pools_dict = {}
        with transaction.atomic():
            for delegation_revoke_request in delegation_revoke_requests:
                pool = delegation_revoke_request.user_delegation.pool
                if pool in pools_dict:
                    pools_dict[pool].append(delegation_revoke_request)
                else:
                    pools_dict[pool] = [delegation_revoke_request]

            for pool, delegation_revoke_requests_pool in pools_dict.items():
                for delegation_revoke_request in delegation_revoke_requests_pool:
                    try:
                        cls.check_settlement_delegation_revoke_request(delegation_revoke_request)
                    except Exception:
                        break

    @classmethod
    def check_settlement_delegation_revoke_request(cls, delegation_revoke_request: DelegationRevokeRequest) -> None:
        """
        This function checks conditions before paying revoked requests

        Raises:
            InsufficientBalanceException: when the pool has not enough currency for paying a revoke
        """
        if delegation_revoke_request.user_delegation.pool.unblocked_balance < delegation_revoke_request.amount:
            raise InsufficientBalanceException()
        return cls._settle_delegation_revoke_request(delegation_revoke_request)

    @classmethod
    def create_unfilled_capacity_alert(cls, pool: LiquidityPool, user: User):
        result = UserLevelManager.is_eligible_to_delegate_to_liquidity_pool(user)
        if not result:
            raise PermissionDeniedException()

        _, created = PoolUnfilledCapacityAlert.objects.get_or_create(pool=pool, user=user, sent_at=None)

        if not created:
            raise UnfilledCapacityAlertExist()

    @classmethod
    def remove_unfilled_capacity_alert(cls, pool: LiquidityPool, user: User):
        num, _ = PoolUnfilledCapacityAlert.objects.filter(pool=pool, user=user, sent_at=None).delete()

        if num == 0:
            raise UnfilledCapacityAlertDoesNotExist()

    @classmethod
    def remove_inactive_minimum_available_ratio_alerts(cls):
        created_at = timezone.now() - timedelta(days=2)
        PoolMinimumAvailableRatioAlert.objects.filter(is_active=False, created_at__lte=created_at).delete()

    @classmethod
    def notify_minimum_available_ratio(cls):
        pools = LiquidityPool.objects.filter(is_active=True)
        subquery = PoolMinimumAvailableRatioAlert.objects.filter(pool=OuterRef("pk"))
        pools = pools.annotate(has_ratio_alert=Exists(subquery))

        alerts = []
        activate_pool_alerts = []
        inactivate_pool_alerts = []
        for pool in pools:
            available_ratio = pool.available_balance / pool.capacity
            if available_ratio < pool.min_available_ratio:
                if not pool.has_ratio_alert:
                    alerts.append(PoolMinimumAvailableRatioAlert(pool=pool))
                    if settings.IS_TESTNET:
                        continue
                    currency = get_currency_codename(pool.currency)
                    currency = '' if currency is None else currency
                    Notification.notify_admins(
                        message=f"{currency} Pool\n"
                        f"Available Balance: {pool.available_balance.normalize():f}\n"
                        f"Capacity: {pool.capacity.normalize():f}\n"
                        f"Available ratio: {available_ratio:.2f} < {pool.min_available_ratio:.2f}",
                        title="🛟 Low Pool Available Balance",
                        channel="pool",
                    )
                else:
                    activate_pool_alerts.append(pool.id)
            else:
                inactivate_pool_alerts.append(pool.id)

        PoolMinimumAvailableRatioAlert.objects.bulk_create(alerts, batch_size=1000)

        PoolMinimumAvailableRatioAlert.objects.filter(pool_id__in=activate_pool_alerts).update(is_active=True)

        PoolMinimumAvailableRatioAlert.objects.filter(pool_id__in=inactivate_pool_alerts).update(is_active=False)
