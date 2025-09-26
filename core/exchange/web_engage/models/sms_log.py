import json
from typing import List, Optional
from uuid import uuid4

from django.db import models
from django.db.models import DO_NOTHING, SET_NULL
from model_utils import Choices

from exchange.accounts.models import User


class WebEngageSMSBatch(models.Model):
    """
    Finnotext sends sms in batches. Every batch includes two lists. One of phone numbers and
    one of their corresponding messages.
    """
    STATUS = Choices(
        (1, 'new', 'new'),
        (2, 'sent_to_ssp', 'sent to ssp'),
        (3, 'failed_to_send_to_ssp', 'failed to send to ssp'),
        (4, 'inquired', 'inquired')
    )
    track_id = models.UUIDField(default=uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.IntegerField(choices=STATUS, default=STATUS.new)
    # Log fields. For debugging.
    call_logs = models.TextField(null=True, blank=True)
    inquiry_result = models.TextField(null=True, blank=True)

    def set_call_log(self, status_code: int, response_body: str, save: bool = False):
        call_log: List[dict] = json.loads(self.call_logs or '[]')
        call_log.append({'s': status_code, 'r': response_body})
        self.call_logs = json.dumps(call_log)
        if save:
            self.save(update_fields=('call_logs',))

    @property
    def last_status_code(self) -> Optional[int]:
        if self.call_logs:
            return json.loads(self.call_logs)[-1]['s']
        return None


class WebEngageSMSLog(models.Model):
    STATUS = Choices(
        (1, 'new', 'new'),
        (2, 'sent_to_ssp', 'sent to ssp'),
        (3, 'succeeded', 'succeeded'),
        (4, 'failed', 'failed'),
        (5, 'failed_to_send_to_ssp', 'failed to send to ssp')
    )
    track_id = models.UUIDField(default=uuid4, unique=True)
    text = models.TextField(verbose_name='متن پیامک')
    user = models.ForeignKey(User, related_name='+', on_delete=DO_NOTHING)
    phone_number = models.CharField(max_length=12, null=True, blank=True, verbose_name='شماره موبایل')
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.IntegerField(choices=STATUS, default=STATUS.new)
    message_id = models.CharField(max_length=40)
    batch = models.ForeignKey(WebEngageSMSBatch, null=True, blank=True, related_name='sms_logs', on_delete=SET_NULL)
