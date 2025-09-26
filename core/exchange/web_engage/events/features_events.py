from datetime import datetime
from typing import Optional

from exchange.web_engage.events.base import WebEngageKnownUserEvent


class FeatureEnabledWebEngageEvent(WebEngageKnownUserEvent):
    event_name = "feature_enabled"

    def __init__(self, user, feature, event_time: Optional[datetime] = None):
        super().__init__(user, event_time)
        self.feature = feature

    def _get_data(self) -> dict:
        return {
            "feature": str(self.feature),
        }
