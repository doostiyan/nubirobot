from django.core.management.base import BaseCommand
from django.db.transaction import atomic

from exchange.accounts.models import UserRestriction
from exchange.asset_backed_credit.models import Service, UserService


class Command(BaseCommand):
    help = "Adds change mobile restriction to users with active tara account"

    @atomic
    def handle(self, *args, **options):
        active_tara_user_services = UserService.objects.filter(
            service__provider=Service.PROVIDERS.tara, service__is_active=True, closed_at__isnull=True
        ).select_for_update()

        for user_service in active_tara_user_services:
            UserRestriction.objects.get_or_create(
                user=user_service.user,
                restriction=UserRestriction.RESTRICTION.ChangeMobile,
                source='abc',
                ref_id=user_service.id,
                defaults={
                    'considerations': 'به دلیل فعال بودن اعتبار تارا، ‌کاربر امکان ویرایش شماره موبایل را ندارد.',
                    'description': 'به دلیل فعال بودن اعتبار تارا،‌ امکان ویرایش شماره موبایل وجود ندارد.',
                },
            )

        self.stdout.write(self.style.SUCCESS(F'total updated records: {len(active_tara_user_services)}'))
