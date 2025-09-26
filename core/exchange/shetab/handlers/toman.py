from typing import List, Optional

import requests
from django.conf import settings
from django.core.cache import cache
from rest_framework.reverse import reverse

from exchange.accounts.models import BankCard
from exchange.base.helpers import get_base_api_url
from exchange.base.logging import report_event, report_exception
from exchange.shetab.errors import TomanAuthenticateError, TomanClientError, TomanFailedVerify
from exchange.shetab.handlers.base import BaseShetabHandler


class TomanAuthenticate:
    access_token_cache_name = 'access_token_toman'
    auth_production_toman_url = 'https://accounts.qbitpay.org/oauth2/token/'
    auth_staging_toman_url = 'https://auth.qbitpay.org/oauth2/token/'

    @property
    def auth_url(self):
        if settings.IS_PROD:
            return self.auth_production_toman_url
        return self.auth_staging_toman_url

    @property
    def access_token(self):
        return cache.get(self.access_token_cache_name) or self.acquire_access_token()

    def acquire_access_token(self):
        data = {'grant_type': 'password',
                'client_id': settings.TOMAN_CLIENT_ID,
                'client_secret': settings.TOMAN_CLIENT_SECRET,
                'username': settings.TOMAN_USERNAME,
                'password': settings.TOMAN_PASSWORD,
                'scope': 'payment.create '
                         'payment.list '
                         'settlement.single.submit '
                         'settlement.single.verify '
                         'settlement.single.list',
                }
        try:
            response = requests.post(url=self.auth_url, timeout=30, data=data)
            response.raise_for_status()
            response = response.json()
            access_token = 'Bearer ' + response['access_token']
            cache.set(self.access_token_cache_name, access_token, response['expires_in'])
            return access_token

        except Exception as error:
            report_exception()
            raise TomanAuthenticateError(error) from error


class TomanClient:
    authenticate = TomanAuthenticate()

    def request(self, url, method, **kwargs):
        headers = kwargs.get('headers', {})
        headers.update({'Authorization': self.authenticate.access_token})
        kwargs['headers'] = headers

        try:
            response = requests.request(method, url, timeout=30, **kwargs)
            if response.status_code == 401:
                kwargs['headers']['Authorization'] = self.authenticate.acquire_access_token()
                response = requests.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            return response

        except Exception as error:
            report_exception()
            raise TomanClientError(error) from error


class TomanHandler(BaseShetabHandler):
    toman_client = TomanClient()
    production_url = 'https://ipg.toman.ir/payments'
    staging_url = 'https://ipg-staging.toman.ir/payments'

    @classmethod
    def callback_url(cls):
        return (
            get_base_api_url()
            + reverse('shetab_callback').replace('/', '', 1)
            + '?gateway=toman'
        )

    @classmethod
    def get_url(cls):
        if settings.IS_PROD:
            return cls.production_url
        return cls.staging_url

    @classmethod
    def create_payment(cls, amount: int, tracker_id: str, card_numbers: Optional[List[str]] = None):
        data = {
            'amount': amount,
            'callback_url': cls.callback_url(),
            'tracker_id': tracker_id,
            'card_numbers': card_numbers
        }
        response = cls.toman_client.request(url=cls.get_url(), method='post', json=data).json()
        return {
            'uuid': response['uuid'],
            'tracker_id': response['tracker_id'],
        }

    @classmethod
    def send_verify_request(cls, deposit):
        verify_url = f'/{deposit.nextpay_id}/verify'
        response = cls.toman_client.request(url=cls.get_url() + verify_url, method='post').json()
        if response.get('uuid') != deposit.nextpay_id or int(response.get('amount') or 0) != deposit.amount:
            report_event(
                'TomanFailedVerify',
                extra={
                    'response_uuid': response.get('uuid'),
                    'response_amount': response.get('amount'),
                    'deposit_id': deposit.id,
                },
            )
            raise TomanFailedVerify()

    @classmethod
    def sync(cls, deposit, request, **kwargs):
        from exchange.shetab.models import ShetabDeposit

        if not deposit.pk or not deposit.user or not deposit.amount:
            return
        if deposit.broker != deposit.BROKER.toman:
            return
        if deposit.status_code == 1:
            return
        # Initial payment creation
        if not deposit.is_requested or deposit.status_code == ShetabDeposit.STATUS.pending_request:
            try:
                card_numbers = list(
                    BankCard.objects.filter(user=deposit.user, confirmed=True).values_list("card_number", flat=True)
                )
                payment = cls.create_payment(
                    amount=deposit.amount,
                    tracker_id=deposit.pk,
                    card_numbers=card_numbers,
                )
                code = payment.get('uuid')
                if code and code != '0':
                    deposit.status_code = 0
                    deposit.nextpay_id = code

            except (TomanAuthenticateError, TomanClientError) as error:
                deposit.status_code = ShetabDeposit.STATUS.pending_request
            deposit.save(update_fields=['status_code', 'nextpay_id'])

        elif (
            deposit.status_code == ShetabDeposit.STATUS.pay_new
            or deposit.status_code == ShetabDeposit.STATUS.confirmation_failed
        ):
            try:
                payment = cls.fetch_payment(deposit)
                if payment["amount"] != deposit.amount:
                    deposit.status_code = ShetabDeposit.STATUS.amount_mismatch
                if payment["status"] == 4:
                    cls.send_verify_request(deposit)
                    deposit.status_code = 1
                    deposit.user_card_number = payment['masked_paid_card_number']
                else:
                    deposit.status_code = ShetabDeposit.STATUS.confirmation_failed
            except (TomanAuthenticateError, TomanClientError):
                deposit.status_code = ShetabDeposit.STATUS.confirmation_failed
            except TomanFailedVerify:
                deposit.status_code = ShetabDeposit.STATUS.amount_mismatch
            deposit.save(update_fields=['status_code', 'user_card_number'])
        else:
            cls.update_status_failed_request(deposit)

    @classmethod
    def update_status_failed_request(cls, deposit):
        try:
            status = cls.fetch_payment(deposit)['status']
            if status in [1, 2, 3, 4]:
                deposit.status_code = 0
            elif status == 5:
                deposit.status_code = 1
            else:
                from exchange.shetab.models import ShetabDeposit

                deposit.status_code = ShetabDeposit.STATUS.amount_mismatch
        except (TomanAuthenticateError, TomanClientError) as error:
            return

    @classmethod
    def fetch_payment(cls, deposit):
        url = cls.get_url() + f'/{deposit.nextpay_id}'
        response = cls.toman_client.request(url, 'get').json()
        return {
            'uuid': response['uuid'],
            'amount': response['amount'],
            'status': response['status'],
            'toman_wage': response['toman_wage'],
            'shaparak_wage': response['shaparak_wage'],
            'verified_at': response['verified_at'],
            'tracker_id': response['tracker_id'],
            'masked_paid_card_number': response['masked_paid_card_number'],
        }

    @classmethod
    def get_api_redirect_url(cls, deposit):
        return cls.get_url() + f'/{deposit.nextpay_id}/redirect'
