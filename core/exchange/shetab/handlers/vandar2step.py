import requests
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site

from exchange.base.logging import report_exception, log_event


class Vandar2StepHandler:
    @classmethod
    def get_api_url(cls):
        return 'https://vandar.io/api/ipg/2step/'

    @classmethod
    def send_token_request(cls, deposit, request):
        r = None
        uid = 'nobitex{}'.format(deposit.pk)
        print(get_current_site(request).domain)
        callback_url = 'http://localhost:8000/' if settings.DEBUG else 'https://{}/'.format(get_current_site(request).domain)
        try:
            r = requests.post(cls.get_api_url() + 'send', json={
                'api_key': settings.VANDAR_API_KEY,
                'amount': deposit.amount,
                'payerIdentity': str(deposit.user_id),
                'callback_url': callback_url + 'users/wallets/deposit/shetab-callback?gateway=vandar2step',
                'description': uid,
                'factorNumber': uid,
            }, timeout=20)
            r.raise_for_status()
        except:
            print('Exception in Vandar token request!', r.status_code if r is not None else 'None', r.text if r is not None else 'None')
            report_exception()
            return {}
        return r.json()

    @classmethod
    def send_verify_request(cls, deposit):
        """
            Sample verify response: {
                amount: '1000.00',
                cardNumber: '502229******4060',
                description: 'nobitex16346',
                factorNumber: 'nobitex16346',
                message: 'ok',
                mobile: None,
                paymentDate: '2019-07-15 20:44:21',
                status: 1,
                transId: 156320722232
            }
        """
        r = None
        api = settings.VANDAR_API_KEY
        token = getattr(deposit, 'nextpay_id', '0')
        try:
            r = requests.post(cls.get_api_url() + 'verify', json={
                'api_key': api,
                'token': token,
            }, timeout=20)
            r.raise_for_status()
            json_result = r.json()
        except:
            try:
               response_text = str(r.json())
            except:
                response_text = r.text if r is not None else ''
            error_details = '[{}] {}'.format(token, response_text)
            log_event('Vandar Verify API Failed: {}'.format(r.status_code if r is not None else 0), details=error_details,
                      level='warning', module='shetab', category='notice', runner='api')
            deposit.error_message = response_text or 'خطا در اتصال به درگاه'
            report_exception()
            return None
        return {
            'amount': deposit.amount,
            'card_number': json_result.get('cardNumber') or ('1' * 16),
        }

    @classmethod
    def send_get_tx_request(cls, deposit):
        """
           Sample get tx response:  {
              "status": 1,
              "amount": "10000",
              "transId": 155058785697,
              "refnumber": GmshtyjwKSuZXT81+6o9nKIkOcW*****PY05opjBoF,
              "trackingCode": 23***6,
              "factorNumber": null,
              "mobile": null,
              "description": "description",
              "cardNumber": "603799******6299",
              "CID": "ECC1F6931DDC1B8A0892293774836F3FFAC4A3C9D34997405F340FCC1BDDED82",
              "paymentDate": "2019-02-19 18:21:50",
              "message": "Not Verified"
            }
       """
        r = None
        api = settings.VANDAR_API_KEY
        token = getattr(deposit, 'nextpay_id', '0')
        try:
            r = requests.post(cls.get_api_url() + 'transaction', json={
                'api_key': api,
                'token': token,
            }, timeout=20)
            r.raise_for_status()
            json_result = r.json()
        except:
            try:
                response_text = str(r.json())
            except:
                response_text = r.text if r is not None else ''
            error_details = '[{}] {}'.format(token, response_text)
            log_event('Vandar Get Transaction API Failed: {}'.format(r.status_code if r is not None else 0),
                      details=error_details,
                      level='warning', module='shetab', category='notice', runner='api')
            deposit.error_message = response_text or 'خطا در دریافت تراکنش وندار'
            report_exception()
            return None
        return json_result


    @classmethod
    def send_confirm_request(cls, deposit):
        """
           Sample confirm response:   {
              "status": 1,
              "message": "Transaction Confirmed"
           }
        """
        r = None
        api = settings.VANDAR_API_KEY
        token = getattr(deposit, 'nextpay_id', '0')
        try:
            r = requests.post(cls.get_api_url() + 'confirm', json={
                'api_key': api,
                'token': token,
                'confirm': 1
            }, timeout=20)
            r.raise_for_status()
            r = r.json()
        except:
            try:
                response_text = str(r.json())
            except:
                response_text = r.text if r is not None else ''
            error_details = '[{}] {}'.format(token, response_text)
            log_event('Vandar Get Transaction API Failed: {}'.format(r.status_code if r is not None else 0),
                      details=error_details,
                      level='warning', module='shetab', category='notice', runner='api')
            deposit.error_message = response_text or 'خطا در تایید تراکنش وندار'
            report_exception()
            return False

        if not r.get('status', 0):
            return False
        return True


    @classmethod
    def sync(cls, deposit, request, **kwargs):
        from exchange.shetab.models import ShetabDeposit

        if not deposit.pk or not deposit.user or not deposit.amount:
            return
        if deposit.broker != deposit.BROKER.vandar2step:
            return
        if not deposit.is_requested:
            r = cls.send_token_request(deposit, request)
            print(r)
            code = r.get('token')
            deposit.status_code = ShetabDeposit.STATUS.pending_request
            if code and code != '0':
                deposit.status_code = 0
                deposit.nextpay_id = code
            deposit.save(update_fields=['status_code', 'nextpay_id'])
            return

        r = cls.send_get_tx_request(deposit) or {}
        card_number = r.get('cardNumber')
        if not card_number:
            deposit.status_code = ShetabDeposit.STATUS.confirmation_failed
        elif not deposit.check_card_number(card_number=card_number, update_status=False):
            deposit.status_code = 102050
            deposit.error_message = 'به دلیل واریز با کارت بانکی ' \
                                    'که در پروفایل شما تایید نشده، تراکنش ناموفق بوده و مبلغ به حساب شما بازخواهد گشت.'
            deposit.user_card_number = card_number
        elif not cls.send_confirm_request(deposit):
            deposit.status_code = ShetabDeposit.STATUS.confirmation_failed
        else:
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


    @classmethod
    def get_api_redirect_url(cls, deposit):
        return 'https://vandar.io/ipg/2step/{}'.format(deposit.nextpay_id)
