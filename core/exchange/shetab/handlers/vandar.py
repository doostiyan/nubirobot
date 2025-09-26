from typing import Optional

import requests
from django.conf import settings

from exchange.accounts.models import BankAccount, Confirmed, User
from exchange.base.logging import log_event, report_exception
from exchange.wallet.models import BankDeposit
from exchange.wallet.settlement import BaseVandarV3


class VandarException(Exception):
    pass


class VandarHandler:
    @classmethod
    def get_api_url(cls):
        api_url = 'https://ipg.vandar.io/api/v3/'
        if not settings.IS_PROD:
            api_url += 'test/'
        return api_url

    @classmethod
    def send_token_request(cls, deposit, request):
        r = None
        uid = 'nobitex{}'.format(deposit.pk)
        valid_bank_cards = [deposit.selected_card.card_number]
        valid_bank_cards += [
            bank_card.card_number
            for bank_card in deposit.user.bank_cards.filter(confirmed=True)
            .exclude(
                card_number=deposit.selected_card.card_number,
            )
            .order_by('-created_at')[:9]
        ]

        try:
            r = requests.post(
                cls.get_api_url() + 'send',
                json={
                    'api_key': settings.VANDAR_API_KEY,
                    'amount': deposit.amount,
                    'payerIdentity': str(deposit.user_id),
                    'callback_url': 'https://api.nobitex1.ir/users/wallets/deposit/shetab-callback?gateway=vandar',
                    'description': uid,
                    'factorNumber': uid,
                    'valid_card_number': valid_bank_cards,
                },
                proxies=settings.DEFAULT_PROXY,
                timeout=20,
            )
            r.raise_for_status()
        except:
            print('Exception in Vandar token request!', r.status_code if r else 'None', r.text if r else 'None')
            report_exception()
            return {}
        return r.json()

    @classmethod
    def send_verify_request(cls, deposit):
        """
            Sample verify response: {amount: '1000.00', cardNumber: '502229******4060', description: 'nobitex16346', factorNumber: 'nobitex16346', message: 'ok', mobile: None, paymentDate: '2019-07-15 20:44:21', status: 1, transId: 156320722232}
        """
        r = None
        api = settings.VANDAR_API_KEY
        token = getattr(deposit, 'nextpay_id', '0')
        try:
            r = requests.post(cls.get_api_url() + 'verify', json={
                'api_key': api,
                'token': token,
            }, proxies=settings.DEFAULT_PROXY, timeout=20)
            json_result = r.json()
            verify_status = json_result.get('status')
            if verify_status != 1:
                return None
            r.raise_for_status()
        except:
            response_text = r.text if r is not None else ''
            error_details = '[{}] {}'.format(token, response_text)
            log_event('Vandar Verify API Failed: {}'.format(r.status_code if r is not None else 0),
                      details=error_details,
                      level='warning', module='shetab', category='notice', runner='api')
            deposit.error_message = response_text or 'خطا در اتصال به درگاه'
            report_exception()
            return None
        return {
            'amount': deposit.amount,
            'card_number': json_result.get('cardNumber') or ('1' * 16),
        }

    @classmethod
    def sync(cls, deposit, request, **kwargs):
        from exchange.shetab.models import ShetabDeposit

        if not deposit.pk or not deposit.user or not deposit.amount:
            return
        if deposit.broker != deposit.BROKER.vandar:
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
            code = r.get('token')
            deposit.status_code = ShetabDeposit.STATUS.pending_request
            if code and code != '0':
                deposit.status_code = 0
                deposit.nextpay_id = code
            deposit.save(update_fields=['status_code', 'nextpay_id'])

    @classmethod
    def get_api_redirect_url(cls, deposit):
        vandar_ipg_url = 'https://ipg.vandar.io/v3/'
        if not settings.IS_PROD:
            vandar_ipg_url += 'test/'
        return vandar_ipg_url + str(deposit.nextpay_id)


