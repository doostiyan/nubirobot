import random
import re
from uuid import uuid4

import requests
from django.conf import settings

from exchange.accounts.sms_config import (
    AGGREGATED_LOAD_BALANCER,
    GENERAL_AGGREGATED_LOAD_BALANCER_PER_TEMPLATE,
    SMS_PROVIDER_LOAD_BALANCER_CONFIG_key,
    SmsProvider,
)
from exchange.accounts.sms_templates import (
    KAVENEGAR_TEMPLATES,
    OLD_SMSIR_TO_KAVENEGAR_TEMPLATE_CONVERTOR_MAP,
    OLD_SMSIR_TO_NEW_SMSIR_TEMPLATE_CONVERTOR_MAP,
    OLD_TEMPLATE_NUMBER_TO_TEMPLATE_NAME_DICT,
)
from exchange.base.decorators import measure_time_cm
from exchange.base.logging import metric_incr
from exchange.base.models import Settings
from exchange.integrations.errors import APICallException, ConnectionFailedException
from exchange.integrations.finnotext import FinnotextSMSService


def get_human_readable_template_name(template_number: int) -> str:
    # Example: Gets template number 54043 and returns 'TfaEnable'
    template_name = OLD_TEMPLATE_NUMBER_TO_TEMPLATE_NAME_DICT.get(template_number, 'unknown')
    return ''.join(x.capitalize() for x in template_name.lower().split('_'))


class SmsSender:
    @classmethod
    def send(cls, sms: 'UserSms'):
        if sms.template == 0 or sms.template not in OLD_SMSIR_TO_NEW_SMSIR_TEMPLATE_CONVERTOR_MAP:
            OldSmsIrClient.send(sms)
            return

        provider = cls.load_balance_between_providers(sms.template)
        if provider == SmsProvider.KAVENEGAR.value:
            KavenegarClient.send(sms)
        elif provider == SmsProvider.NEW_SMSIR.value:
            NewSmsIrClient.send(sms)
        elif provider == SmsProvider.FINNOTEXT.value:
            cls.send_with_finnotext(sms)
        else:
            OldSmsIrClient.send(sms)

    @classmethod
    def send_with_finnotext(cls, sms):
        from exchange.accounts.models import UserSms

        # todo refactor later! come up with better details and delivery status formats.
        # todo finnotext inquiry needs to be added here later.
        number = sms.get_receiving_numbers()[0]  # TODO this is considered to always be just one number.
        track_id = str(uuid4())
        try:
            details = FinnotextSMSService.send_otp(
                phone_number=number, body=sms.sms_full_text, track_id=track_id, from_number='987007793', timeout=8
            )
            delivery_status = f'Sent: {track_id}'
            if details is not None:
                details = f'Sent: {details}'
            metric_incr(
                f'metric_smsir_api_counter__finnotext_SuccessfulSend_{get_human_readable_template_name(sms.template)}'
            )
        except ConnectionFailedException:
            details = f'Failed: {track_id} connection failed'
            delivery_status = 'Sent: Unsuccessful'
            metric_incr(
                f'metric_smsir_api_counter__finnotext_ConnectionFailed_{get_human_readable_template_name(sms.template)}'
            )
        except APICallException as e:
            details = 'Failed: ' + e.response_body
            delivery_status = 'Sent: Unsuccessful'
            metric_incr(
                f'metric_smsir_api_counter__finnotext_ConnectionFailed_{get_human_readable_template_name(sms.template)}'
            )
        sms.details = details[:100]
        sms.delivery_status = delivery_status[:100]
        sms.carrier = UserSms.CARRIERS.finnotext
        sms.save(update_fields=['details', 'delivery_status', 'carrier'])

    @classmethod
    def load_balance_between_providers(cls, template) -> SmsProvider:
        load_balancer_config = Settings.get_cached_json(
            SMS_PROVIDER_LOAD_BALANCER_CONFIG_key, default=AGGREGATED_LOAD_BALANCER
        )
        load_balance_for_template = load_balancer_config.get(
            OLD_TEMPLATE_NUMBER_TO_TEMPLATE_NAME_DICT[template], GENERAL_AGGREGATED_LOAD_BALANCER_PER_TEMPLATE
        )
        load_balance_for_template = sorted(load_balance_for_template.items(), key=lambda item: item[1])
        randomness = random.random()
        for provider, provider_chance in load_balance_for_template:
            if randomness < provider_chance:
                return provider
        return SmsProvider.DEFAULT.value


