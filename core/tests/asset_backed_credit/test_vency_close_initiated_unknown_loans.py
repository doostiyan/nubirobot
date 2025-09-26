from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import Service, UserService, UserServicePermission
from exchange.base.calendar import ir_now


class CommandsTestCase(TestCase):
    def setUp(self):
        self.service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan, defaults={'is_active': True}
        )
        self.service_2, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.tara, tp=Service.TYPES.loan, defaults={'is_active': True}
        )

        created = UserService.STATUS.created
        initiated = UserService.STATUS.initiated
        settled = UserService.STATUS.settled
        self.user_service_1 = self.create_user_service(self.service, '1000000000', Decimal('1000'), created, '')
        self.user_service_1 = self.create_user_service(self.service, '1000000001', Decimal('1000'), created, '123')

        self.user_service_1 = self.create_user_service(self.service, '1000000002', Decimal('1000'), initiated, '')
        self.user_service_1 = self.create_user_service(self.service, '1000000003', Decimal('1234'), initiated, '456')
        self.user_service_1 = self.create_user_service(self.service, '1000000004', Decimal('1000'), initiated, '')
        self.user_service_1 = self.create_user_service(self.service, '1000000005', Decimal('1111'), initiated, '10101')

        self.user_service_1 = self.create_user_service(self.service, '1000000006', Decimal('1000'), settled, '')
        self.user_service_1 = self.create_user_service(self.service, '1000000007', Decimal('1000'), settled, '789')

        self.user_service_1 = self.create_user_service(self.service_2, '1000000008', Decimal('1000'), created, '101112')
        self.user_service_1 = self.create_user_service(self.service_2, '1000000009', Decimal('1000'), initiated, '')
        self.user_service_1 = self.create_user_service(self.service_2, '1000000010', Decimal('1000'), settled, '')

    def test_command(self):
        assert (
            UserService.objects.filter(
                service__provider=Service.PROVIDERS.vency,
                service__tp=Service.TYPES.loan,
                status=UserService.STATUS.initiated,
                account_number='',
            ).count()
            == 2
        )

        assert (
            UserService.objects.filter(
                service__provider=Service.PROVIDERS.vency,
                service__tp=Service.TYPES.loan,
                status=UserService.STATUS.closed,
                closed_at__isnull=False,
                account_number='',
            ).count()
            == 0
        )

        call_command('abc_fix_initiated_vency_loans')

        assert (
            UserService.objects.filter(
                service__provider=Service.PROVIDERS.vency,
                service__tp=Service.TYPES.loan,
                status=UserService.STATUS.initiated,
                account_number='',
            ).count()
            == 0
        )

        assert (
            UserService.objects.filter(
                service__provider=Service.PROVIDERS.vency,
                service__tp=Service.TYPES.loan,
                status=UserService.STATUS.closed,
                closed_at__isnull=False,
                account_number='',
            ).count()
            == 2
        )

    def create_user_service(self, service, national_code: str, init_debt: Decimal, status: int, account_number=''):
        user, _ = User.objects.get_or_create(national_code=national_code, defaults={'username': national_code})
        permission = UserServicePermission.objects.create(user=user, service=self.service, created_at=ir_now())
        closed_at = ir_now() if status == UserService.STATUS.settled else None
        return UserService.objects.create(
            user=user,
            service=service,
            user_service_permission=permission,
            initial_debt=init_debt,
            current_debt=init_debt,
            principal=init_debt * Decimal('1.2'),
            installment_amount=init_debt * Decimal('0.2'),
            installment_period=6,
            provider_fee_amount=init_debt * Decimal('0.15'),
            status=status,
            closed_at=closed_at,
            account_number=account_number,
        )
