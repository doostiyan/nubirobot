from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from exchange.asset_backed_credit.models import Service, UserService
from exchange.base.calendar import ir_now


class Command(BaseCommand):
    help = "Update unknown initiated loan services"

    def handle(self, *args, **options):
        user_services = UserService.objects.filter(
            service__provider=Service.PROVIDERS.vency,
            service__tp=Service.TYPES.loan,
            status=UserService.STATUS.initiated,
            account_number='',
        )

        with transaction.atomic():
            for user_service in user_services:
                try:
                    user_service.status = UserService.STATUS.closed
                    user_service.closed_at = ir_now()
                    user_service.user_service_permission.deactivate()
                    user_service.save(
                        update_fields=(
                            'status',
                            'closed_at',
                        )
                    )
                except Exception as e:
                    self.stdout.write(self.style.ERROR(str(e)))

        self.stdout.write(self.style.SUCCESS(f'Successfully closed {len(user_services)} loan services.'))
