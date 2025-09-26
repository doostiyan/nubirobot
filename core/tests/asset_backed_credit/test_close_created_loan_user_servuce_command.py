from django.core.management import call_command
from django.test import TestCase

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import Service, UserService, UserServicePermission
from exchange.base.calendar import ir_now


class CommandsTestCase(TestCase):
    def setUp(self):
        self.service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.vency,
            tp=Service.TYPES.loan,
            is_active=True,
        )
        self.user = User.objects.create_user(username='test-command')
        self.permission = UserServicePermission.objects.create(service=self.service, user=self.user)
        self.user_service_1 = UserService.objects.create(
            service=self.service,
            user=self.user,
            user_service_permission=self.permission,
            current_debt=1_000_000,
            initial_debt=1_000_000,
            status=UserService.STATUS.created,
        )
        self.permission.revoked_at = ir_now()
        self.permission.save()

        self.user = User.objects.create_user(username='test-command-2')
        self.permission = UserServicePermission.objects.create(service=self.service, user=self.user)
        self.user_service_2 = UserService.objects.create(
            service=self.service,
            user=self.user,
            user_service_permission=self.permission,
            current_debt=1_000_000,
            initial_debt=1_000_000,
            status=UserService.STATUS.created,
        )

    def test_command(self):
        return_val = call_command('abc_close_created_loan_user_services_with_deactivated_permissions')

        self.user_service_1.refresh_from_db()
        self.user_service_2.refresh_from_db()

        assert self.user_service_1.status == UserService.STATUS.closed
        assert self.user_service_1.closed_at is not None

        assert self.user_service_2.status == UserService.STATUS.created
        assert self.user_service_2.closed_at is None
