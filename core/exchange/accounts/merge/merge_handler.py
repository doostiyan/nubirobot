from typing import Type

from exchange.accounts.merge.merge_worker import (
    EmailOTPVerifier,
    EmailRequestCreator,
    LastStepNewMobileOTPVerifier,
    MergeRequestWorker,
    MobileRequestCreator,
    NewMobileOTPVerifier,
    OldMobileOTPVerifier,
    OTPVerifier,
    RequestCreator,
)
from exchange.accounts.merge.otp_sender import SendOTPMergeRequest
from exchange.accounts.models import (
    User,
    UserMergeRequest,
)


class MergeHandler:
    def __init__(self, main_account: User, second_account: User, merge_by: int) -> None:
        self.main_account = main_account
        self.second_account = second_account
        self.merge_by = merge_by

    def _get_worker_class(self, state: int, merge_by: int) -> Type[MergeRequestWorker]:
        # merge_by email
        if merge_by == UserMergeRequest.MERGE_BY.email:
            return {
                UserMergeRequest.STATUS.requested: EmailRequestCreator,
                UserMergeRequest.STATUS.email_otp_sent: EmailOTPVerifier,
            }[state]

        # merge_by mobile
        if self.main_account.mobile:
            return {
                UserMergeRequest.STATUS.requested: MobileRequestCreator,
                UserMergeRequest.STATUS.old_mobile_otp_sent: OldMobileOTPVerifier,
                UserMergeRequest.STATUS.new_mobile_otp_sent: NewMobileOTPVerifier,
            }[state]

        return {
            UserMergeRequest.STATUS.requested: MobileRequestCreator,
            UserMergeRequest.STATUS.new_mobile_otp_sent: LastStepNewMobileOTPVerifier,
        }[state]

    def initiate_request(self) -> UserMergeRequest:
        """
        Raises:
            IncompatibleUserLevelError
            HasTransactionError
            HasReferralProgramError
            HasActiveMergeRequestError
            UserHasEmailError
            CheckMobileIdentityError
        """
        worker: RequestCreator = self._get_worker_class(UserMergeRequest.STATUS.requested, self.merge_by)
        return worker(self.main_account, self.second_account).apply()

    def proceed_request(self, otp: str, request: UserMergeRequest) -> UserMergeRequest:
        """
        Raises:
            IncompatibleUserLevelError
            HasTransactionError
            HasReferralProgramError
            HasActiveMergeRequestError
            UserHasEmailError
            OTPVerificationError
        """
        worker: OTPVerifier = self._get_worker_class(request.status, self.merge_by)
        return worker(self.main_account, self.second_account, request, otp).apply()

    @classmethod
    def retry_send_otp(cls, request: UserMergeRequest):
        otp_receiver = {
            UserMergeRequest.STATUS.email_otp_sent: request.second_user.email,
            UserMergeRequest.STATUS.new_mobile_otp_sent: request.second_user.mobile,
            UserMergeRequest.STATUS.old_mobile_otp_sent: request.main_user.mobile,
        }
        return SendOTPMergeRequest(request.main_user, request.merge_by, otp_receiver[request.status]).send_otp()
