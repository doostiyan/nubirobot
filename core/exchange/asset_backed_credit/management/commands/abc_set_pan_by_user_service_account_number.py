from datetime import date

from django.core.management.base import BaseCommand, CommandError

from exchange.asset_backed_credit.models import AssetToDebtMarginCall, Card, Service, UserService


class Command(BaseCommand):
    help = "Update last margin call actions"

    def handle(self, *args, **options):
        total, total_errors = self.set_pan_by_user_service_account_number()
        self.stdout.write(self.style.SUCCESS(f'updated total {total} cards, {total_errors} errors occurred'))

    def set_pan_by_user_service_account_number(self):
        user_services = UserService.objects.filter(
            account_number__isnull=False, service__tp=Service.TYPES.debit
        ).select_related('user')

        total_errors = 0

        for user_service in user_services:
            try:
                Card.objects.create(
                    pan=user_service.account_number,
                    status=Card.STATUS.activated,
                    user_service=user_service,
                    user=user_service.user,
                )
            except Exception as e:
                total_errors += 1
                self.stdout.write(self.style.ERROR(str(e)))

        return len(user_services), total_errors
