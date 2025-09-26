from exchange.base.api import NobitexAPIError


class UserLevelRestrictionAPIError(NobitexAPIError):
    def __init__(self):
        super().__init__(
            status_code=400,
            message='UserLevelRestriction',
            description='User level does not meet the requirements',
        )
