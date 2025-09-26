from typing import Optional

from exchange.accounts.models import User
from exchange.features.models import QueueItem


class BetaFeatureTestMixin:
    feature: str

    @classmethod
    def request_feature(cls, user: User, status: Optional[str] = None):
        QueueItem.objects.update_or_create(
            user=user,
            feature=getattr(QueueItem.FEATURES, cls.feature),
            defaults={
                'status': getattr(QueueItem.STATUS, status or 'waiting'),
            }
        )

    @classmethod
    def clear_feature(cls, user: User):
        QueueItem.objects.filter(user=user, feature=getattr(QueueItem.FEATURES, cls.feature)).delete()
