import uuid

from django.core.management import BaseCommand
from django.db import transaction

from exchange.accounts.models import User


class Command(BaseCommand):
    def handle(self, *args, **options):
        users_without_webengage_id = User.objects.filter(webengage_cuid__isnull=True)
        with transaction.atomic():
            for user in users_without_webengage_id:
                user.webengage_cuid = uuid.uuid4()
                user.save()
