from typing import List

from celery import shared_task
from django.db import transaction
from exchange.base.logging import report_event
from exchange.base.calendar import ir_today
from exchange.promotions.models import UserDiscountBatch
from exchange.promotions.discount import process_user_discount_batch_file


@shared_task(name='create_user_discount')
def task_create_user_discount(user_discount_batch_id: int, we_ids: List[str]):
    """Make user discount"""

    with transaction.atomic():
        user_discount_batch = UserDiscountBatch.objects.select_for_update().select_related('discount', 'file')\
                                                       .get(id=user_discount_batch_id)
        if user_discount_batch is None:
            report_event('UserDiscountBatchDoseNotExistError', extras={'src': 'TaskCreateUserDiscount'})
            return

        process_user_discount_batch_file(user_discount_batch, we_ids, ir_today())
