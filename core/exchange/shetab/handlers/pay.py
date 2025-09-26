import requests
from django.conf import settings

from exchange.base.logging import report_exception


class PayHandler:
    @classmethod
    def get_nextpay_id(cls, deposit):
        token = deposit.nextpay_id
        if not settings.IS_PROD:
            token = token[token.find('-') + 1:]
        return token

    @classmethod
    def send_token_request(cls, deposit, request):
        uid = 'nobitex{}'.format(deposit.pk)
        redirect_url = 'https://api.nobitex.ir/' if settings.IS_PROD else request.build_absolute_uri('/')
        redirect_url += 'users/wallets/deposit/shetab-callback'
        try:
            r = requests.post('https://pay.ir/pg/send', data={
                'api': settings.PAY_IR_API_KEY,
                'amount': deposit.amount,
                'factorNumber': str(deposit.pk),
                'description': uid,
                'redirect': redirect_url,
                'resellerId': 1000015859,
            }, timeout=10)
            r.raise_for_status()
            return r.json()
        except:
            report_exception()
            return {}

    @classmethod
    def send_verify_request(cls, deposit):
        try:
            r = requests.post('https://pay.ir/pg/verify', data={
                'api': settings.PAY_IR_API_KEY,
                'token': cls.get_nextpay_id(deposit),
            }, timeout=10)
            r.raise_for_status()
            return r.json()
        except:
            report_exception()
            return None

    @classmethod
    def sync(cls, deposit, request, **kwargs):
        if not deposit.pk or not deposit.user or not deposit.amount:
            return
        if deposit.broker != deposit.BROKER.payir:
            return
        if deposit.is_requested:
            r = cls.send_verify_request(deposit) or {}
            deposit.status_code = r.get('status', -10002)
            fields = ['status_code']
            if deposit.is_status_valid:
                confirmed_amount = r.get('amount')
                if not confirmed_amount or int(confirmed_amount) != deposit.amount:
                    deposit.status_code = -10002
                else:
                    deposit.user_card_number = r['cardNumber']
                    fields.append('user_card_number')
            deposit.save(update_fields=fields)
        else:
            r = cls.send_token_request(deposit, request)
            deposit.status_code = int(r.get('status', -10001))
            if deposit.status_code == 1:
                deposit.status_code = 0   # To specify the status of total order, which is still pending
                nextpay_id = r.get('token')
                if nextpay_id and nextpay_id != '0':
                    if not settings.IS_PROD:
                        nextpay_id = '{}-{}'.format(deposit.id, nextpay_id)
                    deposit.nextpay_id = nextpay_id
            deposit.save(update_fields=['status_code', 'nextpay_id'])

    @classmethod
    def get_api_redirect_url(cls, deposit):
        return 'https://pay.ir/pg/{}'.format(cls.get_nextpay_id(deposit))


class PayIrHandler:
    base_address = 'https://pay.ir/api/v1/'

    @classmethod
    def get_access_token(cls):
        try:
            data = {'mobile': settings.PAY_IR_USERNAME, 'password': settings.PAY_IR_PASSWORD}
            r = requests.post(f'{cls.base_address}authenticate', data=data, timeout=30)
            r.raise_for_status()
            json_result = r.json()
        except:
            report_exception()
            raise ValueError('PayAPIError')
        access_token = json_result['token']
        return access_token

    @classmethod
    def get_wallet_balances(cls):
        try:
            r = requests.post(f'{cls.base_address}wallet/balance?token={cls.get_access_token()}', timeout=30)
            r.raise_for_status()
            json_result = r.json()
        except:
            report_exception()
            return None
        balance = json_result['data']['balance']
        return balance
