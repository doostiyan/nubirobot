from datetime import datetime
from typing import Optional

from exchange.web_engage.events.base import WebEngageKnownUserEvent
from exchange.web_engage.tasks import task_send_user_referral_data_to_web_engage


class SignUpWebEngageEvent(WebEngageKnownUserEvent):
    """
    This event is for sign up user that it doesn't matter if the
     mobile number or email is verified.
    """

    event_name = 'sign_up'

    def __init__(self, user, with_mobile: bool, event_time: Optional[datetime] = None,
                 device_kind: Optional[str] = None):
        super().__init__(user, event_time, device_kind)
        self.with_mobile = with_mobile

    def _get_data(self) -> dict:
        return {
            'hashedPhone': self.user.get_webengage_id() if self.user.has_verified_mobile_number else None,
            'hashedEmail': self.user.get_webengage_id() if self.user.is_email_verified else None,
            'with_mobile': self.with_mobile,
        }


class SignUpAndVerifiedWebEngageEvent(WebEngageKnownUserEvent):
    """
    This event is for sign up user that must be verified mobile number and email.
    """

    event_name = 'sign_up_verified'

    def __init__(self, user, with_mobile: bool, event_time: Optional[datetime] = None,
                 device_kind: Optional[str] = None):
        super().__init__(user, event_time, device_kind)
        self.with_mobile = with_mobile

    def _get_data(self) -> dict:
        return {
            'hashedPhone': self.user.get_webengage_id() if self.user.has_verified_mobile_number else None,
            'hashedEmail': self.user.get_webengage_id() if self.user.is_email_verified else None,
            'with_mobile': self.with_mobile,
        }


class EmailVerifiedWebEngageEvent(WebEngageKnownUserEvent):
    event_name = "email_verified"

    def _get_data(self) -> dict:
        return dict()


class MobileVerifiedWebEngageEvent(WebEngageKnownUserEvent):
    event_name = "mobile_verified"

    def __init__(self, user, edited: bool, event_time: Optional[datetime] = None,
                 device_kind: Optional[str] = None):
        super().__init__(user, event_time, device_kind)
        self.edited = edited

    def _get_data(self) -> dict:
        return {"edited": self.edited}


class MobileEnteredWebEngageEvent(WebEngageKnownUserEvent):
    event_name = "mobile_entered"

    def _get_data(self) -> dict:
        return dict()


class TelephoneVerifiedWebEngageEvent(WebEngageKnownUserEvent):
    event_name = "telephone_verified"

    def _get_data(self) -> dict:
        return dict()


class BankCardVerifiedWebEngageEvent(WebEngageKnownUserEvent):
    event_name = "bank_card_verified"

    def _get_data(self) -> dict:
        return dict()


class BankAccountVerifiedWebEngageEvent(WebEngageKnownUserEvent):
    event_name = "bank_account_verified"

    def _get_data(self) -> dict:
        return dict()


class Level2VerifiedWebEngageEvent(WebEngageKnownUserEvent):
    event_name = "level_2_verified"

    def _get_data(self) -> dict:
        return dict()


class Level1VerifiedWebEngageEvent(WebEngageKnownUserEvent):
    event_name = "level_1_verified"

    def _get_data(self) -> dict:
        return dict()


class Level3VerifiedWebEngageEvent(WebEngageKnownUserEvent):
    event_name = "level_3_verified"

    def _get_data(self) -> dict:
        return dict()


class IdentityConfirmedWebEngageEvent(WebEngageKnownUserEvent):
    event_name = "identity_vr_confirmed"

    def _get_data(self) -> dict:
        return dict()


class SelfieConfirmedWebEngageEvent(WebEngageKnownUserEvent):
    event_name = "selfie_vr_confirmed"

    def _get_data(self) -> dict:
        return dict()


class AutoKycConfirmedWebEngageEvent(WebEngageKnownUserEvent):
    event_name = "auto_kyc_vr_confirmed"

    def _get_data(self) -> dict:
        return dict()


class SelfieRejectedWebEngageEvent(WebEngageKnownUserEvent):
    event_name = "selfie_vr_rejected"

    def __init__(self, user, reject_reason: str, event_time: Optional[datetime] = None,
                 device_kind: Optional[str] = None):
        super().__init__(user, event_time, device_kind)
        self.reject_reason = reject_reason

    def _get_data(self) -> dict:
        return {"reject_reason": self.reject_reason}


class AutoKycRejectedWebEngageEvent(WebEngageKnownUserEvent):
    event_name = "auto_kyc_vr_rejected"

    def __init__(self, user, reject_reason: str, event_time: Optional[datetime] = None,
                 device_kind: Optional[str] = None):
        super().__init__(user, event_time, device_kind)
        self.reject_reason = reject_reason

    def _get_data(self) -> dict:
        return {"reject_reason": self.reject_reason}


class SelfieStartedWebEngageEvent(WebEngageKnownUserEvent):
    event_name = "selfie_vr_started"

    def _get_data(self) -> dict:
        return dict()


class AutoKycStartedWebEngageEvent(WebEngageKnownUserEvent):
    event_name = "auto_kyc_vr_started"

    def _get_data(self) -> dict:
        return dict()


class SuccessfulRegisterWithReferralCode(WebEngageKnownUserEvent):
    event_name = "successful_register_with_referral_code"

    def _get_data(self) -> dict:
        return dict()

    def send(self):
        if not self._is_eligible_for_sending():
            return
        super().send()
        task_send_user_referral_data_to_web_engage.delay(user_id=self.user.id)


class ReferredUserUpgradedToLevel1WebEngageEvent(WebEngageKnownUserEvent):
    event_name = "referred_user_upgraded_to_level_1"

    def _get_data(self) -> dict:
        return dict()

    def send(self):
        if not self._is_eligible_for_sending():
            return
        super().send()
        task_send_user_referral_data_to_web_engage.delay(user_id=self.user.id)
