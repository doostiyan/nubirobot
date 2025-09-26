import requests
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site

from exchange.base.logging import report_exception, log_event
from .base import BaseShetabHandler


class IDPayHandler(BaseShetabHandler):
    @classmethod
    def get_api_key(cls, deposit):
        next_url = deposit.next_redirect_url or ''
        if 'nobitex.net' in next_url:
            return '35035432-235e-4e76-868b-f34fb44f3d21'
        else:
            return settings.IDPAY_API_KEY

    @classmethod
    def send_token_request(cls, deposit, request):
        r = None
        uid = 'nobitex{}'.format(deposit.pk)
        try:
            r = requests.post('https://api.idpay.ir/v1.1/payment', json={
                'order_id': uid,
                'amount': deposit.amount,
                'name': str(deposit.user_id),
                'desc': uid,
                'callback': 'https://{}/users/wallets/deposit/shetab-callback'.format(get_current_site(request).domain),
            }, headers={
                'X-API-KEY': cls.get_api_key(deposit),
                'X-SANDBOX': 'true' if settings.DEBUG or settings.IS_TESTNET else 'false',
            }, timeout=10)
            r.raise_for_status()
        except:
            print('Exception in IDPay token request!', r.status_code if r else 'None', r.text if r else 'None')
            report_exception()
            return {}
        return r.json()

    @classmethod
    def send_verify_request(cls, deposit):
        r = None
        uid = 'nobitex{}'.format(deposit.pk)
        try:
            r = requests.post('https://api.idpay.ir/v1.1/payment/verify', json={
                'id': deposit.nextpay_id,
                'order_id': uid,
            }, headers={
                'X-API-KEY': cls.get_api_key(deposit),
                'X-SANDBOX': 'true' if settings.DEBUG or settings.IS_TESTNET else 'false',
            }, timeout=10)
            r.raise_for_status()
            r = r.json()
            payment = r.get('payment', {})
            amount = int(payment.get('amount'))
            card_number = payment.get('card_no')
        except:
            error_details = '[{}] {}'.format(uid, r.text if r is not None else '')
            log_event('IDPay Verify API Failed: {}'.format(r.status_code if r is not None else 0), details=error_details,
                      level='warning', module='shetab', category='notice', runner='api')
            deposit.error_message = r.text if r else 'خطا در اتصال به درگاه'
            report_exception()
            return None
        return {'amount': amount, 'card_number': card_number}

    @classmethod
    def sync(cls, deposit, request, **kwargs):
        from exchange.shetab.models import ShetabDeposit

        if not deposit.pk or not deposit.user or not deposit.amount:
            return
        if deposit.broker != deposit.BROKER.idpay:
            return
        if deposit.is_requested:
            r = cls.send_verify_request(deposit) or {}
            confirmed_amount = r.get('amount')
            if not confirmed_amount:
                deposit.status_code = ShetabDeposit.STATUS.confirmation_failed
            else:
                confirmed_amount = int(confirmed_amount)
                if confirmed_amount != deposit.amount:
                    deposit.status_code = ShetabDeposit.STATUS.amount_mismatch
                else:
                    deposit.status_code = 1
                    deposit.user_card_number = r.get('card_number')
            deposit.save(update_fields=['status_code', 'user_card_number'])
        else:
            r = cls.send_token_request(deposit, request)
            code = r.get('id')
            gateway_redirect_url = r.get('link')
            deposit.status_code = ShetabDeposit.STATUS.pending_request
            if code and code != '0':
                deposit.status_code = 0
                deposit.nextpay_id = code
                deposit.gateway_redirect_url = gateway_redirect_url
            deposit.save(update_fields=['status_code', 'nextpay_id', 'gateway_redirect_url'])
