from decimal import Decimal

from exchange.base.constants import ZERO
from exchange.base.models import get_currency_codename
from exchange.base.serializers import register_serializer
from exchange.pool.models import (DelegationRevokeRequest, DelegationTransaction, LiquidityPool, UserDelegation,
                                  UserDelegationProfit)


@register_serializer(model=LiquidityPool)
def serialize_liquidity_pool(pool: LiquidityPool, opts: dict):
    opts = opts or {}
    level = opts.get("level")
    data = {
        "id": pool.id,
        "capacity": pool.capacity,
        "filledCapacity": pool.filled_capacity - pool.revoked_capacity,
        "availableBalance": pool.unfilled_capacity,
        "currentProfit": int(max(pool.current_profit, Decimal(0))),
        "APR": pool.apr,
        "profitPeriod": pool.profit_period,
        "startDate": pool.start_date,
        "endDate": pool.end_date,
        "profitDate": pool.profit_date,
    }

    if level == 2:
        data.update(
            {
                "minDelegation": pool.min_delegation,
                "maxDelegation": min(pool.get_max_delegation(opts["user_type"]), pool.capacity),
                "hasDelegate": pool.has_delegate,
                "hasActiveAlert": pool.has_active_alert,
            }
        )

    return data

@register_serializer(model=DelegationTransaction)
def serialize_delegation_tx(delegation_tx: DelegationTransaction, opts: dict):
    data = {
        'amount': delegation_tx.amount,
        'createdAt': delegation_tx.created_at,
        'currency': get_currency_codename(delegation_tx.user_delegation.pool.currency),
        'userDelegationId': delegation_tx.user_delegation_id,
    }
    if hasattr(delegation_tx, 'delegation_revoke_request'):
        data['requestedAt'] = delegation_tx.delegation_revoke_request.created_at
    return data


@register_serializer(model=UserDelegation)
def serialize_user_delegation(user_delegation: UserDelegation, opts: dict):
    return {
        'id': user_delegation.pk,
        'pool': user_delegation.pool,
        'balance': user_delegation.balance,
        'createdAt': user_delegation.created_at,
        'closedAt': user_delegation.closed_at,
        'totalProfit': user_delegation.total_profit,
        'currency': get_currency_codename(user_delegation.pool.currency),
        'revokingBalance': getattr(user_delegation, 'revoking_balance', ZERO),
        'minRevoke': user_delegation.pool.min_delegation,
    }


@register_serializer(model=UserDelegationProfit)
def serialize_user_profit(user_profit: UserDelegationProfit, opts: dict):
    return {
        'userDelegationId': user_profit.user_delegation_id,
        'currency': get_currency_codename(user_profit.user_delegation.pool.currency),
        'amount': user_profit.amount,
        'toDate': user_profit.to_date,
        'fromDate': user_profit.from_date,
        'settledAt': user_profit.settled_at,
    }


@register_serializer(model=DelegationRevokeRequest)
def serialize_delegation_revoke_request(delegation_revoke_request: DelegationRevokeRequest, opts: dict):
    return {
        'id': delegation_revoke_request.id,
        'userDelegationId': delegation_revoke_request.user_delegation_id,
        'currency': get_currency_codename(delegation_revoke_request.user_delegation.pool.currency),
        'amount': delegation_revoke_request.amount,
        'createdAt': delegation_revoke_request.created_at,
        'status': delegation_revoke_request.get_status_display(),
        'settledAt': delegation_revoke_request.settled_at,
    }
