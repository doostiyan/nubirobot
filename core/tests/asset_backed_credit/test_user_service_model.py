from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import TestCase

from exchange.asset_backed_credit.exceptions import AmountIsLargerThanDebtOnUpdateUserService, UpdateClosedUserService
from exchange.asset_backed_credit.models.user_service import DebtChangeLog, UserService
from exchange.base.calendar import ir_now
from exchange.base.money import money_is_zero
from tests.asset_backed_credit.helper import ABCMixins


class UserServiceListAPITest(ABCMixins, TestCase):
    def setUp(self):
        self.user_service = self.create_user_service()

    def assert_current_debt(self, user_service: UserService, new_debt: Decimal, amount: Decimal):
        user_service.refresh_from_db()
        user_service.user_service_permission.refresh_from_db()
        debt_changelog = DebtChangeLog.objects.order_by('-created_at').first()

        assert user_service.current_debt == new_debt
        assert user_service.closed_at is None
        assert user_service.user_service_permission.revoked_at is None

        assert debt_changelog.user_service == user_service
        assert debt_changelog.amount == amount

    @patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_update_debt_and_finalize(self, mock_restriction_task):
        amount = -self.user_service.current_debt + 1
        self.user_service.update_current_debt(amount)
        self.assert_current_debt(self.user_service, new_debt=Decimal(1), amount=amount)
        self.user_service.finalize(UserService.STATUS.settled)
        assert self.user_service.closed_at is None
        assert self.user_service.user_service_permission.revoked_at is None

        self.user_service.update_current_debt(Decimal(-1))
        self.assert_current_debt(self.user_service, Decimal(0), amount=-1)
        self.user_service.finalize(UserService.STATUS.settled)
        assert money_is_zero(self.user_service.current_debt)
        assert self.user_service.closed_at is not None
        assert self.user_service.user_service_permission.revoked_at is not None

        with pytest.raises(UpdateClosedUserService):
            self.user_service.update_current_debt(Decimal(-1))
        mock_restriction_task.assert_called_once()

    def test_update_debt_to_negative_value(self):
        with pytest.raises(AmountIsLargerThanDebtOnUpdateUserService):
            self.user_service.update_current_debt(-self.user_service.current_debt - 1)

    def test_debt_change_created(self):
        user_service = self.create_user_service()
        assert user_service.debt_change_logs.count() == 2
        debt_change_log = user_service.debt_change_logs.filter(type=DebtChangeLog.TYPE.initial_debt).first()
        assert debt_change_log.amount == user_service.initial_debt
        assert debt_change_log.created_at is not None
        debt_change_log = user_service.debt_change_logs.filter(type=DebtChangeLog.TYPE.current_debt).first()
        assert debt_change_log.amount == user_service.initial_debt
        assert debt_change_log.created_at is not None

    @patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_debt_change_on_update_current_debt(self, mock_restriction_task):
        self.user_service.update_current_debt(-self.user_service.current_debt + 1)
        assert self.user_service.current_debt == 1
        assert self.user_service.debt_change_logs.count() == 3
        debt_change_log = self.user_service.debt_change_logs.order_by('-created_at').first()
        assert debt_change_log.amount == -self.user_service.initial_debt + 1
        assert debt_change_log.created_at is not None

        # make current debt zero and finalize the settlement
        self.user_service.update_current_debt(-1)
        assert self.user_service.current_debt == 0
        assert self.user_service.debt_change_logs.count() == 4
        debt_change_log = self.user_service.debt_change_logs.order_by('-created_at').first()
        assert debt_change_log.amount == -1
        assert debt_change_log.created_at is not None

        self.user_service.refresh_from_db()
        assert self.user_service.closed_at is None
        assert self.user_service.current_debt == 0

        self.user_service.finalize(UserService.STATUS.settled)
        self.user_service.refresh_from_db()
        assert self.user_service.closed_at is not None
        assert self.user_service.current_debt == 0
        mock_restriction_task.assert_called_once()

    @patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_debt_change_on_update_initial_debt(self, mock_restriction_task):
        initial_debt = self.user_service.initial_debt
        self.user_service.update_debt(-self.user_service.current_debt + 1)
        assert self.user_service.initial_debt == 1
        assert self.user_service.current_debt == 1
        assert self.user_service.debt_change_logs.count() == 4
        debt_change_log = (
            self.user_service.debt_change_logs.filter(type=DebtChangeLog.TYPE.initial_debt)
            .order_by('-created_at')
            .first()
        )
        assert debt_change_log.amount == -initial_debt + 1
        assert debt_change_log.created_at is not None
        debt_change_log = (
            self.user_service.debt_change_logs.filter(type=DebtChangeLog.TYPE.current_debt)
            .order_by('-created_at')
            .first()
        )
        assert debt_change_log.amount == -initial_debt + 1
        assert debt_change_log.created_at is not None

        # make initial and current debt zero and finalize the settlement
        self.user_service.update_debt(-1)
        assert self.user_service.initial_debt == 0
        assert self.user_service.current_debt == 0
        assert self.user_service.debt_change_logs.count() == 6
        debt_change_log = (
            self.user_service.debt_change_logs.filter(type=DebtChangeLog.TYPE.initial_debt)
            .order_by('-created_at')
            .first()
        )
        assert debt_change_log.amount == -1
        assert debt_change_log.created_at is not None
        debt_change_log = (
            self.user_service.debt_change_logs.filter(type=DebtChangeLog.TYPE.current_debt)
            .order_by('-created_at')
            .first()
        )
        assert debt_change_log.amount == -1
        assert debt_change_log.created_at is not None

        self.user_service.refresh_from_db()
        assert self.user_service.closed_at is None
        assert self.user_service.current_debt == 0

        self.user_service.finalize(UserService.STATUS.settled)
        self.user_service.refresh_from_db()
        assert self.user_service.closed_at is not None
        assert self.user_service.current_debt == 0
        mock_restriction_task.assert_called_once()

    def test_debt_change_on_non_related_changes(self):
        self.user_service.debt_change_logs.all().delete()

        self.user_service.closed_at = ir_now()
        self.user_service.save()

        assert self.user_service.debt_change_logs.count() == 0
