import datetime
from typing import Optional

import requests
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from exchange.accounting.models import DepositSystemBankAccount
from exchange.accounts.models import AdminConsideration, Notification, User
from exchange.base.calendar import ir_now
from exchange.base.logging import log_event, report_exception
from exchange.base.models import Settings
from exchange.base.tasks import run_admin_task
from exchange.features.models import QueueItem
from exchange.features.utils import is_feature_enabled
from exchange.shetab.parsers import parse_bank_swift_name, parse_jibit_deposit_status
from exchange.wallet.models import BankDeposit


class JibitHandler:
    base_address = 'https://api.jibit.ir/ppg/v2/'
    base_address_transfers = 'https://api.jibit.ir/trf/v1/'

    @classmethod
    def get_access_token(cls):
        return cache.get('jibit_access_token') or cls.acquire_access_token()

    @classmethod
    def acquire_access_token(cls):
        # Get new access token from API
        try:
            r = requests.post(cls.base_address + 'tokens/generate', json={
                'apiKey': settings.JIBIT_API_KEY,
                'secretKey': settings.JIBIT_API_SECRET,
            }, timeout=30)
            r.raise_for_status()
            json_result = r.json()
        except:
            report_exception()
            raise ValueError('JibitAPIError')
        # Save access token
        access_token = json_result['accessToken']
        refresh_token = json_result['refreshToken']
        cache.set('jibit_access_token', access_token, 86000)
        cache.set('jibit_refresh_token', refresh_token, 86000)
        return access_token

    @classmethod
    def send_token_request(cls, deposit, request):
        r = None
        uid = 'nobitex{}'.format(deposit.pk)
        callback_url = settings.PROD_API_URL if settings.IS_PROD else request.build_absolute_uri('/')
        try:
            data = {
                'amount': deposit.amount,
                'currency': 'RIALS',
                'referenceNumber': uid,
                'userIdentifier': str(deposit.user_id),
                'callbackUrl': callback_url + '/users/wallets/deposit/shetab-callback?gateway=jibit',
                'description': uid,
            }
            if settings.FORCE_SHETAB_CARD_IN_GATEWAY and deposit.selected_card:
                data['payerCardNumber'] = deposit.selected_card.card_number
                data['forcePayerCardNumber'] = True

            r = requests.post(cls.base_address + 'orders', json=data, headers={
                'Authorization': 'Bearer ' + cls.get_access_token(),
            }, timeout=30)
            r.raise_for_status()
        except:
            print('Exception in Jibit token request!', r.status_code if r is not None else 'None', r.text if r is not None else 'None')
            report_exception()
            return {}
        return r.json()

    @classmethod
    def send_verify_request(cls, deposit, is_retry=False):
        r = None
        access_token = cls.get_access_token()
        try:
            r = requests.get(cls.base_address + 'orders/{}/verify'.format(deposit.nextpay_id), headers={
                'Authorization': 'Bearer ' + access_token,
                'Content-Type': 'application/json',
            }, timeout=30)
            r.raise_for_status()
            response = r.json()
            if response['status'] != 'Successful':
                raise ValueError('Jibit Verify Error')
        except:
            error_details = '[{}] {}'.format(deposit.nextpay_id, r.text if r is not None else '')
            log_event('Jibit Verify API Failed: {}'.format(r.status_code if r is not None else 0),
                      details=error_details, level='warning', module='shetab', category='notice', runner='api')
            deposit.error_message = r.text if r is not None else 'خطا در اتصال به درگاه'
            report_exception()
            return None
        return {
            'amount': deposit.amount,
            'card_number': deposit.user_card_number,
        }

    @classmethod
    def sync(cls, deposit, request, retry=False, **kwargs):
        from exchange.shetab.models import ShetabDeposit

        if not deposit.pk or not deposit.user or not deposit.amount:
            return
        if deposit.broker != deposit.BROKER.jibit:
            return
        # Initial payment creation
        if not deposit.is_requested:
            r = cls.send_token_request(deposit, request)
            code = r.get('orderIdentifier')
            deposit.status_code = ShetabDeposit.STATUS.pending_request
            if code and code != '0':
                deposit.status_code = 0
                deposit.nextpay_id = code
            deposit.save(update_fields=['status_code', 'nextpay_id'])
            return
        # Update already failed requests
        if deposit.status_code == ShetabDeposit.STATUS.confirmation_failed:
            if retry:
                cls.update_failed_deposit(deposit)
            return
        # Verify step
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
                deposit.user_card_number = cls.get_user_card_number(deposit, retries=1)
        deposit.save(update_fields=['status_code', 'user_card_number'])

    @classmethod
    def fetch_deposit_status(cls, deposit):
        try:
            r = requests.get(cls.base_address + 'orders/{}'.format(deposit.nextpay_id), headers={
                'Authorization': 'Bearer ' + cls.get_access_token(),
                'Content-Type': 'application/json',
            }, timeout=50)
            r.raise_for_status()
            return r.json()
        except:
            report_exception()
            return None

    @classmethod
    def get_user_card_number(cls, deposit, retries=0):
        default_card_number = '1' * 16
        response = cls.fetch_deposit_status(deposit)
        if response is None:
            if retries <= 0:
                Notification.notify_admins(
                    f'خطا در دریافت وضعیت واریز شتابی #{deposit.id}',
                    title='💳 جیبیت',
                    channel='operation',
                )
                return default_card_number
            return cls.get_user_card_number(deposit, retries=retries - 1)
        if response['status'] not in ['SUCCESS', 'IN_PROGRESS']:
            return default_card_number
        return response.get('payerCard') or default_card_number

    @classmethod
    def get_api_redirect_url(cls, deposit):
        return cls.base_address + 'orders/{}/payments'.format(deposit.nextpay_id)

    @classmethod
    def update_failed_deposit(cls, deposit):
        updated_fields = []
        response = cls.fetch_deposit_status(deposit)
        status = response['status'] if response else 'TIMEOUT'
        # Set card number if available
        if status in ['SUCCESS', 'IN_PROGRESS']:
            card_number = response.get('payerCard') or ('1' * 16)
            if card_number:
                deposit.user_card_number = card_number
                updated_fields.append('user_card_number')
        if status == 'SUCCESS':
            confirmed_amount = int(response.get('amount') or 0)
            if confirmed_amount == deposit.amount:
                deposit.status_code = 1
                updated_fields.append('status_code')
        if updated_fields:
            deposit.save(update_fields=updated_fields)

    @staticmethod
    def normalize_datetime(value):
        return f'{timezone.datetime.utcfromtimestamp(value.timestamp()).isoformat()}Z' if value else None

    @classmethod
    def fetch_deposits(cls, from_date=None, to_date=None, page=1, size=1000):
        try:
            address = f'orders?page={page}&size={size}'
            if from_date:
                address += f'&from={cls.normalize_datetime(from_date)}'
            if to_date:
                address += f'&to={cls.normalize_datetime(to_date)}'
            r = requests.get(cls.base_address + address, headers={
                'Authorization': 'Bearer ' + cls.get_access_token(),
                'Content-Type': 'application/json',
            }, timeout=50)
            r.raise_for_status()
            return r.json()
        except:
            report_exception()
            return None

    @classmethod
    def fetch_withdraws(cls, from_date=None, to_date=None, page=1, size=100):
        try:
            address = f'transfers/filter?page={page}&size={size}'
            if from_date:
                address += f'&from={cls.normalize_datetime(from_date)}'
            if to_date:
                address += f'&to={cls.normalize_datetime(to_date)}'
            r = requests.get(cls.base_address_transfers + address, headers={
                'Authorization': 'Bearer ' + cls.get_access_token(),
                'Content-Type': 'application/json',
            }, timeout=50)
            r.raise_for_status()
            return r.json()
        except:
            report_exception()
            return None


