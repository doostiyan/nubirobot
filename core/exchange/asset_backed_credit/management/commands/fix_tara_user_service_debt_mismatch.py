from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import Service, UserService


class Command(BaseCommand):
    help = 'Fix TARA user service debt mismatch'

    DATA = {
        '09122169951': Decimal('20681665'),
    }

    def handle(self, *args, **options):
        try:
            service = Service.objects.get(tp=Service.TYPES.credit, provider=Service.PROVIDERS.tara)
        except Service.DoesNotExist:
            raise CommandError('Tara user service provider does not exist')

        for mobile_number, current_debt in self.DATA.items():
            try:
                user = User.objects.get(mobile=mobile_number)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR_OUTPUT('Mobile number "%s" does not exist' % mobile_number))
                continue

            user_service = (
                UserService.objects.filter(user=user, service=service, closed_at__isnull=True).order_by('id').last()
            )
            if not user_service:
                self.stdout.write(self.style.ERROR('UserService for "%s" does not exist' % mobile_number))
                continue

            user_service.current_debt = current_debt
            user_service.save(update_fields=['current_debt'])

            self.stdout.write(self.style.SUCCESS('Successfully updated user-service for "%s"' % mobile_number))
