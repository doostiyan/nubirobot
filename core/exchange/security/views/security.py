""" Security Views """
import datetime

from django.shortcuts import get_object_or_404, render
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.views import View
from django_ratelimit.decorators import ratelimit

from exchange.accounts.models import UserRestriction
from exchange.accounts.user_restrictions import UserRestrictionsDescription
from exchange.base.api import api
from exchange.security.forms import EmergencyCancelWithdrawForm
from exchange.security.models import EmergencyCancelCode, KnownDevice, LoginAttempt
from exchange.security.tasks import delete_all_devices_task
from exchange.wallet.models import WithdrawRequest


def cancel_withdraws(cancel_code):
    msg_help = 'لطفاً از پنل کاربری خود اقدام به لغو درخواست‌های برداشت نمایید.'
    if not cancel_code:
        return {
            'status': 'failed',
            'message': 'کد لغو وارد نشده است. ' + msg_help,
        }
    try:
        emergency_cancel_code = EmergencyCancelCode.objects.get(cancel_code=cancel_code)
    except EmergencyCancelCode.DoesNotExist:
        return {
            'status': 'failed',
            'message': 'کد لغو وارد شده معتبر نیست. ' + msg_help,
        }
    canceled_withdraws_count = 0
    user = emergency_cancel_code.user
    cancelable_withdraw_requests = WithdrawRequest.objects.filter(
        wallet__user=user,
        status__in=WithdrawRequest.STATUSES_CANCELABLE,
        created_at__gte=now() - datetime.timedelta(hours=6),
    )
    for withdraw in cancelable_withdraw_requests:
        canceled = withdraw.cancel_request()
        if canceled:
            canceled_withdraws_count += 1

    # Limit user withdraws for 72 hours for security reasons
    UserRestriction.add_restriction(
        user=user,
        restriction=UserRestriction.RESTRICTION.WithdrawRequest,
        considerations='ایجاد محدودیت برداشت به علت لغو اضطراری درخواست برداشت توسط کاربر',
        duration=datetime.timedelta(hours=72),
        description=UserRestrictionsDescription.EMERGENCY_CANCELLATION_WITHDRAWAL,
    )
    # Create a descriptive message for user
    msg_protection = 'جهت حفاظت از حساب شما، امکان ثبت درخواست برداشت جدید به مدت ۷۲ ساعت برای حساب شما محدود شد.'
    if len(cancelable_withdraw_requests) == 0:
        message = 'شما درخواست برداشت قابل لغو کردنی ندارید. با این حال ' + msg_protection
    else:
        message = 'تعداد {} مورد از {} درخواست برداشت ارسال نشده شما لغو شد. همچنین {}'.format(
            canceled_withdraws_count,
            len(cancelable_withdraw_requests),
            msg_protection,
        )
    return {
        'status': 'finish',
        'message': message,
    }


class EmergencyCancelWithdraw(View):
    """
    Represent the withdraw cancel page in GET method
    Cancel all withdraw requests at his/her own request
    """
    template_name = 'security/emergency_cancel_withdraw.html'
    msg_help = 'لطفاً از پنل کاربری خود اقدام به لغو درخواست‌های برداشت نمایید.'

    @method_decorator(ratelimit(key='ip', rate='10/m', method='GET'))
    def get(self, request):
        form = EmergencyCancelWithdrawForm(request.GET)
        if not form.is_valid():
            return render(request, self.template_name, {
                'status': 'failed',
                'message': 'کد لغو وارد نشده است. ' + self.msg_help,
            })
        cancel_code = form.cleaned_data['code']
        return render(request, self.template_name, {
            'status': 'ok',
            'cancel_code': cancel_code,
        })

    @method_decorator(ratelimit(key='ip', rate='10/h', method='POST'))
    def post(self, request):
        form = EmergencyCancelWithdrawForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {
                'status': 'failed',
                'message': 'کد لغو وارد نشده است. ' + self.msg_help,
            })
        cancel_code = form.cleaned_data['code']
        result = cancel_withdraws(cancel_code)
        return render(request, self.template_name, result)


@ratelimit(key='user_or_ip', rate='25/5m', block=True)
@api
def emergency_cancel_withdraw_get_code(request):
    """Return the emergency withdraw code for this user, or None if not defined.

        POST /security/emergency-cancel/get-code
    """
    cancel_code = EmergencyCancelCode.get_emergency_cancel_code(request.user)
    return {
        'status': 'ok',
        'cancelCode': {
            'code': cancel_code,
        }
    }


@ratelimit(key='user_or_ip', rate='12/h', block=True)
@api
def emergency_cancel_withdraw_activate(request):
    """Activate emergency cancel withdraw feature and return generated cancel code,
       or if it is already activated then return old cancel code.

        POST /security/emergency-cancel/activate
    """
    user = request.user
    cancel_code_obj, _ = EmergencyCancelCode.objects.get_or_create(
        user=user,
        defaults={
            'cancel_code': EmergencyCancelCode.make_unique_cancel_code,
        },
    )
    return {
        'status': 'ok',
        'cancelCode': {
            'code': cancel_code_obj.cancel_code,
        }
    }


@ratelimit(key='user_or_ip', rate='60/h', block=True)
@api
def user_devices(request):
    user = request.user
    login_attempts = LoginAttempt.objects.filter(
        user=user,
        is_successful=True,
        device__isnull=False,
    ).values_list(
        'created_at',
        'ip',
        'ip_country',
        'device__user_agent',
        'device__device_id',
    ).order_by('-created_at')
    devices = {}
    for created_at, ip, ip_country, user_agent, device in login_attempts:
        if device not in devices:
            devices[device] = {
                'device': device,
                'user_agent': user_agent,
                'login_attempts': []
            }
        devices[device]['login_attempts'].append({
            'ip': ip,
            'ip_country': ip_country,
            'created_at': created_at
        })
    return {
        'status': 'ok',
        'devices': list(devices.values()),
    }


@ratelimit(key='user_or_ip', rate='60/h', block=True)
@api
def delete_device(request):
    """Remove known device
       POST security/devices/delete
    """
    device_id = request.g('device')
    known_device = get_object_or_404(
        KnownDevice.objects.filter(user=request.user),
        device_id=device_id
    )
    known_device.delete()
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='60/h', block=True)
@api
def delete_all_devices(request):
    """Remove all known devices
       POST security/devices/delete-all
    """
    delete_all_devices_task.delay(request.user.id)
    return {
        'status': 'ok',
    }
