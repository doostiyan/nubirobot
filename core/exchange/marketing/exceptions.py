class InvalidUserIDException(Exception):
    pass


class InvalidOTPException(Exception):
    pass


class InvalidCampaignException(Exception):
    pass


class NoDiscountCodeIsAvailable(Exception):
    pass


class MissionHasNotBeenCompleted(Exception):
    pass


class RewardHasBeenAlreadyAssigned(Exception):
    pass
