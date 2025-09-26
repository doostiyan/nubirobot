from celery import shared_task

from exchange.integrations.errors import APICallException, ConnectionFailedException
from exchange.web_engage.externals.web_engage import web_engage_event_api
from exchange.web_engage.services.user import send_user_base_data, send_user_campaign_data, send_user_referral_data
from exchange.web_engage.types import EmailStatusEventData


@shared_task(name='task_send_user_data_to_web_engage', max_retries=1, rate_limit='5000/m')
def task_send_user_data_to_web_engage(user_id: int):
    send_user_base_data(user_id=user_id)


@shared_task(name='task_send_user_referral_data_to_web_engage', max_retries=1, rate_limit='5000/m')
def task_send_user_referral_data_to_web_engage(user_id: int):
    send_user_referral_data(user_id=user_id)


@shared_task(name='task_send_user_campaign_data_to_web_engage', max_retries=1, rate_limit='5000/m')
def task_send_user_campaign_data_to_web_engage(webengage_user_id: str, campaign_id: str):
    send_user_campaign_data(webengage_user_id, campaign_id)


@shared_task(name='task_send_event_data_to_web_engage', max_retries=1, rate_limit='5000/m')
def task_send_event_data_to_web_engage(data: dict):
    web_engage_event_api.send(data)


@shared_task(name="task_send_dsn_to_web_engage", max_retries=5)
def task_send_dsn_to_web_engage(email_status_event: dict):
    from exchange.web_engage.services.esp import send_email_delivery_status_to_webengage

    send_email_delivery_status_to_webengage(EmailStatusEventData(**email_status_event))


@shared_task(bind=True, name="web_engage_send_batch_sms_to_ssp",
             max_retries=5, autoretry_for=(ConnectionFailedException, APICallException))
def task_send_batch_sms_to_ssp(self, batch_id: int):
    from exchange.web_engage.services.ssp import send_batch_sms

    send_batch_sms(batch_id, self.request.retries, self.max_retries)
