from typing import Optional, Type

from exchange.accounts.exceptions import (
    OTPVerificationError,
)
from exchange.accounts.merge.merge_manager import MergeByEmail, MergeByMobile, MergeManager
from exchange.accounts.merge.otp_sender import SendOTPMergeRequest
from exchange.accounts.models import (
    User,
    UserEvent,
    UserMergeRequest,
    UserOTP,
)


class MergeRequestWorker:
    merge_manager_class: Type[MergeManager]

    def __init__(self, main_account: User, second_account: User) -> None:
        self.main_account = main_account
        self.second_account = second_account
        self.merge_manager: MergeManager = self.merge_manager_class(main_account, second_account)

    def apply(self):
        raise NotImplementedError

    def _change_request_to_next_status(self, request: UserMergeRequest) -> UserMergeRequest:
        raise NotImplementedError


class RequestCreator(MergeRequestWorker):
    merge_manager_class: Type[MergeManager]

    def __init__(
        self,
        main_account: User,
        second_account: User,
        otp_sender: SendOTPMergeRequest,
    ) -> None:
        super().__init__(main_account, second_account)
        self.otp_sender = otp_sender

    def _deactivate_old_merge_request(self):
        UserMergeRequest.objects.filter(main_user=self.main_account).exclude(
            status__in=[
                UserMergeRequest.STATUS.accepted,
                UserMergeRequest.STATUS.need_approval,
                UserMergeRequest.STATUS.rejected,
            ],
        ).update(status=UserMergeRequest.STATUS.failed)

    def _create_request(self) -> UserMergeRequest:
        raise NotImplementedError

    def _deactivate_old_otp(self):
        raise NotImplementedError

    def apply(self):
        self.merge_manager.check_merge_conditions(None)
        request: UserMergeRequest = self._create_request()
        self._deactivate_old_merge_request()
        self._deactivate_old_otp()
        self.otp_sender.send_otp()
        return self._change_request_to_next_status(request)


class EmailRequestCreator(RequestCreator):
    merge_manager_class = MergeByEmail

    def __init__(self, main_account: User, second_account: User) -> None:
        super().__init__(
            main_account,
            second_account,
            SendOTPMergeRequest(main_account, UserMergeRequest.MERGE_BY.email, second_account.email),
        )
        self.email = self.second_account.email

    def _create_request(self) -> UserMergeRequest:
        return UserMergeRequest.objects.create(
            status=UserMergeRequest.STATUS.requested,
            merge_by=UserMergeRequest.MERGE_BY.email,
            main_user=self.main_account,
            second_user=self.second_account,
        )

    def _deactivate_old_otp(self):
        UserOTP.active_otps(
            user=self.main_account,
            tp=UserOTP.OTP_TYPES.email,
            usage=UserOTP.OTP_Usage.user_merge,
        ).update(otp_status=UserOTP.OTP_STATUS.disabled)

    def _change_request_to_next_status(self, request: UserMergeRequest) -> UserMergeRequest:
        request.status = UserMergeRequest.STATUS.email_otp_sent
        request.save(update_fields=['status'])
        return request


class MobileRequestCreator(RequestCreator):
    merge_manager_class = MergeByMobile

    def __init__(self, main_account: User, second_account: User) -> None:
        super().__init__(
            main_account,
            second_account,
            SendOTPMergeRequest(main_account, UserMergeRequest.MERGE_BY.mobile, second_account.mobile),
        )
        self.merge_manager: MergeByMobile

    def _create_request(self):
        return UserMergeRequest.objects.create(
            status=UserMergeRequest.STATUS.requested,
            merge_by=UserMergeRequest.MERGE_BY.mobile,
            main_user=self.main_account,
            second_user=self.second_account,
        )

    def _deactivate_old_otp(self):
        UserOTP.active_otps(
            user=self.main_account,
            tp=UserOTP.OTP_TYPES.mobile,
            usage=UserOTP.OTP_Usage.user_merge,
        ).update(otp_status=UserOTP.OTP_STATUS.disabled)

    def _change_request_to_next_status(self, request: UserMergeRequest):
        request.status = UserMergeRequest.STATUS.new_mobile_otp_sent
        request.save(update_fields=['status'])
        return request


