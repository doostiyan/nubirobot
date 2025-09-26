"""Staking User Watch Tests"""
import datetime

from django.test import TestCase

from exchange.accounts.models import Notification
from exchange.staking.crons import UserWatchCron
from exchange.staking.models import Plan, UserWatch
from tests.staking.utils import PlanTestDataMixin


class UserWatchCronTest(PlanTestDataMixin, TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        Notification.objects.all().delete()
        cls.plan.filled_capacity = cls.plan.total_capacity
        cls.plan.save(update_fields=('filled_capacity',))

    @classmethod
    def extend_plan(cls, plan: Plan):
        plan_kwargs = cls.get_plan_kwargs()
        plan_kwargs['external_platform'] = plan.external_platform
        plan_kwargs['staking_period'] = plan.staking_period
        plan_kwargs['staked_at'] = plan.staked_at + plan.staking_period
        plan_kwargs['extended_from'] = plan
        return Plan.objects.create(**plan_kwargs)

    @staticmethod
    def run_cron():
        UserWatchCron().run()

    def test_user_watch_when_capacity_is_free(self):
        UserWatch.objects.create(plan=self.plan, user=self.user)

        self.plan.filled_capacity -= 10
        self.plan.save(update_fields=('filled_capacity',))
        self.run_cron()

        assert not UserWatch.objects.exists()
        notification = Notification.objects.last()
        assert notification

    def test_user_watch_before_stake_when_capacity_is_full(self):
        self.plan.staked_at += datetime.timedelta(days=1)
        self.plan.save(update_fields=('staked_at',))
        watch = UserWatch.objects.create(plan=self.plan, user=self.user)

        self.run_cron()

        watch.refresh_from_db()
        assert watch
        assert not Notification.objects.exists()

    def test_user_watch_after_close_when_plan_has_not_extended(self):
        UserWatch.objects.create(plan=self.plan, user=self.user)
        self.plan.staked_at -= datetime.timedelta(days=1)
        self.plan.save(update_fields=('staked_at',))

        self.run_cron()

        assert not UserWatch.objects.exists()
        assert not Notification.objects.exists()

    def test_user_watch_after_stake_when_plan_is_extended_and_capacity_is_free(self):
        UserWatch.objects.create(plan=self.plan, user=self.user)
        self.extend_plan(self.plan)

        self.run_cron()

        assert not UserWatch.objects.exists()
        notification = Notification.objects.last()
        assert notification

    def test_user_watch_after_stake_when_plan_is_extended_but_capacity_is_full(self):
        watch = UserWatch.objects.create(plan=self.plan, user=self.user)
        plan = self.extend_plan(self.plan)
        plan.filled_capacity = plan.total_capacity
        plan.save(update_fields=('filled_capacity',))

        self.run_cron()

        watch.refresh_from_db()
        assert watch
        assert watch.plan != self.plan
        assert watch.plan.extended_from == self.plan
        assert not Notification.objects.exists()
