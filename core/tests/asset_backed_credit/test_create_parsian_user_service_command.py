from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import Service, UserService, UserServicePermission


class CommandsTestCase(TestCase):
    def setUp(self):
        self.user1, _ = User.objects.get_or_create(username='john.doe', mobile='090010001010')
        self.user2, _ = User.objects.get_or_create(username='john.wick', mobile='090020002020')
        self.user3, _ = User.objects.get_or_create(username='john.june', mobile='090040004040')

        self.service, _ = Service.objects.get_or_create(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)

    def test_command(self):
        args = []
        opts = {}

        user_service_permission, _ = UserServicePermission.objects.get_or_create(user=self.user3, service=self.service)
        UserService.objects.get_or_create(
            service=self.service,
            user=self.user3,
            user_service_permission=user_service_permission,
            account_number='6037200020002000',
            current_debt=0,
            initial_debt=0,
        )

        with patch(
            'exchange.asset_backed_credit.management.commands.abc_create_parsian_user_services.Command._get_data_by_user_id',
            return_value={'6037100010001000': self.user1.id},
        ), patch(
            'exchange.asset_backed_credit.management.commands.abc_create_parsian_user_services.Command._get_data_by_user_id_for_update',
            return_value={'6037200020002000': self.user2.id},
        ):
            call_command('abc_create_parsian_user_services', *args, **opts)

        assert UserService.objects.filter(user__in=[self.user1, self.user2], service=self.service).count() == 2

        assert UserService.objects.filter(
            user=self.user1, service=self.service, account_number='6037100010001000'
        ).exists()
        assert UserService.objects.filter(
            user=self.user2, service=self.service, account_number='6037200020002000'
        ).exists()

        assert not UserService.objects.filter(service=self.service, account_number='6037300030003000').exists()
        assert not UserService.objects.filter(user=self.user3, service=self.service).exists()
