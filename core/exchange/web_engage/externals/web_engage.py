import json
import logging
from typing import Optional
from uuid import uuid4

import requests
from django.conf import settings
from django.utils.decorators import method_decorator
from requests import Timeout

from exchange.base.decorators import measure_time
from exchange.base.logging import metric_incr
from exchange.base.models import Settings
from exchange.settings import DEBUG
from exchange.web_engage.types import EmailStatusEventData, SmsStatusData, UserData, UserReferralData

logger = logging.getLogger(__name__)


def is_web_engage_active():
    return not DEBUG and Settings.get_flag("webengage_enabled")


def call_on_webengage_active(func):
    def wrapper(*args, **kwargs):
        if is_web_engage_active():
            return func(*args, **kwargs)

    return wrapper


class WebEngageAPI:
    api_key = settings.WEB_ENGAGE_API_KEY
    timeout_seconds = 10
    base_url = None

    def __init__(self):
        self.headers = {"Authorization": f"Bearer {self.api_key.strip()}", "Content-Type": "application/json"}


class WebEngageEmailDeliveryReportAPI(WebEngageAPI):
    base_url = settings.WEB_ENGAGE_PRIVATE_ESP_WEBHOOK

    @call_on_webengage_active
    def send(self, webengage_id, data: EmailStatusEventData):
        return requests.post(
            headers={'Content-Type': 'application/json'},
            url=self.base_url,
            json={
                'version': '1.0',
                'messageId': data.message_id,
                'event': data.event,  # SENT, DELIVERED, BOUNCE or UNSUBSCRIBE
                'timestamp': data.timestamp,
                'email': webengage_id,
                'hashedEmail': webengage_id,
                'statusCode': data.status_code,
                'message': data.message,
            },
        )


class WebEngageSSPAPI(WebEngageAPI):
    base_url = settings.WEB_ENGAGE_PRIVATE_SSP_WEBHOOK

    @call_on_webengage_active
    def send(self, data: SmsStatusData):
        if data.status == "sms_accepted":
            return requests.post(url=self.base_url, json={"status": data.status})

        request_body = {
            "version": "1.0",
            "messageId": data.message_id,
            "toNumber": data.phone_number,
            "status": data.status,
            "statusCode": data.status_code.value,
            "message": data.message,
        }
        return requests.post(url=self.base_url, json=request_body)


class WebEngageDataAPI(WebEngageAPI):
    base_url = "https://api.webengage.com"
    licence_code = settings.WEB_ENGAGE_LICENSE_CODE

    @call_on_webengage_active
    @method_decorator(measure_time(metric='webengage_event'))
    def request(self, endpoint: str, data: dict, event_type: Optional[str] = None) -> Optional[dict]:
        try:
            headers = {"x-request-id": str(uuid4()).replace('-', ''), **self.headers}
            response = requests.post(
                self.base_url + endpoint.format(license_code=self.licence_code),
                headers=headers,
                data=json.dumps(data),
                timeout=self.timeout_seconds,
            )
        except Timeout:
            metric_incr(f'metric_integrations_errors__webengage_event_connection')
        except Exception:
            logger.exception("Unexpected Exception occurred while trying to send data to web engage.")
        else:
            if response.status_code >= 400:
                metric_incr(f'metric_integrations_errors__webengage_event_{response.status_code}')
                try:
                    response.raise_for_status()
                except Exception as e:
                    logger.exception(f'WebEngage Events: {response.status_code}')
                    logger.exception(f'WebEngage Response Body: {response.text}')
                return
            data = response.json().get("response", dict())
            status = data.get("status")
            if status in ["success", "queued"]:
                return data
        finally:
            metric_incr(f'metric_integrations_calls__webengage_event/{(event_type or "unknown").replace("_", "-")}')


class WebEngageUpsertUserAPI(WebEngageDataAPI):

    def send_base_info(self, user_data: UserData):
        from exchange.accounts.models import User

        user = user_data.user
        order_summary = user_data.order_summary
        data = {
            "userId": user.get_webengage_id(),
            "firstName": user.first_name,
            "hashedPhone": user.get_webengage_id() if user.has_verified_mobile_number else None,
            "hashedEmail": user.get_webengage_id() if user.is_email_verified else None,
            "birthDate": user.birthday.strftime('%Y-%m-%dT10:30:00+0430') if user.birthday else None,
            "gender": user.get_gender_display() if user.gender != User.GENDER.unknown else None,
            "city": user.city or None,
            "country": "Iran",
            "attributes": {
                "2step_verification": user.requires_2fa,
                "date_joined": user.date_joined.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "user_level": user.user_type,
                "last_order_date": order_summary.last_order_date,
                "first_order_date": order_summary.first_order_date,
                "total_order_value_code": order_summary.total_order_value_code,
                "total_orders": order_summary.total_orders,
                "marketing_campaign_id": user_data.marketing_campaign_id,
            },
        }
        data = {key: value for key, value in data.items() if value is not None}
        data['attributes'] = {key: value for key, value in data['attributes'].items() if value is not None}
        return super().request("/v1/accounts/{license_code}/users", data, 'all_user_data')

    def send_referral_info(self, referral_data: UserReferralData):
        user_data = {
            "userId": referral_data.web_engage_user_id,
            "attributes": {
                'referred_count': referral_data.referred_count,
                'authorized_count': referral_data.authorized_count,
            },
        }
        return super().request("/v1/accounts/{license_code}/users", user_data, 'user_referral_attributes')

    def send_user_campaign_info(self, webengage_user_id: str, campaign_id: str):
        user_data = {
            'userId': webengage_user_id,
            'attributes': {
                'marketing_campaign_id': campaign_id,
            },
        }
        return super().request('/v1/accounts/{license_code}/users', user_data, 'user_campaign_attributes')


class WebEngageEventAPI(WebEngageDataAPI):
    def send(self, event_data):
        return super().request("/v1/accounts/{license_code}/events", event_data, event_data.get('eventName'))


web_engage_user_api = WebEngageUpsertUserAPI()
web_engage_event_api = WebEngageEventAPI()
web_engage_email_delivery_report_api = WebEngageEmailDeliveryReportAPI()
web_engage_ssp_api = WebEngageSSPAPI()
