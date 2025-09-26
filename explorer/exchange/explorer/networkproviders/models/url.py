from django.db import models


class URL(models.Model):
    url = models.URLField(unique=True)
    use_proxy = models.BooleanField(default=False)

    def __str__(self):
        return self.url
