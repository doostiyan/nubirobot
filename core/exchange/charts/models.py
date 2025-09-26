from django.conf import settings
from django.db import models
from jsonfield import JSONField

from exchange.accounts.models import User


class Chart(models.Model):
    ownerSource = models.CharField(max_length=200, db_index=True, db_column='owner_source')
    ownerId = models.CharField(max_length=200, db_index=True, db_column='owner_id')
    name = models.CharField(max_length=200)
    symbol = models.CharField(max_length=50)
    resolution = models.CharField(max_length=10)
    lastModified = models.DateTimeField(auto_now=True)
    content = JSONField()
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='charts', null=True)

    def __str__(self):
        return self.ownerSource + ':' + self.ownerId

    def setContent(self, _content):
        self.content = _content


class StudyTemplate(models.Model):
    ownerSource = models.CharField(max_length=200, db_index=True, db_column='owner_source')
    ownerId = models.CharField(max_length=200, db_index=True, db_column='owner_id')
    name = models.CharField(max_length=200)
    content = JSONField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='study_templates', null=True
    )

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'name'], name='unique_studytemplate_user_name_asdji29a')]

    def __str__(self):
        return self.ownerSource + ':' + self.ownerId

    def setContent(self, _content):
        self.content = _content
