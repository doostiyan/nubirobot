from django.core.management import call_command
from django.test import TestCase

from exchange.accounts.models import UserRestriction
from tests.asset_backed_credit.helper import ABCMixins


class AddMobileRestrictionCommandTests(TestCase, ABCMixins):
    def setUp(self):
        self.user_service = self.create_user_service()
        self.candidate_restriction1 = UserRestriction.objects.create(
            user=self.user_service.user,
            restriction=UserRestriction.RESTRICTION.ChangeMobile,
            source='abc',
            ref_id=self.user_service.id,
            description=None,
        )
        self.candidate_restriction2 = UserRestriction.objects.create(
            user=self.create_user(),
            restriction=UserRestriction.RESTRICTION.ChangeMobile,
            source='abc',
            ref_id=30,
            description=None,
            considerations='test consideration',
        )
        self.restriction2 = UserRestriction.objects.create(
            user=self.create_user(),
            restriction=UserRestriction.RESTRICTION.ChangeMobile,
            source='not_abc',
            ref_id=10,
            description='test',
            considerations='test',
        )
        self.restriction3 = UserRestriction.objects.create(
            user=self.create_user(),
            restriction=UserRestriction.RESTRICTION.ChangeMobile,
            source='abc',
            ref_id=None,
            description=None,
        )

        self.updated_considerations = 'به دلیل فعال بودن اعتبار تارا، ‌کاربر امکان ویرایش شماره موبایل را ندارد.'
        self.updated_description = 'به دلیل فعال بودن اعتبار تارا،‌ امکان ویرایش شماره موبایل وجود ندارد.'

    def test_command_success(self):
        call_command('abc_set_tara_users_restriction_description')

        self.candidate_restriction1.refresh_from_db()
        self.candidate_restriction2.refresh_from_db()
        self.restriction2.refresh_from_db()
        self.restriction3.refresh_from_db()

        assert self.candidate_restriction1.user == self.user_service.user
        assert self.candidate_restriction1.restriction == UserRestriction.RESTRICTION.ChangeMobile
        assert self.candidate_restriction1.source == 'abc'
        assert self.candidate_restriction1.ref_id == self.user_service.id
        assert self.candidate_restriction1.considerations == self.updated_considerations
        assert self.candidate_restriction1.description == self.updated_description

        assert self.candidate_restriction2.considerations == self.updated_considerations
        assert self.candidate_restriction2.description == self.updated_description

        assert self.restriction2.restriction == UserRestriction.RESTRICTION.ChangeMobile
        assert self.restriction2.source == 'not_abc'
        assert self.restriction2.ref_id == 10
        assert self.restriction2.description == 'test'
        assert self.restriction2.considerations == 'test'

        self.restriction3.restriction = UserRestriction.RESTRICTION.ChangeMobile
        self.restriction3.source = 'abc'
        self.restriction3.ref_id = None
        self.restriction3.description = None
        self.restriction3.considerations = ''
