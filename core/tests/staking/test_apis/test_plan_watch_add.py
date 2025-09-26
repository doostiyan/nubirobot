from django.test import TestCase
from rest_framework import status

from exchange.accounts.models import User, VerificationProfile
from exchange.staking.models import Plan, UserWatch
from tests.staking.utils import PlanTestDataMixin


class UserWatchAddAPITests(PlanTestDataMixin, TestCase):
    URL = '/earn/plan/watch/add'

    def setUp(self) -> None:
        self.plan = self.create_plan(**self.get_plan_kwargs())

        self.user = User.objects.get(pk=201)
        self.user.user_type = User.USER_TYPES.level2
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(email_confirmed=True)
        self.user.save()
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.user.auth_token.key}'

    def test_watch_plan_successfully_when_user_watches_plan_for_first_time(self):
        data = {
            'planId': self.plan.id,
        }
        response = self.client.post(self.URL, data=data)

        assert response.status_code == status.HTTP_200_OK
        assert UserWatch.objects.get(plan=self.plan, user=self.user)

    def test_watch_plan_with_no_errors_when_user_has_already_watched_it(self):
        UserWatch.objects.create(user=self.user, plan=self.plan)

        data = {
            'planId': self.plan.id,
        }
        response = self.client.post(self.URL, data=data)

        assert response.status_code == status.HTTP_200_OK
        assert UserWatch.objects.get(plan=self.plan, user=self.user)

    def test_watch_plan_fails_when_no_such_plan_exists(self):
        not_existing_plan_id = Plan.objects.last().id + 1000
        data = {
            'planId': not_existing_plan_id,
        }
        response = self.client.post(self.URL, data=data)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert UserWatch.objects.filter(plan_id=not_existing_plan_id, user=self.user).first() is None
