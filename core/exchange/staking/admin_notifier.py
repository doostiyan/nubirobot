from typing import Union

from django.core.cache import cache

from exchange.accounts.models import Notification
from exchange.base.helpers import deterministic_hash
from exchange.staking import errors


def notify_or_raise_exception_decorator(func):
    """As we know, staking project is implemented as some state machines and some state transitions.
        If a state transition fails, either there is a technical unexpected error that should be
        addressed by developer teams, or there is some operational problem (for example there is
        shortage of balance) that should be handled by operational personnel.
        This decorator wraps state transitions and in case of `Exception` pass the exception to
        `notify_or_raise_exception` which decide exception should be reported in `sentry` or
        `staking admin group`.
    """
    def wrapped_transition(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            notify_or_raise_exception(e)
    return wrapped_transition


def notify_or_raise_exception(exception: Union[errors.StakingError, Exception]):
    """This functions decides if for a given exception should raise an exception
        (to be perceived as an event in sentry) or should be used to sent as a notif
        to staking operational administrators.
    """
    if isinstance(
        exception,
        (
            errors.CallSupport,
            errors.FailedAssetTransfer,
            errors.AdminMistake,
            errors.UserWithNegativeBalanceOrDeactivatedWallet,
            errors.UserStakingAlreadyExtended,
            errors.AssetAlreadyStaked,
            errors.SystemRejectedCreateRequest,
        ),
    ):
        if should_back_off(exception):
            return None

        Notification.notify_admins(
            message=exception.message,
            title='🔵 ' + exception.code,
            channel='staking',
        )
        return None

    if might_be_a_systematic_problem(exception):
        raise exception

    return None


def should_back_off(exception: errors.StakingError) -> bool:
    """Since staking state transfer cron is running every few minutes (currently 5), there is
        a need for a mechanism that prevent sending repetitive notification. More precisely
        a notif could only be sent again after 2 hours.
    """
    back_off_period = 2 * 60 * 60  # 2 hours
    cache_key = f'staking_notif_back_of_{deterministic_hash(exception.code + exception.message)}'

    if cache.get(cache_key):
        return True

    cache.set(cache_key, True, back_off_period)
    return False


def might_be_a_systematic_problem(exception: Exception) -> bool:
    """Beside exception types that trigger a notification for admin, there are other types of
        exception that happens in one of these two scenarios: 1- It is side effect of an
        operational error. 2- It is something wrong with the code. This method determines
        that if an exception lies in which one of said categories.
    """
    suspicion_period = 60 * 60 * 6  # 6 hours
    alarming_occurrence_threshold = 20
    cache_key = f'staking_suspicious_exception_{deterministic_hash(str(exception))}'

    try:
        cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, suspicion_period)

    is_suspicious = cache.get(cache_key, 1) > alarming_occurrence_threshold
    if is_suspicious:
        cache.delete(cache_key)
    return is_suspicious
