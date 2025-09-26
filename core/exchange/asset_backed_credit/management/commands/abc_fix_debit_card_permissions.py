from django.core.management.base import BaseCommand
from django.db import transaction

from exchange.asset_backed_credit.models import Service, UserService, UserServicePermission


class Command(BaseCommand):
    help = "Set created_at on debit user-service-permissions and fix missmatch service-types"

    def handle(self, *args, **options):
        with transaction.atomic():
            debit_services = UserService.objects.select_for_update().filter(service__tp=Service.TYPES.debit)

            for user_service in debit_services:
                try:
                    permission = UserServicePermission.objects.select_for_update().get(
                        id=user_service.user_service_permission.id
                    )
                    permission.created_at = user_service.created_at
                    permission.service = user_service.service
                    permission.save(update_fields=['created_at', 'service'])

                    self.stdout.write(self.style.SUCCESS(f'Successfully updated invalid permission: {permission.pk}.'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Failed to update permission: {permission.pk}'))
                    self.stdout.write(self.style.ERROR(str(e)))
