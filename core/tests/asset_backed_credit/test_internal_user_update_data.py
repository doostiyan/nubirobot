from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase, override_settings

from exchange.asset_backed_credit.exceptions import InternalAPIError
from exchange.asset_backed_credit.externals.user import UserProfileSchema, VerificationProfileSchema
from exchange.asset_backed_credit.models import InternalUser
from exchange.asset_backed_credit.services.user import update_internal_users_data
from exchange.base.models import Settings


class UpdateInternalUsersDataTest(TestCase):
    def setUp(self):
        Settings.set('abc_use_internal_users_update_cron', 'yes')

    @patch('exchange.asset_backed_credit.externals.user.UserProvider.get_user')
    def test_successful_update(self, mock_get_user):
        internal_user = InternalUser.objects.create(
            uid=uuid4(),
            user_type=None,
            national_code=None,
            mobile='09123456789',
            email='user@example.com',
            email_confirmed=False,
            mobile_confirmed=False,
            identity_confirmed=False,
            mobile_identity_confirmed=False,
        )
        return_value = UserProfileSchema(
            uid=internal_user.uid,
            username='test-username',
            verification_status=3,
            user_type=InternalUser.USER_TYPES.trusted,
            verification_profile=VerificationProfileSchema(
                mobile_confirmed=True, identity_confirmed=True, mobile_identity_confirmed=True, email_confirmed=True
            ),
            national_code='3080247844',
            mobile='09121111111',
            email='updateduser@example.com',
            gender=1,
            birthdate_shamsi='1401/12/12',
            requires2fa=True,
            father_name='t',
        )
        mock_get_user.return_value = return_value

        update_internal_users_data()

        internal_user.refresh_from_db()
        assert internal_user.id
        assert internal_user.user_type == InternalUser.USER_TYPES.trusted
        assert internal_user.national_code == return_value.national_code
        assert internal_user.mobile == return_value.mobile
        assert internal_user.email == return_value.email
        assert internal_user.email_confirmed
        assert internal_user.mobile_confirmed
        assert internal_user.identity_confirmed
        assert internal_user.mobile_identity_confirmed
        assert internal_user.gender == return_value.gender
        assert internal_user.father_name == return_value.father_name
        assert internal_user.requires_2fa == return_value.requires2fa
        assert internal_user.birthdate_shamsi == return_value.birthdate_shamsi

        mock_get_user.assert_called_once()

    @patch('exchange.asset_backed_credit.externals.user.UserProvider.get_user')
    def test_internal_api_error_handling(self, mock_get_user):
        internal_user = InternalUser.objects.create(
            uid=uuid4(),
            user_type=None,
            national_code=None,
            mobile='09123456789',
            email='user@example.com',
            email_confirmed=False,
            mobile_confirmed=False,
            identity_confirmed=False,
            mobile_identity_confirmed=False,
        )

        mock_get_user.side_effect = InternalAPIError("API error occurred")

        update_internal_users_data()

        internal_user.refresh_from_db()
        assert internal_user.id
        assert internal_user.user_type is None
        assert internal_user.national_code is None
        assert internal_user.mobile == '09123456789'
        assert internal_user.email == 'user@example.com'
        assert internal_user.email_confirmed == False
        assert internal_user.mobile_confirmed == False
        assert internal_user.identity_confirmed == False
        assert internal_user.mobile_identity_confirmed == False
        assert internal_user.gender == InternalUser.GenderChoices.UNKNOWN
        assert internal_user.birthdate_shamsi is None
        assert internal_user.father_name is None
        assert internal_user.requires_2fa == False
        mock_get_user.assert_called_once()

    @patch('exchange.asset_backed_credit.externals.user.UserProvider.get_user')
    def test_multiple_users_with_one_not_meeting_exclude_conditions(self, mock_get_user):
        internal_user_1 = InternalUser.objects.create(
            uid=uuid4(),
            user_type=None,
            national_code='987654321',
            mobile='09123333389',
            email_confirmed=False,
            mobile_confirmed=False,
            identity_confirmed=False,
            mobile_identity_confirmed=False,
        )

        internal_user_2 = InternalUser.objects.create(
            uid=uuid4(),
            user_type=InternalUser.USER_TYPES.level1,
            national_code='123456789',
            mobile='09122256789',
            email='olduser2@example.com',
            email_confirmed=True,
            mobile_confirmed=True,
            identity_confirmed=True,
            mobile_identity_confirmed=True,
            gender=InternalUser.GenderChoices.FEMALE,
            birthdate_shamsi='1399/12/12',
            father_name='test',
            requires_2fa=True,
        )

        internal_user_3 = InternalUser.objects.create(
            uid=uuid4(),
            user_type=None,
            national_code=None,
            mobile='09123333789',
            email='olduser3@example.com',
            email_confirmed=False,
            mobile_confirmed=False,
            identity_confirmed=False,
            mobile_identity_confirmed=False,
        )

        internal_user_1_updates = UserProfileSchema(
            uid=internal_user_1.uid,
            username='test-username',
            verification_status=3,
            user_type=InternalUser.USER_TYPES.trusted,
            verification_profile=VerificationProfileSchema(
                mobile_confirmed=True, identity_confirmed=True, mobile_identity_confirmed=True, email_confirmed=True
            ),
            national_code='3080247844',
            mobile='09121111111',
            email='updateduser1@example.com',
            gender=1,
            birthdate_shamsi='1401/12/12',
            requires2fa=True,
            father_name='t',
        )
        internal_user_3_updates = UserProfileSchema(
            uid=internal_user_3.uid,
            verification_status=3,
            username='test-username',
            user_type=InternalUser.USER_TYPES.trusted,
            verification_profile=VerificationProfileSchema(
                mobile_confirmed=True, identity_confirmed=True, mobile_identity_confirmed=True, email_confirmed=True
            ),
            national_code='3080247845',
            mobile='091211333112',
            email='updateduser3@example.com',
            gender=1,
            birthdate_shamsi='1401/12/12',
            requires2fa=True,
            father_name='t',
        )
        mock_get_user.side_effect = [internal_user_1_updates, internal_user_3_updates]

        update_internal_users_data()

        assert mock_get_user.call_count == 2

        internal_user_1.refresh_from_db()
        assert internal_user_1.id
        assert internal_user_1.user_type == internal_user_1_updates.user_type
        assert internal_user_1.national_code == internal_user_1_updates.national_code
        assert internal_user_1.mobile == internal_user_1_updates.mobile
        assert internal_user_1.email == internal_user_1_updates.email
        assert internal_user_1.email_confirmed == internal_user_1_updates.verification_profile.email_confirmed
        assert internal_user_1.mobile_confirmed == internal_user_1_updates.verification_profile.mobile_confirmed
        assert internal_user_1.identity_confirmed == internal_user_1_updates.verification_profile.identity_confirmed
        assert (
            internal_user_1.mobile_identity_confirmed
            == internal_user_1_updates.verification_profile.mobile_identity_confirmed
        )
        assert internal_user_1.gender == internal_user_1_updates.gender
        assert internal_user_1.father_name == internal_user_1_updates.father_name
        assert internal_user_1.requires_2fa == internal_user_1_updates.requires2fa
        assert internal_user_1.birthdate_shamsi == internal_user_1_updates.birthdate_shamsi

        internal_user_2.refresh_from_db()
        assert internal_user_2.id
        assert internal_user_2.user_type == InternalUser.USER_TYPES.level1
        assert internal_user_2.national_code == '123456789'
        assert internal_user_2.mobile == '09122256789'
        assert internal_user_2.email == 'olduser2@example.com'
        assert internal_user_2.email_confirmed
        assert internal_user_2.mobile_confirmed
        assert internal_user_2.identity_confirmed
        assert internal_user_2.mobile_identity_confirmed

        internal_user_3.refresh_from_db()
        internal_user_3.refresh_from_db()
        assert internal_user_3.id
        assert internal_user_3.user_type == internal_user_3_updates.user_type
        assert internal_user_3.national_code == internal_user_3_updates.national_code
        assert internal_user_3.mobile == internal_user_3_updates.mobile
        assert internal_user_3.email == internal_user_3_updates.email
        assert internal_user_3.email_confirmed == internal_user_3_updates.verification_profile.email_confirmed
        assert internal_user_3.mobile_confirmed == internal_user_3_updates.verification_profile.mobile_confirmed
        assert internal_user_3.identity_confirmed == internal_user_3_updates.verification_profile.identity_confirmed
        assert (
            internal_user_3.mobile_identity_confirmed
            == internal_user_3_updates.verification_profile.mobile_identity_confirmed
        )
        assert internal_user_3.gender == internal_user_3_updates.gender
        assert internal_user_3.father_name == internal_user_3_updates.father_name
        assert internal_user_3.requires_2fa == internal_user_3_updates.requires2fa
        assert internal_user_3.birthdate_shamsi == internal_user_3_updates.birthdate_shamsi

    @patch('exchange.asset_backed_credit.externals.user.UserProvider.get_user')
    def test_user_update_is_skipped_when_flag_is_not_enabled(self, mock_get_user):
        Settings.set('abc_use_internal_users_update_cron', 'no')

        internal_user = InternalUser.objects.create(
            uid=uuid4(),
            user_type=None,
            national_code=None,
            mobile='09123456789',
            email='user@example.com',
            email_confirmed=False,
            mobile_confirmed=False,
            identity_confirmed=False,
            mobile_identity_confirmed=False,
        )

        mock_get_user.side_effect = UserProfileSchema(
            uid=internal_user.uid,
            username='test-username',
            verification_status=3,
            user_type=InternalUser.USER_TYPES.trusted,
            verification_profile=VerificationProfileSchema(
                mobile_confirmed=True, identity_confirmed=True, mobile_identity_confirmed=True, email_confirmed=True
            ),
            national_code='3080247844',
            mobile='09121111111',
            email='updateduser1@example.com',
            gender=1,
            birthdate_shamsi='1401/12/12',
            requires2fa=True,
            father_name='t',
        )

        update_internal_users_data()

        internal_user.refresh_from_db()
        assert internal_user.id
        assert internal_user.user_type is None
        assert internal_user.national_code is None
        assert internal_user.mobile == '09123456789'
        assert internal_user.email == 'user@example.com'
        assert internal_user.email_confirmed == False
        assert internal_user.mobile_confirmed == False
        assert internal_user.identity_confirmed == False
        assert internal_user.mobile_identity_confirmed == False
        assert internal_user.gender == InternalUser.GenderChoices.UNKNOWN
        assert internal_user.birthdate_shamsi is None
        assert internal_user.father_name is None
        assert internal_user.requires_2fa == False
        mock_get_user.assert_not_called()