class JibitHandlerV2:
    base_address = 'https://napi.jibit.ir/ppg/v3/'

    @classmethod
    def get_access_token(cls):
        return cache.get('jibit_ppg_access_token') or cls.acquire_access_token()

    @classmethod
    def acquire_access_token(cls):
        # Get new access token from API
        try:
            r = requests.post(cls.base_address + 'tokens', json={
                'apiKey': settings.JIBIT_PPG_API_KEY,
                'secretKey': settings.JIBIT_PPG_API_SECRET,
            }, timeout=30)
            r.raise_for_status()
            json_result = r.json()
        except:
            report_exception()
            raise ValueError('JibitV2APIError')
        # Save access token
        access_token = json_result['accessToken']
        cache.set('jibit_ppg_access_token', access_token, 86000)
        return access_token

    @classmethod
    def send_token_request(cls, deposit, request):
        r = None
        uid = 'nobitex{}'.format(deposit.pk)
        callback_url = settings.PROD_API_URL if settings.IS_PROD else request.build_absolute_uri('/')
        try:
            data = {
                'amount': deposit.amount,
                'currency': 'IRR',
                'clientReferenceNumber': uid,
                'userIdentifier': str(deposit.user_id),
                'callbackUrl': callback_url + '/users/wallets/deposit/shetab-callback?gateway=jibit_v2',
                'description': uid,
            }
            if settings.FORCE_SHETAB_CARD_IN_GATEWAY and deposit.selected_card:
                data['payerCardNumber'] = deposit.selected_card.card_number
            if deposit.user.has_verified_mobile_number:
                data['payerMobileNumber'] = deposit.user.mobile

            r = requests.post(cls.base_address + 'purchases', json=data, headers={
                'Authorization': 'Bearer ' + cls.get_access_token(),
            }, timeout=30)
            r.raise_for_status()
        except:
            print('Exception in Jibit V2 token request!', r.status_code if r is not None else 'None', r.text if r is not None else 'None')
            report_exception()
            return {}
        return r.json()

    @classmethod
    def send_verify_request(cls, deposit, is_retry=False):
        r = None
        try:
            r = requests.get(cls.base_address + f'purchases/{deposit.nextpay_id}/verify', headers={
                'Authorization': 'Bearer ' + cls.get_access_token(),
            }, timeout=30)
            r.raise_for_status()
            response = r.json()
            if response['status'] != 'SUCCESSFUL':
                raise ValueError('Jibit V2 Verify Error')
        except:
            error_details = '[{}] {}'.format(deposit.nextpay_id, r.text if r is not None else '')
            log_event(
                f'Jibit V2 Verify API Failed: {r.status_code if r is not None else 0}',
                details=error_details,
                level='warning',
                module='shetab',
                category='notice',
                runner='api',
            )
            deposit.error_message = r.text if r is not None else 'خطا در اتصال به درگاه'
            report_exception()
            return False
        return True

    @classmethod
    def sync(cls, deposit, request, retry=False, **kwargs):
        from exchange.shetab.models import ShetabDeposit

        if not deposit.pk or not deposit.user or not deposit.amount:
            return
        if deposit.broker != deposit.BROKER.jibit_v2:
            return
        # Initial payment creation
        if not deposit.is_requested:
            response = cls.send_token_request(deposit, request)
            code = response.get('purchaseId')
            deposit.status_code = ShetabDeposit.STATUS.pending_request
            if code and code != '0':
                deposit.status_code = 0
                deposit.nextpay_id = code
            deposit.save(update_fields=['status_code', 'nextpay_id'])
            return
        # Update already failed requests
        if deposit.status_code == ShetabDeposit.STATUS.confirmation_failed:
            if retry:
                cls.update_failed_deposit(deposit)
            return
        # Verify step
        response = cls.fetch_deposit_status(deposit) or {}
        if response.get('state') == 'READY_TO_VERIFY':
            verified = cls.send_verify_request(deposit)
            if verified:
                response = cls.fetch_deposit_status(deposit) or {}
        if response.get('state') in ('FAILED', 'EXPIRED', 'REVERSED'):
            deposit.status_code = ShetabDeposit.STATUS.confirmation_failed
        elif response.get('state') == 'SUCCESS':
            if int(response.get('amount')) != deposit.amount:
                deposit.status_code = ShetabDeposit.STATUS.amount_mismatch
            else:
                deposit.status_code = deposit.STATUS.pay_success
                deposit.user_card_number = response.get('pspMaskedCardNumber')
        # else leave status_code unchanged. left states: UNKNOWN, IN_PROGRESS
        deposit.save(update_fields=['status_code', 'user_card_number'])

    @classmethod
    def fetch_deposit_status(cls, deposit):
        try:
            r = requests.get(cls.base_address + 'purchases', params={
                'purchaseId': deposit.nextpay_id,
            }, headers={
                'Authorization': 'Bearer ' + cls.get_access_token(),
            }, timeout=50)
            r.raise_for_status()
            return r.json()['elements'][0]
        except:
            report_exception()
            return None

    @classmethod
    def get_user_card_number(cls, deposit, retries=0):
        default_card_number = '1' * 16
        response = cls.fetch_deposit_status(deposit)
        if response is None:
            if retries <= 0:
                Notification.notify_admins(
                    f'خطا در دریافت وضعیت واریز شتابی #{deposit.id}',
                    title='💳 جیبیت',
                    channel='operation',
                )
                return default_card_number
            return cls.get_user_card_number(deposit, retries=retries - 1)
        if response['state'] not in ['SUCCESS', 'IN_PROGRESS']:
            return default_card_number
        return response.get('pspMaskedCardNumber') or default_card_number

    @classmethod
    def get_api_redirect_url(cls, deposit):
        return cls.base_address + 'purchases/{}/payments'.format(deposit.nextpay_id)

    @classmethod
    def update_failed_deposit(cls, deposit):
        updated_fields = []
        response = cls.fetch_deposit_status(deposit)
        state = response['state'] if response else 'TIMEOUT'
        # Set card number if available
        if state in ['SUCCESS', 'IN_PROGRESS']:
            card_number = response.get('pspMaskedCardNumber') or ('1' * 16)
            if card_number:
                deposit.user_card_number = card_number
                updated_fields.append('user_card_number')
        if state == 'SUCCESS':
            confirmed_amount = int(response.get('amount') or 0)
            if confirmed_amount == deposit.amount:
                deposit.status_code = 1
                updated_fields.append('status_code')
        if updated_fields:
            deposit.save(update_fields=updated_fields)

    @staticmethod
    def normalize_datetime(value):
        return value.astimezone(datetime.timezone.utc).isoformat().replace('+00:00', 'Z') if value else None

    @classmethod
    def fetch_deposits(cls, from_date=None, to_date=None, page=1, size=250):
        try:
            params = {
                'page': page,
                'size': size,
                'from': cls.normalize_datetime(from_date),
                'to': cls.normalize_datetime(to_date),
            }
            r = requests.get(cls.base_address + 'purchases', params=params, headers={
                'Authorization': 'Bearer ' + cls.get_access_token(),
            }, timeout=50)
            r.raise_for_status()
            return r.json()
        except:
            report_exception()
            return None


