class InvalidUserNameError(Exception):
    pass


class PasswordRecoveryError(Exception):
    pass


class IncompleteRegisterError(Exception):
    pass


class EmailRegistrationDisabled(Exception):
    pass


class InvalidUserError(Exception):
    pass


class SameUserError(Exception):
    pass


class IncompatibleUserLevelError(Exception):
    pass


class HasTransactionError(Exception):
    pass


class HasReferralProgramError(Exception):
    pass


class HasActiveMergeRequestError(Exception):
    pass


class CheckMobileIdentityError(Exception):
    pass


class OTPRequestError(Exception):
    pass


class OTPVerificationError(Exception):
    pass


class UserHasEmailError(Exception):
    pass


class UserRestrictionRemovalNotAllowed(Exception):
    pass


class MaxMergeRequestExceededError(Exception):
    pass
