from django.core.management import call_command
from django.test import TestCase

from exchange.accounts.models import UserRestriction
from exchange.asset_backed_credit.models import Service
from exchange.base.calendar import ir_now
from tests.asset_backed_credit.helper import ABCMixins


class AddMobileRestrictionCommandTests(TestCase, ABCMixins):
    def setUp(self):
        self.user_with_active_tara = self.create_user()
        self.user_with_closed_tara = self.create_user()
        self.tara_service = self.create_service(Service.PROVIDERS.tara)
        self.user_active_tara_service = self.create_user_service(self.user_with_active_tara, service=self.tara_service)
        self.create_user_service(self.user_with_closed_tara, service=self.tara_service, closed_at=ir_now())

    def test_command_success(self):
        assert UserRestriction.objects.filter(user=self.user_with_active_tara).count() == 0
        assert UserRestriction.objects.filter(user=self.user_with_closed_tara).count() == 0

        call_command('abc_add_change_mobile_restriction_to_tara_users')

        assert UserRestriction.objects.filter(user=self.user_with_closed_tara).count() == 0
        user_restriction = UserRestriction.objects.get(
            user=self.user_with_active_tara,
            restriction=UserRestriction.RESTRICTION.ChangeMobile,
            source='abc',
            ref_id=self.user_active_tara_service.id,
        )
        assert user_restriction
        assert user_restriction.considerations is not None
