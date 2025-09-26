from django.db import models


class EmailInfo(models.Model):
    to = models.EmailField()
    template = models.CharField(max_length=100)
    context = models.JSONField(blank=True, null=True)
    priority = models.CharField(max_length=10)
    backend = models.CharField(max_length=20)
    scheduled_time = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'مدل تستی ایمیل'
