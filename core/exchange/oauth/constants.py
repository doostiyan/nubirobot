from enum import Enum
from typing import Dict


class Scopes(Enum):
    PROFILE_INFO = ('profile-info', 'General profile information including user_id, email, and phone number')
    USER_INFO = ('user-info', 'General user information including name, birth date, and level')
    IDENTITY_INFO = ('identity-info', 'General identify information including user_id, birth date, national code')

    @property
    def scope(self):
        return self.value[0]

    @property
    def description(self):
        return self.value[1]

    @classmethod
    def get_all(cls) -> Dict[str, str]:
        return {item.scope: item.description for item in cls}


DEFAULT_RESPONSE_TYPE = 'code'
AVAILABLE_RESPONSE_TYPE = ['code']
