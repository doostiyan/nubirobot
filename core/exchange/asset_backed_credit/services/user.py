from typing import Optional
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions

from exchange.accounts.models import User
from exchange.accounts.userlevels import UserLevelManager
from exchange.asset_backed_credit.exceptions import InternalAPIError
from exchange.asset_backed_credit.externals.user import UserProvider
from exchange.asset_backed_credit.models import InternalUser
from exchange.base.logging import report_event, report_exception
from exchange.base.models import Settings


def get_or_create_internal_user(user_id: UUID) -> Optional[InternalUser]:
    try:
        return InternalUser.objects.get(uid=user_id)
    except InternalUser.DoesNotExist:
        if settings.ONLY_REPLICA:
            return None
        return _create_internal_user(user_id)
    except ValidationError as e:
        raise exceptions.AuthenticationFailed(_('Invalid user_id.')) from e


def _create_internal_user(user_id: UUID):
    try:
        user_schema = UserProvider.get_user(user_id=user_id)
        return InternalUser.create(
            uid=user_schema.uid,
            user_type=user_schema.user_type,
            national_code=user_schema.national_code,
            mobile=user_schema.mobile,
            email=user_schema.email,
            email_confirmed=user_schema.verification_profile.email_confirmed,
            mobile_confirmed=user_schema.verification_profile.mobile_confirmed,
            identity_confirmed=user_schema.verification_profile.identity_confirmed,
            mobile_identity_confirmed=user_schema.verification_profile.mobile_identity_confirmed,
            gender=user_schema.gender,
            birthdate_shamsi=user_schema.birthdate_shamsi,
            father_name=user_schema.father_name,
            requires_2fa=user_schema.requires2fa,
        )
    except (InternalAPIError, User.DoesNotExist) as e:
        report_exception()
        raise exceptions.AuthenticationFailed(_('Invalid user_id.')) from e


def is_user_verified_level_one(user: User) -> bool:
    if Settings.get_flag('abc_use_internal_user_eligibility'):
        return InternalUser.objects.get(uid=user.uid).is_verified_level_1

    return UserLevelManager.is_user_verified_as_level_1(user=user)


def is_user_mobile_identity_confirmed(user: User) -> bool:
    if Settings.get_flag('abc_use_internal_user_eligibility'):
        return InternalUser.objects.get(uid=user.uid).mobile_identity_confirmed

    return UserLevelManager.is_user_mobile_identity_confirmed(user=user)


@transaction.atomic
def update_internal_users_data():

    if not Settings.get_flag('abc_use_internal_users_update_cron'):
        return

    internal_users = InternalUser.objects.exclude(
        user_type__isnull=False,
        national_code__isnull=False,
        mobile__isnull=False,
        email__isnull=False,
        email_confirmed=True,
        mobile_confirmed=True,
        identity_confirmed=True,
        mobile_identity_confirmed=True,
        gender__in=[InternalUser.GenderChoices.FEMALE, InternalUser.GenderChoices.MALE],
        birthdate_shamsi__isnull=False,
        father_name__isnull=False,
        requires_2fa=True,
    ).select_for_update(no_key=True)

    for internal_user in internal_users:
        try:
            user_schema = UserProvider.get_user(user_id=internal_user.uid)

            internal_user.user_type = user_schema.user_type
            internal_user.national_code = user_schema.national_code
            internal_user.mobile = user_schema.mobile
            internal_user.email = user_schema.email
            internal_user.email_confirmed = user_schema.verification_profile.email_confirmed
            internal_user.mobile_confirmed = user_schema.verification_profile.mobile_confirmed
            internal_user.identity_confirmed = user_schema.verification_profile.identity_confirmed
            internal_user.mobile_identity_confirmed = user_schema.verification_profile.mobile_identity_confirmed
            internal_user.gender = user_schema.gender
            internal_user.birthdate_shamsi = user_schema.birthdate_shamsi
            internal_user.father_name = user_schema.father_name
            internal_user.requires_2fa = user_schema.requires2fa
            internal_user.save()

        except (InternalAPIError, User.DoesNotExist) as e:
            report_event('Exception in updating internal user', extras={'exception': str(e)})
