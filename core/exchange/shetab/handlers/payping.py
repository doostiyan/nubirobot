import math

import requests
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site

from exchange.base.logging import report_exception, log_event


class PaypingHandler:
    @classmethod
    def send_token_request(cls, deposit, request):
        r = None
        uid = 'nobitex{}'.format(deposit.pk)
        try:
            r = requests.post('https://api.payping.ir/v1/pay', json={
                'name': uid,
                'amount': math.ceil(deposit.amount / 10),
                'payerIdentity': str(deposit.user_id),
                'returnUrl': 'https://{}/users/wallets/deposit/shetab-callback'.format(get_current_site(request).domain),
                'description': uid,
                'clientRefId': uid,
            }, headers={
                'Authorization': 'Bearer {}'.format(settings.PAYPING_API_KEY),
            }, proxies=settings.DEFAULT_PROXY, timeout=10)
            r.raise_for_status()
        except:
            print('Exception in payping token request!', r.status_code if r else 'None', r.text if r else 'None')
            report_exception()
            return {}
        return r.json()

    @classmethod
    def send_verify_request(cls, deposit):
        r = None
        amount = math.ceil(deposit.amount / 10)
        ref_id = getattr(deposit, 'callback_ref_id', '0')
        try:
            r = requests.post('https://api.payping.ir/v1/pay/verify', json={
                'refId': ref_id,
                'amount': amount,
            }, headers={
                'Authorization': 'Bearer {}'.format(settings.PAYPING_API_KEY),
            }, proxies=settings.DEFAULT_PROXY, timeout=10)
            r.raise_for_status()
        except:
            error_details = '[{}] {}'.format(ref_id, r.text if r is not None else '')
            log_event('PayPing Verify API Failed: {}'.format(r.status_code if r is not None else 0), details=error_details,
                      level='warning', module='shetab', category='notice', runner='api')
            deposit.error_message = r.text if r else 'خطا در اتصال به درگاه'
            report_exception()
            return None
        return {'amount': deposit.amount}

    @classmethod
    def get_user_card_number(cls, deposit):
        try:
            r = None
            try:
                r = requests.get('https://api.payping.ir/v1/report/{}'.format(deposit.nextpay_id), headers={
                    'Authorization': 'Bearer {}'.format(settings.PAYPING_API_KEY),
                }, proxies=settings.DEFAULT_PROXY, timeout=10)
                r.raise_for_status()
            except:
                print('Exception in payping get-card request!', r.status_code if r else 'None', r.text if r else 'None')
                report_exception()
                raise ValueError
            return r.json()['rrn']
        except:
            return '1' * 16

    @classmethod
    def sync(cls, deposit, request, **kwargs):
        from exchange.shetab.models import ShetabDeposit

        if not deposit.pk or not deposit.user or not deposit.amount:
            return
        if deposit.broker != deposit.BROKER.payping:
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
                    deposit.user_card_number = cls.get_user_card_number(deposit)
            deposit.save(update_fields=['status_code', 'user_card_number'])
        else:
            r = cls.send_token_request(deposit, request)
            code = r.get('code')
            deposit.status_code = ShetabDeposit.STATUS.pending_request
            if code and code != '0':
                deposit.status_code = 0
                deposit.nextpay_id = code
            deposit.save(update_fields=['status_code', 'nextpay_id'])

    @classmethod
    def get_api_redirect_url(cls, deposit):
        return 'https://api.payping.ir/v1/pay/gotoipg/{}'.format(deposit.nextpay_id)
