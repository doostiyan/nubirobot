from celery import shared_task
from django.db import transaction

from .models import ShetabDeposit


@shared_task(name='update_user_invalid_deposits')
def task_update_user_invalid_deposits(user_id):
    ShetabDeposit.update_user_invalid_deposits(user_id)


@shared_task(name='shetab_deposit_sync')
@transaction.atomic
def task_shetab_deposit_sync(deposit_id):
    ShetabDeposit.objects.get(id=deposit_id).sync_and_update(retry=True)


@shared_task(name='shetab_deposit_sync_card')
@transaction.atomic
def task_shetab_deposit_sync_card(deposit_id):
    ShetabDeposit.objects.get(id=deposit_id).sync_card()


@shared_task(name='shetab.admin.add_vandar_customer')
def task_shetab_add_vandar_customer(user_id: int) -> None:
    from exchange.shetab.handlers.vandar import VandarP2P
    from exchange.accounts.models import User
    from exchange.base.parsers import parse_int

    user_id = parse_int(user_id, required=True)
    user = User.objects.filter(pk=user_id).first()
    if not user:
        raise ValueError('shetab.admin.add_vandar_customer: User {user_id} not found')

    vandar_account = VandarP2P.get_or_create_vandar_account(user)
    VandarP2P.get_or_create_payment_id(vandar_account)