class OldSmsIrClient:
    @classmethod
    def send(cls, sms: 'UserSms'):
        numbers = sms.get_receiving_numbers()
        fast_send = sms.template > 0

        with measure_time_cm(metric='metric_smsir_api_time__old_Token'):
            r = requests.post(
                'http://restfulsms.com/api/Token',
                json={
                    'UserApiKey': settings.SMSIR_API_KEY,
                    'SecretKey': settings.SMSIR_SECRET_KEY,
                },
                timeout=8,
            )
        r.raise_for_status()
        token = r.json().get('TokenKey')
        if not token:
            print(r.json())
            sms.details = 'Cannot get token:' + r.json()['Message']
            sms.save(update_fields=['details'])
            return

        if fast_send:
            with measure_time_cm(metric='metric_smsir_api_time__old_UltraFastSend'):
                r = requests.post(
                    'http://restfulsms.com/api/UltraFastSend',
                    json={
                        'ParameterArray': [
                            {'Parameter': parameter, 'ParameterValue': value}
                            for parameter, value in sms._get_parameters_map().items()
                        ],
                        'Mobile': numbers[0],
                        'TemplateId': str(sms.template),
                    },
                    headers={'x-sms-ir-secure-token': token},
                    timeout=8,
                )
        else:
            text = sms.text + '\n' + 'لغو 11'
            with measure_time_cm(metric='metric_smsir_api_time__old_MessageSend'):
                r = requests.post(
                    'http://restfulsms.com/api/MessageSend',
                    json={
                        'Messages': [text],
                        'MobileNumbers': numbers,
                        'LineNumber': '100091070325',
                        'SendDateTime': '',
                        'CanContinueInCaseOfError': 'false',
                    },
                    headers={'x-sms-ir-secure-token': token},
                    timeout=8,
                )
        try:
            r.raise_for_status()
        except Exception as e:
            error = e.__class__.__name__
            metric_incr(f'metric_smsir_api_counter__old_{error}_{get_human_readable_template_name(sms.template)}')
            raise e

        r = r.json()
        if not r['IsSuccessful']:
            metric_incr(
                f'metric_smsir_api_counter__old_UnsuccessfulSend_{get_human_readable_template_name(sms.template)}'
            )
            sms.details = ('Failed:' + r['Message'])[:100]
            sms.delivery_status = 'Sent: Unsuccessful'
            sms.save(update_fields=['details', 'delivery_status'])
            return

        sms.details = 'Sent: {}'.format(r.get('VerificationCodeId' if fast_send else 'BatchKey', 'ERROR'))
        provider_id = r.get('ids', None)
        if provider_id:
            sms.provider_id = int(provider_id[0].get('id'))
        sms.delivery_status = 'Sent: {}'.format(r.get('VerificationCodeId' if fast_send else 'BatchKey', 'ERROR'))
        sms.save(update_fields=['details', 'delivery_status', 'provider_id'])

        metric_incr(f'metric_smsir_api_counter__old_SuccessfulSend_{get_human_readable_template_name(sms.template)}')


