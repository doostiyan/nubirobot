from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from model_utils import Choices

from exchange.celery import app as celery_app


class TicketingGroup(models.Model):
    name = models.CharField(verbose_name='نام', max_length=50, null=False)
    descriptions = models.TextField(verbose_name='توضیحات', max_length=500, null=True, blank=True)
    supervisor = models.ForeignKey('accounts.User', related_name='ticketing_groups', verbose_name='مدیر گروه', null=True,
                                   blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.name


class Topic(models.Model):
    PRIORITY_CHOICES = Choices(
        (0, 'very_low', 'خیلی کم'),
        (50, 'low', 'کم'),
        (100, 'normal', 'متوسط'),
        (150, 'high', 'زیاد'),
        (200, 'critical', 'بسیار زیاد'),
    )
    title = models.CharField(verbose_name='عنوان', max_length=100)
    descriptions = models.TextField(verbose_name='توضیحات', max_length=1000, null=True, blank=True)
    group_in_charge = models.ForeignKey('TicketingGroup', verbose_name='گروه مسئول', null=True, blank=True,
                                        on_delete=models.SET_NULL, related_name='topics')
    members = models.ManyToManyField('accounts.User', related_name='ticketing_topics',
                                     verbose_name='اعضا')
    show_to_users = models.BooleanField(default=False, verbose_name="نمایش به کاربر")
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=PRIORITY_CHOICES.normal,
                                   verbose_name='اولویت')
    _is_deleted = models.BooleanField(default=False, verbose_name="حذف شده")

    def __str__(self):
        return self.title


class Ticket(models.Model):
    STATE_CHOICES = Choices(
        (0, 'sent', 'ارسال‌شده'),
        (1, 'pending', 'در حال بررسی'),
        (2, 'resolved', 'پاسخ‌داده‌شده'),
        (3, 'spam', 'اسپم'),
        (4, 'closed', 'بسته')
    )

    PRIORITY_CHOICES = Choices(
        (100, 'normal', 'عادی'),
        (200, 'urgent', 'فوری'),
    )

    RATE_CHOICES = Choices(
        (1, 'weak', 'ضعیف'),
        (2, 'not_bad', 'بد نبود'),
        (3, 'so_so', 'متوسط'),
        (4, 'good', 'خوب'),
        (5, 'excellent', 'عالی'),
    )

    TASK_TYPE_CHOICES = Choices(
        (0, 'ticketing', 'تیکتینگ')
    )

    is_private = models.BooleanField(default=False)
    state = models.IntegerField(verbose_name='وضعیت', choices=STATE_CHOICES, default=STATE_CHOICES.sent, db_index=True)
    topic = models.ForeignKey('Topic', on_delete=models.SET_NULL, null=True, blank=False,
                              limit_choices_to={'show_to_users': True},
                              verbose_name='موضوع',
                              related_name='tickets')
    content = models.TextField(verbose_name='محتوا', max_length=1000)
    created_at = models.DateTimeField(verbose_name='زمان ایجاد', auto_now_add=True)
    created_by = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='+',
                                   verbose_name='سازنده')
    related_user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='+',
                                     verbose_name='کاربر')
    _assigned_to = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='+', verbose_name='کارشناس')
    group = models.ForeignKey('TicketingGroup', on_delete=models.SET_NULL, null=True, related_name='tickets',
                              verbose_name='گروه')
    files = models.ManyToManyField('accounts.UploadedFile', blank=True, related_name='+', verbose_name='فایل‌های پیوست')
    tags = models.ManyToManyField('TicketingTag', blank=True, related_name='tickets', verbose_name='برچسب‌ها')
    priority = models.IntegerField(verbose_name='اولویت', choices=PRIORITY_CHOICES, default=PRIORITY_CHOICES.normal)
    waiting_time = models.DurationField(null=True)
    rating = models.IntegerField(null=True, verbose_name='امتیاز', choices=RATE_CHOICES)
    rating_note = models.TextField(blank=True, verbose_name='توضیحات', max_length=400)

    def save(self, *args, update_fields=None, **kwargs):
        if self.topic and not self.group:
            self.group = self.topic.group_in_charge
            if update_fields is not None:
                update_fields = (*update_fields, 'group')

        super().save(*args, update_fields=update_fields, **kwargs)

    @property
    def assigned_to(self):
        return self._assigned_to

    def close(self):
        self.state = Ticket.STATE_CHOICES.closed
        self._assigned_to = None
        self.save(update_fields=['state', '_assigned_to'])
        # The below code will cancel the related employee task of the closed ticket
        celery_app.send_task('admin.cancel_employee_task', args=(Ticket.TASK_TYPE_CHOICES.ticketing, self.pk))

    @property
    def state_name(self):
        return self.STATE_CHOICES[self.state]

    @property
    def files_urls(self):
        urls = [reverse(
            'download_ticket_attachment',
            kwargs={'file_hash': attachment.filename}
        ) for attachment in self.files.all()]
        return urls

    @property
    def comments(self):
        return self.activities.filter(type=Activity.TYPES.comment)


class ReadyMessage(models.Model):
    content = models.TextField(verbose_name='محتوا', max_length=1000)
    title = models.CharField(verbose_name='عنوان', max_length=50, null=True)


class Activity(models.Model):
    TYPES = Choices(
        (1, 'log', _('log')),
        (2, 'private_message', _('private_message')),
        (3, 'comment', _('comment')),
        (4, 'report', _('report')),
        (5, 'deleted_comment', _('delete_comment')),
    )
    ticket = models.ForeignKey('Ticket', on_delete=models.CASCADE, related_name='activities')
    created_at = models.DateTimeField(auto_now_add=True)
    type = models.IntegerField(choices=TYPES)
    actor = models.ForeignKey(get_user_model(), on_delete=models.PROTECT, related_name='+')
    content = models.TextField(max_length=1000, blank=False, null=False)
    files = models.ManyToManyField('accounts.UploadedFile', blank=True, related_name='+',
                                   verbose_name='فایل‌های پیوست')
    seen_at = models.DateTimeField(null=True, editable=False, verbose_name='تاریخ مشاهده')

    @property
    def files_urls(self):
        urls = [reverse(
            'download_ticket_attachment',
            kwargs={'file_hash': attachment.filename}
        ) for attachment in self.files.all()]
        return urls

    @property
    def actor_name(self):
        return str(self.actor)


class TicketingTag(models.Model):
    group = models.ForeignKey('TicketingGroup', null=True, blank=True, on_delete=models.CASCADE, related_name='tags')
    name = models.TextField(max_length=50, blank=False, null=False)

    def __str__(self):
        return self.name


