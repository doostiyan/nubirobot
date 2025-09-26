from django.core.management.base import BaseCommand
from django.db import transaction

from exchange.accounts.models import UserRestriction


class Command(BaseCommand):
    help = "Sets description and considerations for UserRestriction that are created with internal API"

    @transaction.atomic
    def handle(self, *args, **options):

        count = UserRestriction.objects.filter(
            restriction=UserRestriction.RESTRICTION.ChangeMobile,
            ref_id__isnull=False,
            source='abc',
            description__isnull=True,
        ).update(
            considerations='به دلیل فعال بودن اعتبار تارا، ‌کاربر امکان ویرایش شماره موبایل را ندارد.',
            description='به دلیل فعال بودن اعتبار تارا،‌ امکان ویرایش شماره موبایل وجود ندارد.',
        )

        self.stdout.write(self.style.SUCCESS(F'total updated records: {count}'))