class NewSmsIrClient:
    API_KEY = settings.NEW_SMSIR_API_KEY
    URL = 'https://api.sms.ir/v1/send/verify'
    MAX_VALUE_LENGTH = 25
    SUCCESSFUL_STATUSES = {1}

    @classmethod
    def send(cls, sms: 'UserSms'):
        from exchange.accounts.models import UserSms

        # TODO We have only moved fastSms here, the rest can be moved here later
        # documentation: https://app.sms.ir/developer/help/verify

        numbers = sms.get_receiving_numbers()
        new_template_id = OLD_SMSIR_TO_NEW_SMSIR_TEMPLATE_CONVERTOR_MAP[sms.template]
        parameters = [
            {'name': parameter, 'value': value[: cls.MAX_VALUE_LENGTH]}  # Value can have a maximum of 25 chars
            for parameter, value in sms._get_parameters_map().items()
        ]
        with measure_time_cm(metric='metric_smsir_api_time__new_Verify'):
            r = requests.post(
                cls.URL,
                json={
                    'parameters': parameters,
                    'mobile': numbers[0],
                    'templateId': new_template_id,
                },
                headers={'Content-Type': 'application/json', 'Accept': 'text/plain', 'x-api-key': cls.API_KEY},
                timeout=8,
            )
        try:
            r.raise_for_status()
        except Exception as e:
            error = e.__class__.__name__
            metric_incr(f'metric_smsir_api_counter__new_{error}_{get_human_readable_template_name(sms.template)}')
            raise e

        r = r.json()
        if int(r['status']) not in cls.SUCCESSFUL_STATUSES:
            # TODO can retry for important messages
            metric_incr(
                f'metric_smsir_api_counter__new_UnsuccessfulSend_{get_human_readable_template_name(sms.template)}'
            )
            sms.details = (
                'Failed:'
                + (
                    r['message']
                    if r.get('message')
                    else NEW_SMS_IR_STATUS_CODES.get(int(r['status']), f'ERROR status {r["status"]}')
                )[:100]
            )
            sms.delivery_status = 'Sent: Unsuccessful'
            sms.carrier = UserSms.CARRIERS.new_restfulsms
            sms.save(update_fields=['details', 'delivery_status', 'carrier'])
            return

        sms.details = f'Sent: {r.get("data", {}).get("messageId", "ERROR")}'
        sms.provider_id = int(r.get('data', {}).get('messageId', None))
        sms.delivery_status = f'Sent: {r.get("data", {}).get("messageId", "ERROR")}'
        sms.carrier = UserSms.CARRIERS.new_restfulsms
        sms.save(update_fields=['details', 'delivery_status', 'provider_id', 'carrier'])

        metric_incr(f'metric_smsir_api_counter__new_SuccessfulSend_{get_human_readable_template_name(sms.template)}')


class KavenegarClient:
    API_KEY = settings.KAVENEGAR_SMS_API_KEY
    URL = f'https://api.kavenegar.com/v1/{API_KEY}/verify/lookup.json'
    HEADERS = {
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
        'charset': 'utf-8',
    }
    UNACCEPTABLE_CHARACTERS = {'\\', '/', '|', ' ', '\n', '-', '_', '&', '?'}
    SUCCESSFUL_STATUSES = {200}

    @classmethod
    def send(cls, sms: 'UserSms'):
        from exchange.accounts.models import UserSms

        # documentation: https://kavenegar.com/rest.html#sms-Lookup
        # Python SDK sample: https://kavenegar.com/SDK.html#python
        # sample request:
        # https://api.kavenegar.com/v1/{API-KEY}/verify/lookup.json?receptor=09361234567&token=852596&template=myverification
        # Kavenegar cannot process special chars in the list above. We can ask for tokens with space later.
        parameters_map = cls._get_parameters_map(sms)
        for _, value in parameters_map.items():
            if any(ch in cls.UNACCEPTABLE_CHARACTERS for ch in value):
                NewSmsIrClient.send(sms)
                return

        numbers = sms.get_receiving_numbers()
        template_name = OLD_SMSIR_TO_KAVENEGAR_TEMPLATE_CONVERTOR_MAP[sms.template]
        receptor_query = f'receptor={numbers[0]}'
        parameters_query = '&'.join(f'{parameter}={value}' for parameter, value in parameters_map.items())
        template_query = f'template={template_name}'
        url = cls.URL + '?' + '&'.join([receptor_query, parameters_query, template_query])

        with measure_time_cm(metric='metric_smsir_api_time__kavenegar_Verify'):
            r = requests.post(url, headers=cls.HEADERS, timeout=15)
        try:
            r.raise_for_status()
        except Exception as e:
            error = e.__class__.__name__
            metric_incr(f'metric_smsir_api_counter__kavenegar_{error}_{get_human_readable_template_name(sms.template)}')
            raise e

        r = r.json()
        status_message = (
            r.get('entries', [{}])[0].get('statustext', '')  # Sms delivery status in Text
            or r.get('entries', [{}])[0].get('status', '')  # Sms delivery status in number
            or r.get('return', {}).get('message', '')  # Http response message
        )
        status_code = r.get('return', {}).get('status', 400)

        if int(status_code) not in cls.SUCCESSFUL_STATUSES:
            # TODO we can retry with another provider for status codes 400, 401, 403, 404, 405, 406, 409, 411,
            #  412, 418, 420, 422, 424, 426, 431, 432, 451
            metric_incr(
                f'metric_smsir_api_counter__kavenegar_UnsuccessfulSend_{get_human_readable_template_name(sms.template)}'
            )
            sms.details = ('Failed: ' + status_message)[:100]
            sms.delivery_status = 'Sent: Unsuccessful'
            sms.carrier = UserSms.CARRIERS.kavenegar
            sms.save(update_fields=['details', 'delivery_status', 'carrier'])
            return

        sms.details = f'Sent: {status_message or status_code}'
        sms.provider_id = int(r.get('entries', [{}])[0].get('messageid', None))
        sms.delivery_status = f'Sent: {status_message or status_code}'
        sms.carrier = UserSms.CARRIERS.kavenegar
        sms.save(update_fields=['details', 'delivery_status', 'provider_id', 'carrier'])

        metric_incr(
            f'metric_smsir_api_counter__kavenegar_SuccessfulSend_{get_human_readable_template_name(sms.template)}'
        )

    @classmethod
    def _get_parameters_map(cls, sms) -> dict:
        template_name = OLD_SMSIR_TO_KAVENEGAR_TEMPLATE_CONVERTOR_MAP[sms.template]
        template = KAVENEGAR_TEMPLATES[template_name]
        parameters = re.findall('%token.*?[1-9]?\s*', template)
        # removing whitespaces and %:
        parameters = [param[1:].strip() for param in parameters]
        return dict(zip(parameters, sms.text.split('\n')))


