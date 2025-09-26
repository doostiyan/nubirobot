import hashlib

from exchange.accounts.models import User
from exchange.base.serializers import serialize
from exchange.oauth.models import Application


def profile_info_serializer(user: User, application: Application):
    verification_profile = user.get_verification_profile()
    is_verified_email = user.email and verification_profile.email_confirmed
    is_verified_mobile = verification_profile.has_verified_mobile_number
    return {
        'userId': hashlib.sha256(f'{application.id}-{user.id}'.encode()).hexdigest(),
        'email': user.email if is_verified_email else None,
        'phoneNumber': user.mobile if is_verified_mobile else None,
    }


def user_info_serializer(user: User):
    return {
        'firstName': user.first_name,
        'lastName': user.last_name,
        'birthdate': serialize(user.birthday),
        'level': user.get_user_type_display(),
    }


def user_identity_info_serializer(user: User, application: Application):
    return {
        'userId': hashlib.sha256(f'{application.id}-{user.id}'.encode()).hexdigest(),
        'birthdate': serialize(user.birthday),
        'nationalCode': user.national_code,
    }
