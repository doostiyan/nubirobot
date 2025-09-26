import re
from typing import Any, Union

from django.db import connection

from exchange.accounts.models import User, UserProfile


class UserProfileManager:
    @classmethod
    def get_user_property(cls, user: Union[int, User], key: str) -> Any:
        '''Get a property value from user profile.'''
        user_id = user if isinstance(user, int) else user.id
        return UserProfile.objects.filter(user_ptr_id=user_id).values_list(f'properties__{key}', flat=True).first()

    @classmethod
    def set_user_property(cls, user: Union[int, User], key: str, value: Union[str, int]) -> None:
        '''Set a key value in properties JSON field of UserProfile.

            This method uses INSERT with an ON CONFLICT condition instead of a simple UPDATE to prevent
            updating rows with unchanged values and causing dead tuples in DB because of MVCC.
            See: https://dba.stackexchange.com/a/118214/15645
        '''
        if isinstance(value, int):
            value_str = str(value)
        elif isinstance(value, str):
            value_str = f'"{value}"'
        else:
            raise ValueError('Invalid value type')
        if isinstance(user, int):
            user_id = user
        elif isinstance(user.id, int):
            user_id = user.id
        else:
            raise ValueError('Invalid user type')

        with connection.cursor() as cursor:
            # Notice: here we pass some parameters inside query string because of inlined json
            #  objects where " should be used instead of '. Any variables passed to this
            #  query must be type-checked explicitly to prevent SQL injection attacks.
            cursor.execute(
                f"INSERT INTO accounts_userprofile (user_ptr_id, properties)"
                f" VALUES (%s, '{{\"{key}\": {value_str}}}'::jsonb)"
                f" ON CONFLICT (user_ptr_id) DO UPDATE"
                f" SET properties = jsonb_set( accounts_userprofile.properties, '{{{key}}}', '{value_str}' )"
                f" WHERE accounts_userprofile.properties->'{{{key}}}' IS DISTINCT FROM '{value_str}'",
                [user_id],
            )

    @classmethod
    def _parse_client_params(cls, user, client, version):
        if isinstance(user, int):
            user_id = user
        else:
            user_id = user.id
        if client in ['android', 'Android']:
            client_key = 'vA'
        elif client in ['ios', 'iOSApp']:
            client_key = 'vI'
        else:
            client_key = None
        if version is None:
            version_int = None
        elif isinstance(version, str):
            try:
                version_int = int(version.replace('.', ''))
                if 0 < version_int < 100:
                    version_int *= 10
            except ValueError:
                version_int = None
        else:
            version_int = int(version)
        return user_id, client_key, version_int

    @classmethod
    def get_client_version(cls, user, client):
        '''Get client version from user profile.'''
        user_id, client_key, _ = cls._parse_client_params(user, client, None)
        if not user_id or not client_key:
            return None
        return cls.get_user_property(user_id, client_key)

    @classmethod
    def set_client_version(cls, user, client, version):
        '''Set client version in user profile.'''
        user_id, client_key, version_int = cls._parse_client_params(user, client, version)
        if not user_id or not client_key or not version_int:
            return False
        cls.set_user_property(user_id, client_key, version_int)
        return True

    @classmethod
    def set_client_version_from_ua(cls, user, ua):
        '''Set client version in user profile using a User Agent.'''
        ua = ua or ''
        m = re.match(r'(Android|iOSApp)/([0-9.]+)', ua)
        if not m:
            return False
        client, version = m.groups()
        return cls.set_client_version(user, client, version)
