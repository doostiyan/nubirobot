from django.core.management.base import BaseCommand

from exchange.asset_backed_credit.models import Service, UserFinancialServiceLimit


class Command(BaseCommand):
    help = "Update limits for release 7.5"

    def handle(self, *args, **options):
        self.update_limit_types()
        self.set_limit_on_service_types()

    def update_limit_types(self):
        user = UserFinancialServiceLimit.objects.filter(tp=1).update(tp=10)
        user_service = UserFinancialServiceLimit.objects.filter(tp=2).update(tp=20)
        service_user_type = UserFinancialServiceLimit.objects.filter(tp=3).update(tp=60)
        service = UserFinancialServiceLimit.objects.filter(tp=4).update(tp=90)

        self.stdout.write(self.style.SUCCESS(f'total {user} limits updated.'))
        self.stdout.write(self.style.SUCCESS(f'total {user_service} limits updated.'))
        self.stdout.write(self.style.SUCCESS(f'total {service_user_type} limits updated.'))
        self.stdout.write(self.style.SUCCESS(f'total {service} limits updated.'))

    def set_limit_on_service_types(self):
        credit, _ = UserFinancialServiceLimit.objects.update_or_create(
            tp=110,  # service_type
            user=None,
            user_type=None,
            service=None,
            service_provider=None,
            service_type=1,  # credit
            defaults={'min_limit': 5_000_000, 'limit': None},
        )

        loan, _ = UserFinancialServiceLimit.objects.update_or_create(
            tp=110,  # service_type
            user=None,
            user_type=None,
            service=None,
            service_provider=None,
            service_type=2,  # loan
            defaults={'min_limit': 50_000_000, 'limit': None},
        )

        debit, _ = UserFinancialServiceLimit.objects.update_or_create(
            tp=110,  # service_type
            user=None,
            user_type=None,
            service=None,
            service_provider=None,
            service_type=3,  # debit
            defaults={'min_limit': 10_000, 'limit': None},
        )

        self.stdout.write(self.style.SUCCESS(f'credit limit created: {credit.tp} {credit.min_limit} {credit.limit}'))
        self.stdout.write(self.style.SUCCESS(f'loan limit created: {loan.tp} {loan.min_limit} {loan.limit}'))
        self.stdout.write(self.style.SUCCESS(f'debit limit created: {debit.tp} {debit.min_limit} {debit.limit}'))
