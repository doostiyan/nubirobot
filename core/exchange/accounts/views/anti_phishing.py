from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status

from exchange.accounts.models import AntiPhishing, UserOTP
from exchange.base.api import APIView, email_required_api
from exchange.base.emailmanager import EmailManager
from exchange.base.parsers import parse_str


class AntiPhishingView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='10/m', method='GET', block=True))
    def get(self, request):
        user = request.user
        anti_phishing_code = AntiPhishing.get_anti_phishing_code_by_user(user)

        if not anti_phishing_code:
            return JsonResponse({
                'status': 'failed',
                'code': 'NotFound',
                'message': 'AntiPhishingCode is not declared for this user',
            }, status=status.HTTP_404_NOT_FOUND)

        return self.response({
            'status': 'ok',
            'antiPhishingCode': AntiPhishing.hide_code(anti_phishing_code),
        })

    @method_decorator(ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True))
    @method_decorator(email_required_api)
    def post(self, request):
        user = request.user
        otp_code = parse_str(self.g('otpCode'), required=True)
        code = parse_str(self.g('code'), required=True)
        if not (4 <= len(code) <= 15):
            return JsonResponse({
                'status': 'failed',
                'code': 'InvalidCodeLength',
                'message': 'Code length must be between 4 and 15 characters'
            }, status=status.HTTP_400_BAD_REQUEST)
        otp_obj, mobile_error = UserOTP.verify(code=otp_code, tp=UserOTP.OTP_TYPES.email,
                                               usage=UserOTP.OTP_Usage.anti_phishing_code, user=user)
        if mobile_error or otp_obj is None:
            return JsonResponse({
                'status': 'failed',
                'code': 'InvalidOTPCode',
                'message': 'Please use otp/request endpoint',
            }, status=status.HTTP_400_BAD_REQUEST)
        previous_anti_phishing_code = AntiPhishing.get_anti_phishing_code_by_user(user)
        already_activated = previous_anti_phishing_code is not None and len(previous_anti_phishing_code) > 0
        AntiPhishing.set_anti_phishing_code(user, code=code)
        EmailManager.send_email(
            user.email,
            'change_anti_phishing_code' if already_activated else 'set_anti_phishing_code',
            data={'anti_phishing_code': code},
            priority='low',
        )
        otp_obj.mark_as_used()
        return self.response({'status': 'ok'})
