from django.db import models
from django.db.models import JSONField
from model_utils import Choices


class WebEngageEmailLog(models.Model):
    subject = models.CharField(max_length=1000, null=True)
    from_address = models.CharField(max_length=200, null=True)
    from_name = models.CharField(max_length=500, null=True)
    reply_to = models.CharField(max_length=500, null=True)
    message = models.TextField(null=False)
    html_message = models.TextField(null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    track_id = models.CharField(db_index=True, unique=True, max_length=200)
    custom_data = JSONField()


class WebEngageEmailRecipientLog(models.Model):
    SUBJECT_TYPES = Choices(
        (1, "normal", "Normal"),
        (2, "cc", "CC"),
        (3, "bcc", "BCC"),
    )
    to = models.CharField(db_index=True, max_length=200, null=False)
    subject_type = models.IntegerField(choices=SUBJECT_TYPES, default=SUBJECT_TYPES.normal)
    created_at = models.DateTimeField(auto_now_add=True)
    done_at = models.DateTimeField(null=True)
    status = models.CharField(max_length=200, default="PENDING", null=True)
    message_id = models.CharField(max_length=200, null=True)
    email_body = models.ForeignKey(WebEngageEmailLog, related_name="recipients", on_delete=models.CASCADE)
