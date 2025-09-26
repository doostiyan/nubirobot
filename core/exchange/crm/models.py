import os
from datetime import timedelta
from typing import Union

from django.conf import settings
from django.db import models
from django.db.models.manager import BaseManager
from django.utils import timezone
from django.utils.text import slugify


class NewsTag(models.Model):
    name = models.TextField(max_length=50, unique=True, verbose_name='نام')
    slug = models.TextField(max_length=50, unique=True, db_index=True, verbose_name='شناسه')
    color = models.CharField(max_length=7, null=True, verbose_name='رنگ')

    class Meta:
        verbose_name = 'برچسب'
        verbose_name_plural = 'برچسب‌ها'

    @classmethod
    def get_tag(cls, name: str):
        """Get Tag object by name"""
        return cls.objects.get_or_create(name=name)[0]

    def __str__(self):
        return self.name

    def save(self, *args, update_fields=None, **kwargs):
        self.slug = slugify(self.name, allow_unicode=True)
        if update_fields:
            update_fields = (*update_fields, 'slug')

        super().save(*args, update_fields=update_fields, **kwargs)


class News(models.Model):
    DIRECTORY_NAME = 'news'
    CACHE_KEY = 'news_list'
    CACHE_TTL = 5 * 60  # 5 minutes, in seconds
    NEWS_ACTIVE_PERIOD = timedelta(days=90)

    title = models.CharField(max_length=200, verbose_name='عنوان خبر')
    subtitle = models.CharField(max_length=1000, null=True, verbose_name='زیر تیتر')
    context = models.TextField(verbose_name='متن خبر')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='تاریخ ایجاد خبر')
    link = models.URLField(
        null=True, blank=True, verbose_name='لینک خبر'
    )  # This field has higher priority than image_name
    image = models.URLField(null=True, blank=True, verbose_name='لینک آپلود تصویر')
    publish_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name='تاریخ انتشار')
    is_disabled = models.BooleanField(default=False, verbose_name='غیرفعال')
    tags = models.ManyToManyField(NewsTag, related_name='news')
    image_name = models.UUIDField(blank=True, null=True)

    class Meta:
        verbose_name = 'اخبار'
        verbose_name_plural = verbose_name

    @classmethod
    def get_active_news(cls) -> 'BaseManager[News]':
        news = (
            cls.objects.filter(
                is_disabled=False,
                publish_at__lte=timezone.now(),
                publish_at__gte=timezone.now() - cls.NEWS_ACTIVE_PERIOD,
            )
            .order_by('-publish_at')
            .prefetch_related('tags')
        )
        return news

    @property
    def image_relative_path(self) -> str:
        return os.path.join('uploads', self.DIRECTORY_NAME, self.image_name.hex)

    @property
    def image_disk_path(self) -> str:
        return os.path.join(settings.MEDIA_ROOT, self.image_relative_path)

    @property
    def image_serve_url(self) -> Union[str, None]:
        if self.image:
            return self.image

        if self.image_name:
            return f'/media/uploads/{self.DIRECTORY_NAME}/{self.image_name.hex}'

        return None
