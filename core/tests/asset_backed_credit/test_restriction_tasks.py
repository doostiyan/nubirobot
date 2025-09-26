from unittest import TestCase
from unittest.mock import patch

from exchange.asset_backed_credit.externals.restriction import UserRestrictionType
from exchange.asset_backed_credit.tasks import add_user_restriction_task, remove_user_restriction_task
from tests.asset_backed_credit.helper import ABCMixins


class AddRestrictionTaskTests(TestCase, ABCMixins):
    def setUp(self):
        self.user_service = self.create_user_service()
        self.restriction = UserRestrictionType.CHANGE_MOBILE.value

    @patch('exchange.asset_backed_credit.externals.restriction.UserRestrictionProvider.add_restriction')
    def test_add_restriction_task_success(self, mock_restriction_provider):
        add_user_restriction_task.apply(
            kwargs={
                'user_service_id': self.user_service.id,
                'restriction': self.restriction,
                'description_key': 'ACTIVE_TARA_CREDIT',
                'considerations': 'test considerations',
            }
        )

        mock_restriction_provider.assert_called_once_with(
            user_service=self.user_service,
            restriction=self.restriction,
            description_key='ACTIVE_TARA_CREDIT',
            considerations='test considerations',
        )

    @patch('exchange.asset_backed_credit.externals.restriction.UserRestrictionProvider.add_restriction')
    @patch.object(add_user_restriction_task, 'retry')
    def test_add_restriction_task_retries_after_fails(self, mock_retry, mock_restriction_provider):
        mock_restriction_provider.side_effect = Exception()

        add_user_restriction_task.apply(
            kwargs={
                'user_service_id': self.user_service.id,
                'restriction': self.restriction,
                'description_key': 'ACTIVE_TARA_CREDIT',
                'considerations': 'test considerations',
            }
        )

        mock_retry.assert_called_once()
        assert mock_restriction_provider.call_count == 1
        mock_restriction_provider.assert_called_once_with(
            user_service=self.user_service,
            restriction=self.restriction,
            description_key='ACTIVE_TARA_CREDIT',
            considerations='test considerations',
        )


class RemoveRestrictionTaskTests(TestCase, ABCMixins):
    def setUp(self):
        self.user_service = self.create_user_service()
        self.restriction = UserRestrictionType.CHANGE_MOBILE.value

    @patch('exchange.asset_backed_credit.externals.restriction.UserRestrictionProvider.remove_restriction')
    def test_remove_restriction_task_success(self, mock_restriction_provider):
        remove_user_restriction_task.apply(
            kwargs={'user_service_id': self.user_service.id, 'restriction': self.restriction}
        )

        mock_restriction_provider.assert_called_once_with(self.user_service, self.restriction)

    @patch('exchange.asset_backed_credit.externals.restriction.UserRestrictionProvider.remove_restriction')
    @patch.object(remove_user_restriction_task, 'retry')
    def test_remove_restriction_task_retries_after_fails(self, mock_retry, mock_restriction_provider):
        mock_restriction_provider.side_effect = Exception()

        remove_user_restriction_task.apply(
            kwargs={'user_service_id': self.user_service.id, 'restriction': self.restriction}
        )

        mock_retry.assert_called_once()
        assert mock_restriction_provider.call_count == 1
