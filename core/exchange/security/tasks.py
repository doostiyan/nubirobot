''' Security Tasks '''

from celery import shared_task

from exchange.security.models import KnownDevice


@shared_task(name='delete_all_devices_task',)
def delete_all_devices_task(user_id: int):
    KnownDevice.objects.filter(
        user_id=user_id,
    ).delete()
