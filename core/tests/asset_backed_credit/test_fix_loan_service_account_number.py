from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import Service, UserService, UserServicePermission
from exchange.base.calendar import ir_now


class CommandsTestCase(TestCase):
    def setUp(self):
        self.service_1, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan, defaults={'is_active': True}
        )
        self.service_2, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.tara, tp=Service.TYPES.credit, defaults={'is_active': True}
        )

        created = UserService.STATUS.created
        initiated = UserService.STATUS.initiated

        self.user_service_1 = self.create_user_service('1000000000', self.service_1, created, '111')
        self.user_service_2 = self.create_user_service('1000000001', self.service_2, created, '222')
        self.user_service_3 = self.create_user_service('1000000002', self.service_2, initiated, '333')
        self.user_service_4 = self.create_user_service('1000000003', self.service_1, initiated, '444')
        self.user_service_5 = self.create_user_service('1000000004', self.service_1, initiated, '555')

    def test_command(self):
        call_command('abc_fix_loan_service_account_numbers')

        self.user_service_1.refresh_from_db()
        self.user_service_2.refresh_from_db()
        self.user_service_3.refresh_from_db()
        self.user_service_4.refresh_from_db()
        self.user_service_5.refresh_from_db()

        assert self.user_service_1.account_number == str(self.user_service_1.external_id)
        assert self.user_service_2.account_number == '222'
        assert self.user_service_3.account_number == '333'
        assert self.user_service_4.account_number == str(self.user_service_4.external_id)
        assert self.user_service_5.account_number == str(self.user_service_5.external_id)

    @staticmethod
    def create_user_service(national_code: str, service: Service, status: int, account_number: str):
        user, _ = User.objects.get_or_create(national_code=national_code, defaults={'username': national_code})
        permission = UserServicePermission.objects.create(user=user, service=service, created_at=ir_now())
        closed_at = ir_now() if status == UserService.STATUS.settled else None
        debt = 100_000
        return UserService.objects.create(
            user=user,
            service=service,
            user_service_permission=permission,
            initial_debt=debt,
            current_debt=debt,
            principal=debt * Decimal('1.2'),
            installment_amount=debt * Decimal('0.2'),
            installment_period=6,
            provider_fee_amount=debt * Decimal('0.15'),
            account_number=account_number,
            status=status,
            closed_at=closed_at,
        )
