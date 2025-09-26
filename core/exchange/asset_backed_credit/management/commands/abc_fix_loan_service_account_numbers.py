from django.core.management import BaseCommand

from exchange.asset_backed_credit.models import Service, UserService


class Command(BaseCommand):
    help = 'fix loan service account numbers'

    def handle(self, *args, **options):
        user_services = UserService.objects.filter(service__tp=Service.TYPES.loan)
        self.stdout.write(self.style.SUCCESS(f'total {len(user_services)} user-services selected.'))
        for user_service in user_services:
            user_service.account_number = str(user_service.external_id)
            user_service.save(update_fields=['account_number'])

        self.stdout.write(self.style.SUCCESS('user-services updated successfully.'))
