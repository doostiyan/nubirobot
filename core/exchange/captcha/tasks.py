from celery import shared_task
from django.conf import settings
from django.core.management import call_command


@shared_task(name='create_captcha_pool', max_retries=1)
def task_create_captcha_pool():
    call_command('captcha_create_pool', pool_size=5000 if settings.IS_PROD else 10, loop=False)
