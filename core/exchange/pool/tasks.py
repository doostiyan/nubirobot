from decimal import Decimal
from typing import Optional, Tuple

from celery import shared_task
from django.db import transaction

from exchange.accounts.models import User
from exchange.base.logging import report_event
from exchange.pool.errors import ExceedCapacityException, InsufficientBalanceException, InvalidDelegationAmount
from exchange.pool.models import DelegationTransaction, DelegationRevokeRequest ,LiquidityPool, UserDelegation
from exchange.pool.poolmanager import PoolManager

from exchange.wallet.models import Wallet


@shared_task(name='generate_nobitex_delegator_deposit_address')
def task_generate_deposit_address_for_nobitex_delegator(currency: int, network: Optional[str] = None):
    """Generate deposit address for nobitex delegator on pool creation"""
    wallet = Wallet.get_user_wallet(User.get_nobitex_delegator(), currency)
    with transaction.atomic():
        wallet.get_current_deposit_address(create=True, network=network)


@shared_task(name='nobitex_delegate')
def task_delegate_in_pool(pool_id: int, amount: str) -> Tuple[bool, Optional[str]]:
    amount = Decimal(amount)
    if amount <= 0:
        return False, 'Invalid Amount'

    try:
        with transaction.atomic():
            user_delegation, _ = UserDelegation.objects.get_or_create(
                pool_id=pool_id, user=User.get_nobitex_delegator()
            )
            DelegationTransaction.objects.create(user_delegation=user_delegation, amount=Decimal(amount))
    except LiquidityPool.DoesNotExist:
        return False, 'Invalid Pool'
    except ExceedCapacityException:
        return False, 'Exceed Capacity'
    except InsufficientBalanceException:
        return False, 'Invalid Amount'
    except InvalidDelegationAmount:
        return False, 'Insufficient Balance'
    return True, None


@shared_task(name="check_settle_delegation_revoke_request")
def task_check_settle_delegation_revoke_request(pool_id: int):
    PoolManager.check_delegation_revoke_request(pool_id)
