import logging
from typing import Dict, List
from uuid import uuid4

import requests
from django.conf import settings
from requests import Response

from exchange.base.decorators import measure_time
from exchange.base.logging import metric_incr, report_event
from exchange.integrations.errors import APICallException, ConnectionFailedException
from exchange.integrations.finnotech import get_finnotech_access_token

logger = logging.getLogger(__name__)

FINNOTEXT_INQUIRY_ERROR_CODES = {
    0: 'منتظر ارسال',
    1: 'ارسال شده',
    2: 'تایید نشده توسط کاربر',
    5: 'در مسیر ارسال به مخابرات',
    6: 'کلاینت آی دی تکراری است',
    10: 'ارسال با خطا مواجه شده است',
    11: 'ارسال شده به مخابرات ولی تعیین وضعیت نشده',
    19: 'ارسال شده و گزارش ارسال در دسترس نیست',
    20: 'ارسال شده و گزارش ارسال در دسترس نیست',
    21: 'ارسال شده و آماده تحویل به پیام رسان شده',
    22: 'ارسال شده و مخابرات می باشد',
    23: 'ارسال شده ولی قادر به ارسال پیام نمیباشد- لیست سیاه',
    24: 'ارسال شده و به دست مشترک رسیده است',
    25: 'ارسال پیام در پیام رسان متوقف شده است',
    26: 'شماره اختصاصی نامعتبر',
    100: 'ارسال شده و امکان گزارش گیری نیست'
}


class FinnotextSMSService:

    @classmethod
    @measure_time(metric='finnotext_send')
    def send_sms(cls, body: List[str], phone_numbers: List[str], track_id: str, from_number: str):
        """
        Scope: facility:finnotext:post
        Document: https://devbeta.finnotech.ir/facility-finnotext.html?sandbox=undefined
        """

        if not settings.IS_PROD:
            return
        url = f"https://apibeta.finnotech.ir/facility/v2/clients/{settings.MARKETING_FINNOTEXT_CLIENT_ID}/finnotext"
        data = {
            'to': phone_numbers,
            'from': from_number,
            'message': body
        }
        try:
            response = requests.post(
                url,
                json=data,
                headers={'Authorization': f'Bearer {get_finnotech_access_token()}'},
                timeout=(10, 50),
                params={'trackId': track_id},
            )
        except Exception as e:
            metric_incr(f'metric_integrations_errors__finnotext_send_connection')
            metric_incr('metric_integrations_calls__finnotext_send')
            report_event("WebEngage SSP Batch Connection Error")
            raise ConnectionFailedException(actual_exception=e.__class__.__name__)
        metric_incr('metric_integrations_calls__finnotext_send')

        if 200 <= response.status_code < 300:
            response_data = response.json()
            if response_data.get("status") == "DONE":
                return
            else:
                report_event("WebEngage SSP Batch API")
                raise APICallException()
        elif cls._is_duplicate_message_error(response):
            return
        else:
            metric_incr(f'metric_integrations_errors__finnotext_send_{response.status_code}')
            try:
                response.raise_for_status()
            except Exception as e:
                report_event(f"WebEngage SSP Batch API unexpected status code: {response.status_code}")
            raise APICallException(status_code=response.status_code, response_body=response.text)

    @staticmethod
    def _is_duplicate_message_error(response: Response) -> bool:
        try:
            response_data = response.json()
            return (
                response.status_code == 400
                and response_data.get('status') == 'FAILED'
                and 'error' in response_data
                and response_data['error'].get('message', '') == 'trackId is duplicated'
            )
        except:
            return False

    @classmethod
    @measure_time(metric='finnotext_inquiry')
    def inquiry(cls, inquiry_track_id: str, phone_number: str = None) -> Dict[str, int]:
        """
        Scope: finnotext-inquiry:get
        Document: https://docs.finnotech.ir/facility-finnotext-inquiry.html
        """

        url = f"https://apibeta.finnotech.ir/facility/v2/clients/{settings.MARKETING_FINNOTEXT_CLIENT_ID}/finnotextInquiry"
        if not settings.IS_PROD:
            return {phone_number: 24}
        try:
            response = requests.get(
                url,
                headers={'Authorization': f'Bearer {get_finnotech_access_token()}'},
                timeout=(10, 50),
                params={'trackId': str(uuid4()), 'inquiryTrackId': str(inquiry_track_id)},
            )
        except Exception as e:
            logger.exception("Error calling finnotech Inquiry API")
            metric_incr(f'metric_integrations_errors__finnotext_inquiry_connection')
            metric_incr('metric_integrations_calls__finnotext_inquiry')
            raise ConnectionFailedException(e.__class__.__name__)
        metric_incr('metric_integrations_calls__finnotext_inquiry')
        response_data = response.json()
        if 200 <= response.status_code < 300 and response_data.get("status") == "DONE":
            message_status = response_data.get("result", dict()).get("messages_status")
            return {
                m["to_number"] if m["to_number"].startswith('+98') else '+98' + m["to_number"][1:]: m["status"]
                for m in message_status
            }
        elif response.status_code == 404:
            from exchange.web_engage.models.sms_log import WebEngageSMSBatch
            batch = WebEngageSMSBatch.objects.get(track_id=inquiry_track_id)
            batch.status = WebEngageSMSBatch.STATUS.inquired
            batch.save(update_fields=['status'])
            metric_incr(f'metric_integrations_errors__finnotext_inquiry_{response.status_code}')
            raise APICallException(status_code=response.status_code, response_body=response.text)
        else:
            metric_incr(f'metric_integrations_errors__finnotext_inquiry_{response.status_code}')
            raise APICallException(status_code=response.status_code, response_body=response.text)

    @classmethod
    @measure_time(metric='finnotext_otp')
    def send_otp(cls, body: str, phone_number: str, track_id: str, from_number: str, timeout: int):
        """
        Scope: facility:finnotext-otp:post
        Document: https://docs.finnotech.ir/facility-finnotextOtp.html
        """

        if not settings.IS_PROD:
            return
        url = f"https://apibeta.finnotech.ir/facility/v2/clients/{settings.MARKETING_FINNOTEXT_CLIENT_ID}/finnotextOtp"
        data = {'to': phone_number, 'from': from_number, 'message': body}
        try:
            response = requests.post(
                url,
                json=data,
                headers={'Authorization': f'Bearer {get_finnotech_access_token()}'},
                timeout=timeout,
                params={'trackId': track_id},
            )
        except Exception as e:
            metric_incr(f'metric_integrations_errors__finnotext_otp_connection')
            metric_incr('metric_integrations_calls__finnotext_otp')
            report_event("finnotext OTP Error")
            raise ConnectionFailedException(actual_exception=e.__class__.__name__)
        metric_incr('metric_integrations_calls__finnotext_otp')

        if 200 <= response.status_code < 300:
            response_data = response.json()
            if response_data.get("status") == "DONE":
                return response_data['result']
            else:
                report_event("finnotext OTP Error")
                raise APICallException(response_body="""{"track_id": \"""" + track_id + """\"}""")
        else:
            metric_incr(f'metric_integrations_errors__finnotext_otp_{response.status_code}')
            try:
                response.raise_for_status()
            except Exception as e:
                report_event(f"Finnotech otp unexpected status code: {response.status_code}")
            raise APICallException(status_code=response.status_code, response_body=str(response.json()['error']))
