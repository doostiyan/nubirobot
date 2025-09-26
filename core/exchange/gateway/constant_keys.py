from django.utils.translation import gettext as _

#######################
# Gateway invoice error code
#######################

# API
API_REQUIRED = {'code': '-1', 'message': _('API parameter is required.')}
API_NOT_FOUND = {'code': '-2', 'message': _('API not found.')}
API_RESTRICTED = {'code': '-3', 'message': _('API is restricted.')}
API_INVALID = {'code': '-4', 'message': _('API is invalid.')}

# Amount
AMOUNT_INT = {'code': '-6', 'message': _('Amount must be integer.')}
AMOUNT_MIN = {'code': '-7', 'message': _('Amount min value is 500,000 rls.')}
AMOUNT_MAX = {'code': '-12', 'message': _('Amount max value is 500,000,000 rls.')}
USD_AMOUNT_INT = {'code': '-14', 'message': _('USDAmount must be integer.')}
USD_AMOUNT_MIN = {'code': '-15', 'message': _('USDAmount min value is 11 usd.')}
USD_AMOUNT_MAX = {'code': '-16', 'message': _('USDAmount max value is 5,000 usd.')}
AMOUNT_REQUIRED = {'code': '-5', 'message': _('One of the amount fields must have a value.')}
DUPLICATED_AMOUNT = {'code': '-13', 'message': _('Duplicated amount.')}

# Return URL
REDIRECT_REQUIRED = {'code': '-8', 'message': _('callbackURL parameter is required.')}
REDIRECT_BAD_DOMAIN = {'code': '-9', 'message': _('DomainError: callbackURL is different from saved domain for your API user.')}
REDIRECT_FORMAT = {'code': '-10',
                   'message': _('callbackURL format is invalid. Please use this format: https://domain.com/path/to/redirect')}

# Description
DESCRIPTION_LENGTH = {'code': '-11', 'message': _('Description must be less than 255 character.')}

# General Failed
FAILED_ERROR = {'code': '-100', 'message': _('Transaction raises error.')}

#######################
# Gateway get data error code
#######################

TOKEN_INVALID = {'code': '-21', 'message': _('Invalid token.')}
TOKEN_NOT_FOUND = {'code': '-22', 'message': _('Token not found.')}
TOKEN_REQUIRED = {'code': '-23', 'message': _('Token is required.')}


#######################
# Gateway verify error code
#######################

UNVERIFIED = {'code': '-31', 'message': _('Unverified.')}
VERIFIED_BEFORE = {'code': '-32', 'message': _('Verified before.')}

#######################
# Gateway refund error code
#######################
CURRENCY_INVALID = {'code': '-41', 'message': _('Invalid currency.')}
REFUND_INVALID = {'code': '-42', 'message': _('Invalid refund request.')}
EMAIL_INVALID = {'code': '-43', 'message': _('Invalid email address.')}

#######################
# Gateway creation error code
#######################
DOMAIN_INVALID = {'code': 'InvalidDomain', 'message': _('Invalid domain.')}
SITENAME_INVALID = {'code': 'InvalidSiteName', 'message': _('Invalid site name.')}

#######################
# Gateway withdraw error code
#######################
WITHDRAW_UNAVAILABLE = {'code': 'WithdrawUnavailable', 'message': _('Withdraw Unavailable.')}
INVALID_2FA = {'code': 'Invalid2FA', 'message': _('Invalid 2FA')}
WITHDRAW_AMOUNT_LIMITATION = {'code': 'WithdrawAmountLimitation', 'message': _('Withdraw Amount Limitation')}
INSUFFICIENT_BALANCE = {'code': 'InsufficientBalance', 'message': _('Insufficient Balance')}
WITHDRAW_LIMIT_REACHED = {'code': 'WithdrawLimitReached', 'message': _('Withdraw Limit Reached.')}
AMOUNT_TOO_LOW = {'code': 'AmountTooLow', 'message': _('Amount Too Low.')}
AMOUNT_TOO_HIGH = {'code': 'AmountTooHigh', 'message': _('Amount Too High')}
