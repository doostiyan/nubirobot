import functools

from django.conf import settings
from rest_framework.permissions import BasePermission

from exchange.base.api import NobitexAPIError
from exchange.base.models import Settings
from exchange.features.models import QueueItem


def is_feature_enabled(user, feature) -> bool:
    """Check if this user has signed up for this feature and the
        feature is enabled for the user or not."""
    # Process parameters
    track = user.track or 0
    if isinstance(feature, str):
        feature = getattr(QueueItem.FEATURES, feature, None)
        if feature is None:
            return False

    # Check features available on testnet for all users
    if not settings.IS_PROD:
        if feature in [QueueItem.FEATURES.gift_card]:
            return True

    # Features enabled by default
    if feature in [QueueItem.FEATURES.stop_loss, QueueItem.FEATURES.oco]:
        return True

    # Check for special feature flags
    if feature == QueueItem.FEATURES.portfolio:
        return bool(track & QueueItem.BIT_FLAG_PORTFOLIO)

    # Check for Cobank Dynamic Flag
    if feature == QueueItem.FEATURES.cobank and Settings.get_value('cobank_check_feature_flag', 'yes') == 'no':
        return True

    if (
        feature == QueueItem.FEATURES.cobank_cards
        and Settings.get_value('cobank_card_check_feature_flag', 'yes') == 'no'
    ):
        return True

    if (
        feature == QueueItem.FEATURES.direct_debit
        and Settings.get_value('direct_debit_check_feature_flag', 'yes') == 'no'
    ):
        return True

    # Check for features queue
    item = QueueItem.objects.filter(feature=feature, user=user).first()
    if not item:
        return False
    return item.status == QueueItem.STATUS.done


def require_feature(feature: str):
    '''
    decorator to extend views functionality
    by checking if user has access to required feature.
    '''
    def decorator(view):
        @functools.wraps(view)
        def wrapped(request, *args, **kwargs):
            if not is_feature_enabled(request.user, feature):
                raise NobitexAPIError(
                    'FeatureUnavailable',
                    f'{feature} feature is not available for your user',
                )
            return view(request, *args, **kwargs)
        return wrapped
    return decorator


class FeatureEnabled(BasePermission):
    code = 'FeatureUnavailable'
    message = '%s feature is not available for your user'

    def has_permission(self, request, view):
        return is_feature_enabled(request.user, view.feature)


class BetaFeatureMixin:
    """Check whether a beta feature is enabled for the user

    Use in conjunction with restframework `APIView` subclasses.
    Set feature respectively.
    """
    feature: str

    def __init__(self, **kwargs):
        super(BetaFeatureMixin, self).__init__(**kwargs)
        self.permission_classes = list(getattr(self, 'permission_classes', [])) + [FeatureEnabled]

    def permission_denied(self, request, message=None, code=None):
        if code == FeatureEnabled.code:
            raise NobitexAPIError(code, FeatureEnabled.message % self.feature_display)
        super(BetaFeatureMixin, self).permission_denied(request, message, code)

    @property
    def feature_display(self) -> str:
        feature_value = getattr(QueueItem.FEATURES, self.feature, None)
        if feature_value is not None:
            return QueueItem.FEATURES[feature_value]
        return 'Undefined'
