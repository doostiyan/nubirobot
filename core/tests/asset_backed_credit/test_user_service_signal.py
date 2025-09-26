from unittest.mock import patch

from django.test import TestCase

from exchange.asset_backed_credit.externals.restriction import UserRestrictionType
from exchange.asset_backed_credit.models import Service, UserService
from tests.asset_backed_credit.helper import ABCMixins


class UserServicePostSaveSignalTests(ABCMixins, TestCase):
    @patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_remove_change_mobile_restriction_not_called_on_none_tara_services(self, mock_restriction_task):
        self.create_user_service(service=self.create_service(provider=Service.PROVIDERS.vency))
        mock_restriction_task.assert_not_called()

    @patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_remove_change_mobile_restriction_not_called_on_tara_services_with_not_finished_status(
        self, mock_restriction_task
    ):
        self.create_user_service(service=self.create_service(provider=Service.PROVIDERS.tara))
        mock_restriction_task.assert_not_called()

    @patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_remove_change_mobile_restriction_is_called_on_tara_services_that_are_settled(self, mock_restriction_task):
        user_service = self.create_user_service(service=self.create_service(provider=Service.PROVIDERS.tara))
        user_service.status = UserService.STATUS.settled
        user_service.save()

        mock_restriction_task.assert_called_once_with(
            user_service_id=user_service.id, restriction=UserRestrictionType.CHANGE_MOBILE.value
        )

    @patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_remove_change_mobile_restriction_is_called_on_tara_services_that_are_closed(self, mock_restriction_task):
        user_service = self.create_user_service(service=self.create_service(provider=Service.PROVIDERS.tara))
        user_service.status = UserService.STATUS.closed
        user_service.save()

        mock_restriction_task.assert_called_once_with(
            user_service_id=user_service.id, restriction=UserRestrictionType.CHANGE_MOBILE.value
        )
