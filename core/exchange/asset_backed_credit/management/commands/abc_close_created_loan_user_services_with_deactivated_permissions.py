from django.core.management.base import BaseCommand

from exchange.asset_backed_credit.models import Service, UserService
from exchange.base.calendar import ir_now


class Command(BaseCommand):
    help = "Closes loan user services with deactivated permissions"

    def handle(self, *args, **options):
        service = Service.objects.get(provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan)
        total_updated = UserService.objects.filter(
            service=service,
            status=UserService.STATUS.created,
            closed_at__isnull=True,
            user_service_permission__revoked_at__isnull=False,
        ).update(status=UserService.STATUS.closed, closed_at=ir_now())

        self.stdout.write(self.style.SUCCESS('total updated: %d' % total_updated))