class OTPVerifier(MergeRequestWorker):
    merge_manager_class: Type[MergeManager]
    otp_tp: UserOTP.OTP_TYPES = None
    otp_event_log_error: UserEvent.USER_MERGE_ACTION_TYPES = None

    def __init__(
        self,
        main_account: User,
        second_account: User,
        request: UserMergeRequest,
        otp: str,
    ) -> None:
        super().__init__(main_account, second_account)
        self.request = request
        self.otp = otp

    def _change_request_to_next_status(self, request: UserMergeRequest) -> UserMergeRequest:
        raise NotImplementedError

    def _add_user_event_error_log(self, description: Optional[str] = None):
        UserEvent.objects.create(
            user=self.main_account,
            action=UserEvent.ACTION_CHOICES.user_merge,
            action_type=self.otp_event_log_error,
            description=description,
        )

    def _verify_otp_code(self) -> UserOTP:
        """
        verify UserOTP code
        Raises:
            OTPVerificationError: error in otp verification
        """
        otp_obj, error = UserOTP.verify(
            code=self.otp,
            user=self.main_account,
            tp=self.otp_tp,
            usage=UserOTP.OTP_Usage.user_merge,
        )
        if not otp_obj:
            self._add_user_event_error_log()
            raise OTPVerificationError(error)
        return otp_obj

    def apply(self):
        self.merge_manager.check_basic_conditions(self.request)
        otp_obj: UserOTP = self._verify_otp_code()
        otp_obj.mark_as_used()
        self.request = self._change_request_to_next_status(self.request)
        return self.request


class EmailOTPVerifier(OTPVerifier):
    merge_manager_class = MergeByEmail

    def __init__(self, main_account: User, second_account: User, request: UserMergeRequest, otp: str) -> None:
        super().__init__(main_account, second_account, request, otp)
        self.otp_tp = UserOTP.OTP_TYPES.email
        self.otp_event_log_error = UserEvent.USER_MERGE_ACTION_TYPES.fail_email_otp

    def _change_request_to_next_status(self, request: UserMergeRequest) -> UserMergeRequest:
        self.merge_manager_class(request.main_user, request.second_user).merge(request)
        return request


class LastStepNewMobileOTPVerifier(OTPVerifier):
    merge_manager_class = MergeByMobile

    def __init__(self, main_account: User, second_account: User, request: UserMergeRequest, otp: str) -> None:
        super().__init__(main_account, second_account, request, otp)
        self.otp_tp = UserOTP.OTP_TYPES.mobile
        self.otp_event_log_error = UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp

    def _change_request_to_next_status(self, request: UserMergeRequest) -> UserMergeRequest:
        self.merge_manager_class(request.main_user, request.second_user).merge(request)
        return request


class NewMobileOTPVerifier(OTPVerifier):
    merge_manager_class = MergeByMobile

    def __init__(self, main_account: User, second_account: User, request: UserMergeRequest, otp: str) -> None:
        super().__init__(main_account, second_account, request, otp)
        self.otp_tp = UserOTP.OTP_TYPES.mobile
        self.otp_event_log_error = UserEvent.USER_MERGE_ACTION_TYPES.fail_new_mobile_otp
        self.otp_sender = SendOTPMergeRequest(main_account, UserMergeRequest.MERGE_BY.mobile, main_account.mobile)

    def _change_request_to_next_status(self, request: UserMergeRequest) -> UserMergeRequest:
        request.status = UserMergeRequest.STATUS.old_mobile_otp_sent
        request.save(update_fields=['status'])
        return request

    def apply(self):
        request = super().apply()
        self.otp_sender.send_otp()
        return request


class OldMobileOTPVerifier(OTPVerifier):
    merge_manager_class = MergeByMobile

    def __init__(self, main_account: User, second_account: User, request: UserMergeRequest, otp: str) -> None:
        super().__init__(main_account, second_account, request, otp)
        self.otp_tp = UserOTP.OTP_TYPES.mobile
        self.otp_event_log_error = UserEvent.USER_MERGE_ACTION_TYPES.fail_old_mobile_otp

    def _change_request_to_next_status(self, request: UserMergeRequest) -> UserMergeRequest:
        self.merge_manager_class(request.main_user, request.second_user).merge(request)
        return request
