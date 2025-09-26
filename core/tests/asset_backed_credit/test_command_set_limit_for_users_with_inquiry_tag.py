from decimal import Decimal

from django.test import TestCase

from exchange.accounts.models import Tag, User, UserTag
from exchange.asset_backed_credit.crons import ABCUpdateUserFinancialServiceLimitCron
from exchange.asset_backed_credit.models import UserFinancialServiceLimit


class TestABCUpdateUserFinancialServiceLimitCron(TestCase):
    def setUp(self):
        self.tag, _ = Tag.objects.get_or_create(name='استعلام')
        other_tag, _ = Tag.objects.get_or_create(name='دیگری')
        self.user1 = User.objects.create_user(username='john-doe')
        self.user2 = User.objects.create_user(username='jane-doe')
        self.user3 = User.objects.create_user(username='joe-doe')
        self.user4 = User.objects.create_user(username='jim-doe')
        UserTag.objects.create(tag=self.tag, user=self.user1)
        UserTag.objects.create(tag=other_tag, user=self.user2)
        UserTag.objects.create(tag=self.tag, user=self.user4)

    def test_cron(self):
        ABCUpdateUserFinancialServiceLimitCron().run()
        limit_type = UserFinancialServiceLimit.TYPES.user
        assert UserFinancialServiceLimit.objects.get(user=self.user1, tp=limit_type, limit=Decimal(0))
        assert UserFinancialServiceLimit.objects.filter(user=self.user2).count() == 0
        assert UserFinancialServiceLimit.objects.filter(user=self.user3).count() == 0

        UserTag.objects.filter(user=self.user1, tag=self.tag).delete()
        ABCUpdateUserFinancialServiceLimitCron().run()
        assert not UserFinancialServiceLimit.objects.filter(user=self.user1, tp=limit_type, limit=Decimal(0)).exists()
        assert UserFinancialServiceLimit.objects.filter(user=self.user4, tp=limit_type, limit=Decimal(0)).exists()
