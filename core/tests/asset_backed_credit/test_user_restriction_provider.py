from unittest import TestCase
from unittest.mock import patch

from exchange.accounts.models import UserRestriction
from exchange.asset_backed_credit.externals.restriction import (
    UserAddRestrictionRequest,
    UserRemoveRestrictionRequest,
    UserRestrictionProvider,
    UserRestrictionType,
)
from exchange.base.internal.services import Services
from exchange.base.models import Settings
from tests.asset_backed_credit.helper import ABCMixins


class UserRestrictionProviderTest(TestCase, ABCMixins):
    def setUp(self):
        self.user_service = self.create_user_service()
        self.restriction = UserRestrictionType.CHANGE_MOBILE.value

    def test_add_restriction_success_when_internal_api_is_not_enabled(self):
        UserRestrictionProvider().add_restriction(
            self.user_service,
            self.restriction,
            description_key='ACTIVE_TARA_CREDIT',
            considerations='considerations test',
        )

        restriction = UserRestriction.objects.filter(
            user=self.user_service.user,
            restriction=UserRestrictionType.get_db_value(self.restriction),
            source=Services.ABC,
            ref_id=self.user_service.id,
        ).first()
        assert restriction
        assert restriction.description == 'به دلیل فعال بودن اعتبار تارا،‌ امکان ویرایش شماره موبایل وجود ندارد.'
        assert restriction.considerations == 'considerations test'

    def test_add_restriction_success_when_internal_api_is_not_enabled_and_user_has_such_restriction_then_no_error_is_raised(
        self,
    ):
        UserRestriction.objects.create(
            user=self.user_service.user,
            restriction=UserRestrictionType.get_db_value(self.restriction),
            source=Services.ABC,
            ref_id=self.user_service.id,
            description='test 2 description',
            considerations='test 2 considerations',
        )

        UserRestrictionProvider().add_restriction(
            self.user_service,
            self.restriction,
            description_key='ACTIVE_TARA_CREDIT',
            considerations='test considerations',
        )

        restriction = UserRestriction.objects.filter(
            user=self.user_service.user,
            restriction=UserRestrictionType.get_db_value(self.restriction),
            source=Services.ABC,
            ref_id=self.user_service.id,
        ).first()
        assert restriction
        assert restriction.description == 'test 2 description'
        assert restriction.considerations == 'test 2 considerations'

    @patch('exchange.asset_backed_credit.externals.restriction.UserAddRestrictionAPI.request')
    def test_add_restriction_success_when_internal_api_is_enabled(self, mock_api):
        Settings.set('abc_use_restriction_internal_api', 'yes')
        UserRestrictionProvider().add_restriction(
            self.user_service,
            self.restriction,
            description_key='ACTIVE_TARA_CREDIT',
            considerations='test considerations',
        )

        assert mock_api.call_count == 1
        mock_api.assert_called_once_with(
            user_id=self.user_service.user.uid,
            data=UserAddRestrictionRequest(
                restriction=self.restriction,
                ref_id=self.user_service.id,
                description='ACTIVE_TARA_CREDIT',
                considerations='test considerations',
            ),
            idempotency=self.user_service.external_id,
        )

    @patch('exchange.asset_backed_credit.externals.restriction.UserRemoveRestrictionAPI.request')
    def test_remove_restriction_success_with_internal_api_is_enabled(self, mock_api):
        Settings.set('abc_use_restriction_internal_api', 'yes')
        UserRestrictionProvider().remove_restriction(self.user_service, self.restriction)

        assert mock_api.call_count == 1
        mock_api.assert_called_once_with(
            user_id=self.user_service.user.uid,
            data=UserRemoveRestrictionRequest(restriction=self.restriction, ref_id=self.user_service.id),
            idempotency=self.user_service.external_id,
        )

    def test_remove_restriction_success_when_internal_api_is_not_enabled(self):
        UserRestriction.objects.create(
            user=self.user_service.user,
            restriction=UserRestrictionType.get_db_value(self.restriction),
            source=Services.ABC,
            ref_id=self.user_service.id,
        )

        UserRestrictionProvider().remove_restriction(self.user_service, self.restriction)

        assert (
            UserRestriction.objects.filter(
                user=self.user_service.user,
                restriction=UserRestrictionType.get_db_value(self.restriction),
                source=Services.ABC,
                ref_id=self.user_service.id,
            ).first()
            is None
        )

    def test_remove_restriction_success_when_internal_api_is_not_enabled_and_user_has_no_such_restriction_then_no_error_is_raised(
        self,
    ):
        UserRestrictionProvider().remove_restriction(self.user_service, self.restriction)
