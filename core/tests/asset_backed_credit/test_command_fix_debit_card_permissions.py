import random
import string

from django.core.management import call_command
from django.test import TestCase

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import Service, UserService, UserServicePermission
from tests.asset_backed_credit.helper import ABCMixins


class TestFixDebitCardUserServicePermissionsCommand(ABCMixins, TestCase):
    def setUp(self):
        self.service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit, is_active=True)
        self.invalid_service = self.create_service()
        self.user_1, _ = User.objects.get_or_create(username='user-test-01')
        self.user_2, _ = User.objects.get_or_create(username='user-test-02')
        self.user_3, _ = User.objects.get_or_create(username='user-test-03')

        self.create_debit_user_service(service=self.service, user=self.user_1)
        self.create_debit_user_service(service=self.service, user=self.user_2, missmatch_service=self.invalid_service)
        self.create_debit_user_service(service=self.service, user=self.user_3)

    def testCommand(self):
        assert UserServicePermission.objects.filter(service=self.service).count() == 2
        assert UserServicePermission.objects.filter(service=self.invalid_service).count() == 1
        assert UserServicePermission.objects.filter(created_at__isnull=True).count() == 3
        assert UserServicePermission.objects.filter(created_at__isnull=False).count() == 0

        call_command('abc_fix_debit_card_permissions')

        assert UserServicePermission.objects.filter(service=self.service).count() == 3
        assert UserServicePermission.objects.filter(service=self.invalid_service).count() == 0
        assert UserServicePermission.objects.filter(created_at__isnull=True).count() == 0
        assert UserServicePermission.objects.filter(created_at__isnull=False).count() == 3

    @staticmethod
    def create_debit_user_service(service, user, missmatch_service=None):
        card_number = ''.join(random.choices(string.digits, k=16))
        user_service_permission, _ = UserServicePermission.objects.get_or_create(
            user=user, service=missmatch_service or service
        )
        UserService.objects.get_or_create(
            service=service,
            user=user,
            user_service_permission=user_service_permission,
            account_number=card_number,
            current_debt=0,
            initial_debt=0,
        )
