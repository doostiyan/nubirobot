from exchange.accounts.functions import hide_email_address, hide_mobile_number
from exchange.accounts.models import User, UserMergeRequest, UserOTP, UserSms
from exchange.base.emailmanager import EmailManager


class SendOTPMergeRequest:
    def __new__(cls, user: User, merge_by: int, *_, **__) -> 'SendOTPMergeRequest':
        if merge_by == UserMergeRequest.MERGE_BY.mobile:
            return super().__new__(SendOTPMobileMergeRequest)
        return super().__new__(SendOTPEmailMergeRequest)

    def __init__(self, user: User, merge_by: int, otp_receiver) -> None:
        self.user = user
        self.otp_receiver = otp_receiver
        self.merge_by = merge_by

    def _old_otp_disabled(self):
        raise NotImplementedError

    def _send_otp(self):
        raise NotImplementedError

    def send_otp(self):
        self._old_otp_disabled()
        self._send_otp()


class SendOTPEmailMergeRequest(SendOTPMergeRequest):
    def _old_otp_disabled(self):
        UserOTP.active_otps(
            user=self.user,
            tp=UserOTP.OTP_TYPES.email,
            usage=UserOTP.OTP_Usage.user_merge,
        ).update(otp_status=UserOTP.OTP_STATUS.disabled)

    def _send_otp(self):
        """
        creating Email UserOTP and sending it to second account
        #TODO: Refactoring send function in UserOTP
        """
        otp_obj = UserOTP.create_otp(
            user=self.user,
            tp=UserOTP.OTP_TYPES.email,
            usage=UserOTP.OTP_Usage.user_merge,
        )
        EmailManager.send_email(
            self.otp_receiver,
            'merge/otp_message',
            data={
                'otp': otp_obj.code,
                'merge_type': 'ایمیل',
                'merge_account': hide_email_address(self.otp_receiver),
            },
            priority='high',
        )
        otp_obj.is_sent = True
        otp_obj.save(update_fields=['is_sent'])


class SendOTPMobileMergeRequest(SendOTPMergeRequest):
    def _old_otp_disabled(self):
        UserOTP.active_otps(
            user=self.user,
            tp=UserOTP.OTP_TYPES.mobile,
            usage=UserOTP.OTP_Usage.user_merge,
        ).update(otp_status=UserOTP.OTP_STATUS.disabled)

    def _send_otp(self):
        """
        creating SMS UserOTP and sending it to second account
        #TODO: Refactoring send function in UserOTP
        """
        otp_obj = UserOTP.create_otp(
            user=self.user,
            tp=UserOTP.OTP_TYPES.mobile,
            usage=UserOTP.OTP_Usage.user_merge,
        )
        UserSms.objects.create(
            user=self.user,
            tp=UserSms.TYPES.user_merge,
            to=self.otp_receiver,
            text=hide_mobile_number(self.otp_receiver) + '\n' + otp_obj.code,
            template=UserSms.TEMPLATES.user_merge_otp,
        )
        otp_obj.is_sent = True
        otp_obj.save(update_fields=['is_sent'])
