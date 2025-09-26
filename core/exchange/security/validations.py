import re

from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.api import SemanticAPIError
from exchange.accounts.functions import check_user_otp
from exchange.accounts.models import User, UserOTP
from exchange.blockchain.validators import validate_crypto_address_by_network, validate_memo_by_network


def check_enable_2fa(user: User):
    if not user.requires_2fa:
        raise SemanticAPIError(message="Inactive2FA", description="TFA is not enabled!")


def validate_otp(user: User, otp: str, otp_usage=UserOTP.OTP_Usage.address_book) -> UserOTP:
    for otp_type in (UserOTP.OTP_TYPES.mobile, UserOTP.OTP_TYPES.email):
        otp_obj, error = UserOTP.verify(code=otp, tp=otp_type, usage=otp_usage, user=user)
        if otp_obj and not error:
            return otp_obj
    raise SemanticAPIError(message="InvalidOTP", description="OTP is not valid!")


def validate_tfa(user: User, tfa: str):
    is_valid_tfa = check_user_otp(tfa, user)
    if not is_valid_tfa:
        raise SemanticAPIError(message="Invalid2FA", description="TFA is not valid!")


def validate_address(address: str, network: str):
    if not validate_crypto_address_by_network(address, network):
        raise SemanticAPIError(message='InvalidAddress', description='The address is not valid for this network!')


def validate_tag(tag: str, network: str) -> None:

    if not re.match('^[A-Za-z0-9]*$', tag):
        raise SemanticAPIError(message='InvalidTag', description='The Tag is not valid!')

    if not validate_memo_by_network(tag, network):
        raise SemanticAPIError(message='InvalidTag', description='The Tag is not valid for given network!')
