import logging
from datetime import datetime
from typing import Optional

from django.utils import timezone

from exchange.base.models import Settings
from exchange.web_engage.externals.web_engage import call_on_webengage_active
from exchange.web_engage.tasks import task_send_event_data_to_web_engage
from exchange.web_engage.utils import is_webengage_user

logger = logging.getLogger(__name__)


class WebEngageKnownUserEvent:
    event_name: str

    def __init__(self, user, event_time: Optional[datetime] = None, device_kind: Optional[str] = None):
        self.user = user
        self.event_time = event_time or timezone.now()
        self.device_kind = device_kind

    def _get_data(self) -> dict:
        raise NotImplementedError()

    def _is_eligible_for_sending(self) -> bool:
        if not is_webengage_user(self.user):
            return False
        if self.event_name in Settings.get_list("webengage_stopped_events"):
            return False
        return True

    @call_on_webengage_active
    def send(self):
        if not self._is_eligible_for_sending():
            return
        try:
            data = {
                "eventName": self.event_name,
                "eventTime": self.event_time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "eventData": self._get_data(),
                "userId": self.user.get_webengage_id()}

            # add device kind to eventData
            if self.device_kind is not None:
                data['eventData'].update({'device_kind': self.device_kind})

            task_send_event_data_to_web_engage.delay(data=data)
        except:
            logger.exception(f"Error processing web engage event {self.event_name}")
