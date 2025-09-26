from exchange.direct_debit.api.exceptions import UserLevelRestrictionAPIError
from exchange.wallet.models import User


def validate_user_eligibility(user: User) -> None:
    if user.user_type < user.USER_TYPES.level1:
        raise UserLevelRestrictionAPIError()
