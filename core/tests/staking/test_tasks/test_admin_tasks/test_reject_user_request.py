from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import TestCase

from exchange.staking.errors import AdminMistake
from exchange.staking.tasks import reject_user_request_task
from tests.staking.utils import StakingTestDataMixin


class RejectUserRequestTaskTests(StakingTestDataMixin, TestCase):
    @patch('exchange.staking.service.reject_requests.subscription._create_reject_transaction')
    def test_task_calls_cancel_or_reject_create_request_service_for_reject_create_type(self, mocked_service):
        reject_user_request_task(user_id=1212, plan_id=3333, amount='12.45', tp='reject_create')

        mocked_service.assert_called_once_with(
            1212,
            3333,
            Decimal('12.45'),
        )

    @patch('exchange.staking.models.StakingTransaction._cancel_or_reject_end_request')
    def test_task_calls_cancel_or_reject_end_request_service_for_reject_end_type(self, mocked_service):
        reject_user_request_task(user_id=41, plan_id=4444, amount='23.5', tp='reject_end')

        mocked_service.assert_called_once_with(
            41,
            4444,
            Decimal('23.5'),
            223,
        )

    @patch('exchange.staking.models.StakingTransaction._cancel_or_reject_end_request')
    @patch('exchange.staking.service.reject_requests.subscription._create_reject_transaction')
    def test_calling_task_with_type_other_than_reject_end_or_reject_create_raises_error(
        self, mocked_create_service, mocked_end_service
    ):
        with pytest.raises(AdminMistake):
            reject_user_request_task(user_id=41, plan_id=4444, amount='23.5', tp='i_am_invalid_type_LOL')

        mocked_create_service.assert_not_called()
        mocked_end_service.assert_not_called()
