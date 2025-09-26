"""Some staking-agnostic functions which are used being in staking"""
import datetime
import enum
import functools
from decimal import Decimal
from typing import Optional

from django.conf import settings

from exchange.accounts.models import User
from exchange.accounts.userlevels import UserLevelManager
from exchange.base.api import NobitexAPIError, email_required_api
from exchange.base.api_v2_1 import NobitexError
from exchange.base.calendar import ir_now
from exchange.base.models import Settings
from exchange.staking import errors
from exchange.staking.errors import InsufficientWalletBalance
from exchange.wallet.models import Wallet


def staking_user_level(view):
    @functools.wraps(view)
    def wrapped(request, *args, **kwargs):
        result = UserLevelManager.is_eligible_to_stake(request.user)
        if not result:
            raise NobitexAPIError(
                'UserLevelRestriction',
                'Cant do this with your current user level.',
            )
        return view(request, *args, **kwargs)
    return email_required_api(wrapped)


@functools.lru_cache(maxsize=1)
def get_asset_collector_user() -> User:
    """This is the mediator system user who is in charge of collecting users assets and transferring
        them to external platform. when a staking plan is ended, assets and rewards from external platform
        initially will be transferred to wallets of this user.
    """
    return User.objects.get(username='system-staking')


@functools.lru_cache(maxsize=1)
def get_fee_collector_user() -> User:
    return User.objects.get(username='system-staking-fee')


@functools.lru_cache(maxsize=1)
def get_nobitex_reward_collector() -> User:
    """Note that since some of the staking plans might not reach their full capacity, there should
        be a system user for collecting rewards of unassigned capacity of plan.
    """
    return User.objects.get(username='system-staking-rewards')


def staking_exc_to_api_exc_translator(exception: Exception) -> Optional[Exception]:
    """Different APIs provide users with means to create
        distinct type of requests (for example, request
        for creation of staking, ending staking request,
        or canceling some other request,...), this function
        converts common `staking core` exceptions among these
        requests to appropriate API exceptions.
    """

    if isinstance(exception, errors.RequestAccumulationInvalidAmount):
        return NobitexError(
            status_code=400,
            code='RequestAccumulationInvalidAmount',
            message='You have already an active request.',
        )

    if isinstance(exception, errors.InvalidAmount):
        return NobitexError(
            status_code=400,
            code='InvalidAmount',
            message='amount is not acceptable.',
        )

    if isinstance(exception, errors.InvalidPlanId):
        return NobitexError(
            code='InvalidPlanId',
            message='No plan was found with submitted plan id',
            status_code=404,
        )

    if isinstance(exception, errors.RecentlyCanceled):
        return NobitexError(
            status_code=400,
            code='RecentlyCanceled',
            message='User is restricted because of recent cancellation',
        )

    if isinstance(exception, errors.TooLate):
        return NobitexError(
            status_code=400,
            code='TooLate',
            message='It is too late',
        )

    if isinstance(exception, errors.TooSoon):
        return NobitexError(
            status_code=400,
            code='TooSoon',
            message='It is too soon',
        )

    if isinstance(exception, errors.NonExtendablePlan):
        return NobitexError(
            status_code=400,
            code='NonExtendablePlan',
            message='Plan is not extendable',
        )

    return None


def is_v1_end_request_active():
    """In Staking v2 `auto end` and `instant end` were introduced,
    both of these features are generalizations of staking v1 end request,
    hence to avoid confusion and prevent clients from breaking, we would define
    two new endpoints for `auto end` and `instant end`. (in contrast to generalizing
    staking v1 end requests to one of `auto end` or `instant end`). This method would
    decide whether staking v1 end request should still work or become deprecated.
    """
    return Settings.get_flag('staking_v1_end_staking', default='yes')


class Restriction(enum.Enum):

    CREATE_REQUEST = 'StakingParticipation'

    AUTO_EXTEND = 'StakingRenewal'

    INSTANT_END = 'StakingCancellation'


def check_user_restriction(restriction: Restriction):
    def decorator(view):
        @functools.wraps(view)
        def decorated(request, *args, **kwargs):
            if request.user.is_restricted(restriction.value):
                raise NobitexAPIError(
                    'ActionIsRestricted',
                    'You have been restricted by admin.',
                )
            return view(request, *args, **kwargs)

        return decorated

    return decorator


class OperationTime:

    @staticmethod
    def get_next() -> datetime.datetime:
        return OperationTime.get_latest() + datetime.timedelta(days=1)

    @staticmethod
    def get_latest() -> datetime.datetime:
        today_15_pm = ir_now().replace(hour=15, minute=0, second=0, microsecond=0)
        return today_15_pm if ir_now() >= today_15_pm else today_15_pm - datetime.timedelta(days=1)


def check_wallet_balance(user_id: int, currency: int, amount: Decimal):
    wallet = Wallet.get_user_wallet(user=user_id, currency=currency, create=False)

    if not wallet or wallet.balance < amount:
        raise InsufficientWalletBalance()


def env_aware_ratelimit(rate: str) -> str:
    if settings.IS_TESTNET:
        return '150/1m'

    return rate


class StakingFeatureFlags(str, enum.Enum):
    API_DUAL_WRITE = 'staking_use_api_dual_write'
    CRONJOB_DUAL_WRITE = 'staking_use_cronjob_dual_write'

