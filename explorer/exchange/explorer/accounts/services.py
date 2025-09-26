from ..authentication.models import UserAPIKey
from .dtos import UserDTOCreator
from .models import User
from ..authentication.utils.exceptions import APIKeyNotFoundException
from ..utils.cache import CacheUtils

from ..authentication.dtos.api_key import APIKeyDTOCreator


def get_user_dto(user):
    user.api_keys = list(user.user_api_keys.all())
    user_dto = UserDTOCreator.get_dto(user)
    return user_dto


def get_user_dtos():
    users = User.objects.prefetch_related('user_api_keys')
    for user in users:
        user.api_keys = list(user.user_api_keys.all())

    user_dtos = UserDTOCreator.get_dtos(users)
    return user_dtos


def create_user():
    pass


def get_api_keys_dto(revoked=False):
    api_keys = UserAPIKey.objects.filter(revoked=revoked)
    api_keys_dtos = APIKeyDTOCreator.get_dto(api_keys)
    return api_keys_dtos


def delete_api_key(prefix):
    try:
        api_key = UserAPIKey.objects.load_api_key_by_prefix(prefix=prefix)
        if not api_key.has_expired:
            api_key.revoked = True
        else:
            raise APIKeyNotFoundException
        CacheUtils.write_to_external_cache(prefix, api_key, 'redis__user_api_keys')
        CacheUtils.write_to_local_cache(prefix, api_key, 'local__user_api_keys')
        api_key.save()

    except UserAPIKey.DoesNotExist:
        raise APIKeyNotFoundException