class VandarP2P(BaseVandarV3):
    @classmethod
    def _fetch_transactions(cls, start_date, end_date, page, size, **extra_params):
        try:
            params = {
                'page': page,
                'per_page': size,
                'fromDate': cls.normalize_datetime(start_date),
                'toDate': cls.normalize_datetime(end_date),
                'channel': 'cash-in-by-code',
                'status': 'succeed',
                **extra_params
            }
            response = requests.get(cls.API_URL + f'business/{cls.BUSINESS_NAME}/transaction', params=params, headers={
                'Authorization': f'Bearer {cls.get_token()}',
            }, timeout=60)
            response.raise_for_status()
            transactions = response.json().get('data', [])
        except:
            report_exception()
            transactions = []
        return transactions

    @classmethod
    def fetch_deposits(cls, start_date, end_date, page=1, size=100):
        extra_params = {'statusKind': 'transactions'}
        return cls._fetch_transactions(start_date, end_date, page, size, **extra_params)

    @classmethod
    def get_bank_account(cls, payment_number: str) -> Optional[BankAccount]:
        return BankAccount.vandar_objects.filter(
            bank_id=BankAccount.BANK_ID.vandar,
            vandarpaymentid__payment_id=payment_number,
            is_deleted=False,
            is_temporary=False,
            confirmed=True,
        ).first()

    @classmethod
    def get_or_create_payment(cls, response) -> Optional[BankDeposit]:
        from exchange.accounts.userlevels import UserLevelManager

        payment_account = cls.get_bank_account(response.get('payment_number', None))
        if not payment_account:
            return None
        if not UserLevelManager.is_user_eligible_for_vandar_deposit(payment_account.user):
            return None

        amount = response.get('amount', 0) * 10
        deposit, _ = BankDeposit.objects.get_or_create(
            user=payment_account.user,
            receipt_id=response.get('tracking_code'),
            amount=amount,
            src_bank_account=payment_account,
            dst_bank_account=cls.BUSINESS_NAME,
            deposited_at=cls.parse_datetime(response.get('payment_date')),
            fee=min(settings.VANDAR_DEPOSIT_FEE_RATE * amount, settings.VANDAR_DEPOSIT_FEE_MAX),
        )
        return deposit

    @classmethod
    def get_balance(cls):
        balance_url = 'https://api.vandar.io/v2/'
        try:
            response = requests.get(balance_url + f'business/{cls.BUSINESS_NAME}/balance', headers={
                'Authorization': f'Bearer {cls.get_token()}',
            }, timeout=60)
            response.raise_for_status()
            response = response.json()
            balance = response['data']['wallet']
        except:
            report_exception()
            return None
        return balance

    @classmethod
    def get_or_create_vandar_account(cls, user: User):
        from exchange.shetab.models import VandarAccount

        vandar_account = VandarAccount.objects.filter(user=user).first()
        if vandar_account:
            return vandar_account

        try:
            if user.is_company_user:
                data = {
                    'type': 'LEGAL',
                    'agent_mobile': user.mobile,
                    'legal_national_code': user.national_code,
                }
            else:
                data = {
                    'type': 'INDIVIDUAL',
                    'mobile': user.mobile,
                    'individual_national_code': user.national_code,
                }

            response = requests.post(cls.API_V2_URL + f'business/{cls.BUSINESS_NAME}/customers', json=data, headers={
                'Authorization': f'Bearer {cls.get_token()}',
            }, timeout=60)
            response.raise_for_status()
            result = response.json()
            if int(result['status']) != 1:
                raise VandarException(f'Cannot create vandar customer with reason: {result["message"]}')

            customer_id = result['result']['customer']['id']
            vandar_account = VandarAccount.objects.create(user=user, uuid=customer_id)
        except:
            report_exception()
            raise

        return vandar_account

    @classmethod
    def get_or_create_payment_id(cls, vandar_account):
        from exchange.shetab.models import VandarPaymentId

        vandar_payment_id = VandarPaymentId.objects.filter(vandar_account=vandar_account).first()
        if vandar_payment_id:
            return vandar_payment_id

        try:
            response = requests.post(
                cls.API_V2_URL + f'business/{cls.BUSINESS_NAME}/customers/{vandar_account.uuid}/cash-in-code',
                headers={
                    'Authorization': f'Bearer {cls.get_token()}',
                },
                timeout=60,
            )
            response.raise_for_status()
            result = response.json()
            if int(result['status']) != 1:
                raise VandarException(f'Cannot create vandar payment id with reason: {result["message"]}')

            payment_id = result['code']
            vandar_payment_id = VandarPaymentId.objects.create(
                vandar_account=vandar_account,
                bank_account=BankAccount.objects.create(
                    user=vandar_account.user, bank_id=BankAccount.BANK_ID.vandar, account_number=settings.VANDAR_ID_DEPOSIT_PREFIX,
                    confirmed=True, status=Confirmed.STATUS.confirmed,
                ),
                payment_id=payment_id,
            )
        except:
            report_exception()
            raise

        return vandar_payment_id
