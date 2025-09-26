import dataclasses
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exchange.accounts.models import User


@dataclasses.dataclass
class UserData:
    """
    Save user data
    """
    email: str
    is_email_confirmed: bool
    mobile: str
    is_mobile_confirmed: bool

    @classmethod
    def from_user(cls, user: 'User') -> 'UserData':
        return cls(
            email=user.email,
            is_email_confirmed=user.is_email_verified,
            mobile=user.mobile,
            is_mobile_confirmed=user.has_verified_mobile_number,
        )


@dataclasses.dataclass
class MergeRequestStatusChangedContext:
    """
    Save users data before merge.

    Attributes:
    - main_user: has main user data with the UserData class.
    - second_user: has second user data with the UserData class.

    Property:
    - json: returns main and second users data with json format

    """

    main_user: UserData
    second_user: UserData

    @classmethod
    def from_users(cls, main_user: 'User', second_user: 'User') -> 'MergeRequestStatusChangedContext':
        return cls(main_user=UserData.from_user(main_user), second_user=UserData.from_user(second_user))

    @property
    def json(self):
        return json.dumps(dataclasses.asdict(self))