NEW_SMS_IR_STATUS_CODES = {
    # documentation: https://app.sms.ir/developer/help/statusCode
    0: 'درخواست شما با خطا مواجه شده‌است.',
    1: 'عملیات با موفقیت انجام شد',
    10: 'کلید وب سرویس نامعتبر است',
    11: 'کلید وب سرویس غیرفعال است',
    12: 'کلید وب سرویس محدود به آی‌پی‌های تعریف شده می‌باشد.',
    13: 'حساب کاربری غیرفعال است',
    14: 'حساب کاربری در حالت تعلیق قرار دارد',
    15: 'به منظور استفاده از وب سرویس پلن خود را ارتقا دهید',
    16: 'مقدار ارسالی پارامتر نادرست می‌باشد',
    20: 'تعداد درخواست بیشتر از حد مجاز است',
    101: 'شماره خط نامعتبر میباشد',
    102: 'اعتبار کافی نمیباشد',
    103: 'درخواست شما دارای متن (های) خالی است',
    104: 'درخواست شما دارای موبایل (های) نادرست است',
    105: 'تعداد موبایل ها بیشتر از حد مجاز (100 عدد) میباشد',
    106: 'تعداد متن ها بیشتر از حد مجاز (100 عدد) میباشد',
    107: 'لیست موبایل ها خالی میباشد',
    108: 'لیست متن ها خالی میباشد',
    109: 'زمان ارسال نامعتبر میباشد',
    110: 'تعداد شماره موبایل ها و تعداد متن ها برابر نیستند',
    111: 'با این شناسه ارسالی ثبت نشده است',
    112: 'رکوردی برای حذف یافت نشد',
    113: 'قالب یافت نشد',
    114: 'طول رشته مقدار پارامتر، بیش از حد مجاز (25 کاراکتر) میباشد',
    115: 'شماره موبایل(ها) در لیست سیاه سامانه می‌باشند',
    116: 'نام یک یا چند پارامتر مقداردهی نشده‌است. لطفا به بخش مستندات ارسال وریفای مراجعه فرمایید',
    117: 'متن ارسال شده مورد تایید نمی‌باشد',
    118: 'تعداد پیام ها بیشتر از حد مجاز میباشد',
    119: 'به منظور استفاده از قالب‌ شخصی سازی شده پلن خود را ارتقا دهید',
}