class JibitPip:
    base_address = 'https://napi.jibit.ir/pip/v1/'
    LIMITATION_LEVEL_ONE = 100_000_000_0
    LIMITATION_LEVEL_TWO = 200_000_000_0
    LIMITATION_LEVEL_THREE = 500_000_000_0
    LIMITATION_LEVEL_FOUR = 5_000_000_000_0

    @classmethod
    def get_access_token(cls):
        return cache.get('jibit_pip_access_token') or cls.acquire_access_token()

    @classmethod
    def acquire_access_token(cls):
        try:
            r = requests.post(cls.base_address + 'tokens/generate', json={
                'apiKey': settings.JIBIT_PIP_API_KEY,
                'secretKey': settings.JIBIT_PIP_API_SECRET,
            }, timeout=30)
            r.raise_for_status()
            json_result = r.json()
        except:
            report_exception()
            raise ValueError('JibitAPIError')
        # Save access token
        access_token = json_result['accessToken']
        refresh_token = json_result['refreshToken']
        cache.set('jibit_pip_access_token', access_token, 86000)
        cache.set('jibit_pip_refresh_token', refresh_token, 86000)
        return access_token

    @classmethod
    def get_payment_id(cls, bank_account, account_type: Optional[int] = None):
        """
        Retrieves or creates a payment ID for a specified bank account and account type.
        Documentation: https://napi.jibit.ir/pip/swagger-ui.html#/payment-id-controller
        Updated to support choosing the type of payment ID (1403/09/09)
        """

        from exchange.shetab.models import JibitAccount, JibitPaymentId

        if account_type is None:
            account_type = JibitAccount.ACCOUNT_TYPES.jibit

        if not settings.IS_PROD:
            result = {
                'payId': f'test_nobitex_jibit_{bank_account.id}',
                'destinationBank': 'BKMTIR',
                'destinationIban': 'IR760120000000007565000016',
                'destinationDepositNumber': '7565000016',
                'destinationOwnerName': 'راهکار فناوری نویان',
            }
            if account_type == JibitAccount.ACCOUNT_TYPES.jibit:
                result['payId'] = f'test_jibit_{bank_account.id}'
                result['destinationIban'] = 'IR760120020000008992439961'
                result['destinationDepositNumber'] = '8992439961'
                result['destinationOwnerName'] = 'ايوان رايان پيام'
            return result

        r = None
        access_token = cls.get_access_token()
        try:
            r = requests.post(
                url=f'{cls.base_address}paymentIds',
                json=cls.prepare_create_payment_id_data(bank_account, account_type),
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=30,
            )
            if r.status_code == 400 and 'duplicate' in r.text:
                r = requests.get(
                    url=f'{cls.base_address}paymentIds/'
                    f'{JibitPaymentId.get_reference_number(bank_id=bank_account.id)}',
                    headers={'Authorization': f'Bearer {access_token}'},
                    timeout=30,
                )
            r.raise_for_status()
        except:
            error_details = '[{}] {}'.format(bank_account.shaba_number, r.text if r is not None else '')
            log_event(
                f'JibitPaymentError: {r.status_code if r is not None else 0}',
                details=error_details,
                level='warning',
                module='shetab',
                category='notice',
                runner='api',
            )
            return None
        return r.json()

    @classmethod
    def prepare_create_payment_id_data(cls, bank_account, account_type: int) -> dict:
        from exchange.shetab.models import JibitAccount, JibitPaymentId
        callback_url_base = settings.PROD_API_URL if settings.IS_PROD else settings.TESTNET_API_URL
        data = {
            'merchantReferenceNumber': JibitPaymentId.get_reference_number(bank_account.id, account_type),
            'callbackUrl': callback_url_base + 'users/payments/callback',
            'userFullName': bank_account.owner_name,
            'userIban': bank_account.shaba_number,
            'userMobile': bank_account.user.mobile,
        }
        if account_type == JibitAccount.ACCOUNT_TYPES.nobitex_jibit:
            data['forcedDestinationIban'] = Settings.get_value(
                'ideposit_nobitex_destination_iban', 'IR760120000000007565000016'
            )
        return data

    @classmethod
    def deposit_verify(cls, external_reference_number):
        r = None
        access_token = cls.get_access_token()
        try:
            r = requests.get(f'{cls.base_address}payments/{external_reference_number}/verify', headers={
                'Authorization': 'Bearer ' + access_token,
                'Content-Type': 'application/json',
            }, timeout=30)
            r.raise_for_status()
            response = r.json()
            if response.get('externalReferenceNumber') != external_reference_number:
                return None
            return response
        except:
            error_details = '[{}] {}'.format(external_reference_number, r.text if r is not None else '')
            log_event('Jibit deposit verify API Failed: {}'.format(r.status_code if r is not None else 0),
                      details=error_details, level='warning', module='shetab', category='notice', runner='api')
            return None

    @classmethod
    def get_waiting_for_verify(cls, page=0):
        r = None
        access_token = cls.get_access_token()
        try:
            r = requests.get(f'{cls.base_address}payments/waitingForVerify?page={page}&size=100', headers={
                'Authorization': 'Bearer ' + access_token,
                'Content-Type': 'application/json',
            }, timeout=30)
            r.raise_for_status()
            return r.json()
        except:
            error_details = '[{}] {}'.format('get_waiting_for_verify', r.text if r is not None else '')
            log_event('Jibit waiting for verify API Failed: {}'.format(r.status_code if r is not None else 0),
                      details=error_details, level='warning', module='shetab', category='notice', runner='cron')
            return None

    @classmethod
    def parse_destination_account(cls, response, account_type: int):
        """ Create a JibitAccount object based on Jibit API response
        """
        from exchange.shetab.models import JibitAccount
        dst_bank = parse_bank_swift_name(response.get('destinationBank'))
        dst_iban = response.get('destinationIban')
        dst_account_number = response.get('destinationDepositNumber')
        dst_owner_name = response.get('destinationOwnerName')
        if not dst_iban:
            return None
        jibit_account = cls.get_jibit_account_by_iban(dst_iban)
        if not jibit_account:
            jibit_account = JibitAccount.objects.create(
                bank=dst_bank,
                iban=dst_iban,
                account_number=dst_account_number,
                owner_name=dst_owner_name,
                account_type=account_type,
            )
        return jibit_account

    @classmethod
    def get_jibit_account_by_iban(cls, iban: str):
        from exchange.shetab.models import JibitAccount

        return JibitAccount.objects.filter(iban=iban).first()

    @classmethod
    def create_or_update_jibit_payment(cls, response):
        """ Update status of corresponding JibitDeposit based on Jibit API response
        """
        from exchange.shetab.models import JibitDeposit, JibitPaymentId

        # Find user payment ID
        payment_id = response.get('paymentId')
        jibit_account = cls.get_jibit_account_by_iban(response.get('destinationAccountIdentifier'))
        # Find user payment ID
        payment_id = JibitPaymentId.objects.filter(
            payment_id=payment_id,
            jibit_account=jibit_account,
        ).first()
        if not payment_id:
            return False, 'InvalidPaymentId'

        # Find existing deposit object
        external_reference_number = response.get('externalReferenceNumber')
        deposit = JibitDeposit.objects.filter(
            payment_id=payment_id, external_reference_number=external_reference_number,
        ).first()

        # Only update status for existing deposits
        status = parse_jibit_deposit_status(response.get('status'), required=True)
        if deposit:
            if deposit.status in JibitDeposit.STATUSES_FINAL:
                # Not changing already finalized deposits
                return True, None
            if status in JibitDeposit.STATUSES_ACCEPTABLE:
                verify_response = cls.deposit_verify(external_reference_number)
                if not verify_response:
                    return False, 'VerifyUnavailable'
                is_valid = all([
                    verify_response.get('status') == 'SUCCESSFUL',
                    verify_response.get('paymentId') == payment_id.payment_id,
                    int(verify_response.get('amount') or 0) == deposit.amount,
                ])
                if not is_valid:
                    deposit.status = JibitDeposit.STATUS.FAILED
                    deposit.bank_deposit.confirmed = False
                    deposit.bank_deposit.status = deposit.bank_deposit.STATUS.rejected
                    with transaction.atomic():
                        deposit.bank_deposit.save(update_fields=['confirmed', 'status'])
                        deposit.save(update_fields=['status'])
                    return False, 'VerifyFailed'
                # Successful & valid, confirm deposit and bank deposit
                deposit.status = JibitDeposit.STATUS.SUCCESSFUL
                with transaction.atomic():
                    deposit.save(update_fields=['status'])
                    cls.update_bank_deposit_status(deposit.bank_deposit)
                return True, None
            return True, None

        # Create objects for new deposits
        amount = response.get('amount')
        bank_reference_number = response.get('bankReferenceNumber')
        raw_bank_timestamp = response.get('rawBankTimestamp')
        dst_account = DepositSystemBankAccount.objects.filter(
            iban_number=payment_id.jibit_account.iban,
        ).first()
        if not external_reference_number:
            return False, 'InvalidReferenceNumber'
        with transaction.atomic():
            deposit = JibitDeposit.objects.create(
                payment_id=payment_id,
                status=JibitDeposit.STATUS.IN_PROGRESS,
                amount=int(amount),
                external_reference_number=external_reference_number,
                bank_reference_number=bank_reference_number,
                raw_bank_timestamp=raw_bank_timestamp,
            )
            bank_deposit = BankDeposit.objects.create(
                user=payment_id.bank_account.user,
                receipt_id=deposit.bank_reference_number,
                src_bank_account=payment_id.bank_account,
                dst_bank_account=payment_id.jibit_account.iban,
                dst_system_account=dst_account,
                deposited_at=deposit.created_at,  # TODO: This should be real deposit time
                amount=deposit.amount,
                fee=deposit.amount * settings.JIBIT_PIP_FEE_RATE,
            )
            deposit.bank_deposit = bank_deposit
            deposit.save(update_fields=['bank_deposit'])
        if not Settings.is_disabled('detect_bank_deposit_for_fraud'):
            transaction.on_commit(
                lambda: run_admin_task('detectify.check_bank_deposit_fraud', deposit_id=bank_deposit.pk)
            )
        if status in JibitDeposit.STATUSES_ACCEPTABLE:
            cls.create_or_update_jibit_payment(response)
        return True, None

    @classmethod
    def update_bank_deposit_status(cls, bank_deposit: BankDeposit) -> bool:
        """Confirm and update the status of a bank deposit for eligible deposits.

        Update will be skipped if any of these conditions is true:
        - Very large deposits (over 1B)
        - Users without "jibit_pip" feature flag
        - Users without level 1 KYC or with uncommon user type
        - Users with total daily Jibit deposit exceeding their level limit

        Confirmed deposits' status will be set to "confirmed" and an AdminConsideration record is added.
        """
        from exchange.shetab.models import JibitDeposit

        if bank_deposit.amount >= 1_000_000_000_0:
            return False  # ignore very large deposits
        if not is_feature_enabled(bank_deposit.user, QueueItem.FEATURES.jibit_pip):
            return False  # ignore users without the feature flag

        # Check user LYC level
        user_type = bank_deposit.user.user_type
        if user_type < User.USER_TYPE_LEVEL1:
            return False  # ignore users without level1 KYC
        elif user_type == User.USER_TYPE_LEVEL1:
            amount_limitation = cls.LIMITATION_LEVEL_ONE
        elif user_type == User.USER_TYPE_LEVEL2:
            amount_limitation = cls.LIMITATION_LEVEL_TWO
        elif user_type == User.USER_TYPE_LEVEL3:
            amount_limitation = cls.LIMITATION_LEVEL_THREE
        elif user_type >= User.USER_TYPE_LEVEL4:
            amount_limitation = cls.LIMITATION_LEVEL_FOUR
        else:
            return False  # Other user types are unexpected and should not be auto processed

        # Check total JibitDeposits of the user in current day
        start_of_day = ir_now().replace(hour=0, minute=0, second=0, microsecond=0)
        todays_total_bank_deposit_amount = (
            JibitDeposit.objects.filter(
                bank_deposit__user=bank_deposit.user,
                bank_deposit__created_at__gte=start_of_day,
            ).aggregate(total=Sum('bank_deposit__amount'))['total']
            or 0
        )
        if todays_total_bank_deposit_amount > amount_limitation:
            return False  # Jibit deposit limit reached

        # Confirm the deposit
        bank_deposit.confirmed = True
        bank_deposit.status = BankDeposit.STATUS.confirmed
        bank_deposit.save(update_fields=['confirmed', 'status'])
        content_type = ContentType.objects.get(model='bankdeposit')
        AdminConsideration.objects.create(
            admin_user=User.get_generic_system_user(),
            user=bank_deposit.user,
            content_type=content_type,
            object_id=bank_deposit.id,
            consideration='تایید شده',
        )
        return True

    @staticmethod
    def normalize_datetime(value):
        return value.strftime("%Y-%m-%d") if value else ''

    @classmethod
    def fetch_deposits(cls, from_date=None, to_date=None, page=1, size=50):
        try:
            params = {
                'fromDate': cls.normalize_datetime(from_date),
                'toDate': cls.normalize_datetime(to_date),
                'pageSize': str(size),
                'pageNumber': str(page),
            }
            headers = {
                'Authorization': 'Bearer ' + cls.get_access_token(),
            }
            r = requests.get(cls.base_address + 'payments/list', params=params, headers=headers, timeout=50)
            r.raise_for_status()
            return r.json()
        except:
            report_exception()
            return None
