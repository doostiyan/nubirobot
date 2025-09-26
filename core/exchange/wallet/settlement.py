import json
import math
import time
import datetime
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from model_utils import Choices

from exchange.accounting.models import SystemBankAccount
from exchange.accounts.models import BankAccount
from exchange.base import calendar
from exchange.base.logging import log_event, report_exception
from exchange.base.models import Currencies, Settings
from exchange.shetab.errors import TomanAuthenticateError, TomanClientError
from exchange.shetab.handlers.toman import TomanClient
from exchange.wallet.models import WithdrawRequest


def withdraw_set_going_to_send(withdraw):
    if not withdraw.is_accepted:
        raise ValueError('Only accepted requests can be settled')
    if withdraw.wallet.currency != Currencies.rls:
        raise ValueError('Settlement is only available for Rial withdrawals')
    if withdraw.updates:
        raise ValueError('AlreadySettled')
    if withdraw.is_internal:
        raise ValueError('InternalTransfer')
    # Change state to manual_accepted to prevent cancellation by user
    with transaction.atomic():
        withdraw.status = withdraw.STATUS.manual_accepted
        withdraw.save(update_fields=['status'])
        withdraw.create_transaction()
    if not withdraw.transaction or not withdraw.transaction.pk or withdraw.transaction.amount != -withdraw.amount:
        raise ValueError('Withdraw transaction is not valid')


def withdraw_cancel_sending(withdraw):
    withdraw.status = withdraw.STATUS.accepted
    withdraw.save(update_fields=['status'])


def pay_get_token(withdraw):
    try:
        # Get token
        r = requests.post('https://pay.ir/api/v1/authenticate', data={
            'mobile': settings.PAY_IR_USERNAME,
            'password': settings.PAY_IR_PASSWORD,
        }, proxies=settings.DEFAULT_PROXY, timeout=10)
        r.raise_for_status()
        r = r.json()
        if r.get('status') != 1 or not r.get('token'):
            raise ValueError('API error in Pay.ir settlement - token request')
        time.sleep(0.5)
        return r['token']
    except:
        withdraw_cancel_sending(withdraw)
        report_exception()
        raise


def settle_using_payir(withdraw, options=None):
    withdraw_set_going_to_send(withdraw)

    # Check for duplicated settlement
    cashout_id = None
    try:
        r = requests.post('https://pay.ir/api/v1.2/cashout/track?token={}'.format(pay_get_token(withdraw)), data={
            'uid': withdraw.pk,
        }, proxies=settings.DEFAULT_PROXY, timeout=5)
        r.raise_for_status()
        r = r.json()
        if r['status'] == 1:
            cashout_id = r['data']['cashout_id']
    except:
        report_exception()
        raise ValueError('API error in Pay.ir settlement - CashoutRecheckFailed')
    if cashout_id:
        # This is sent, so sent status is ok for this request object
        raise ValueError('Request with uid {} already exist! - duplicated cashout'.format(withdraw.pk))
    time.sleep(0.5)

    # Send settlement request (cashout)
    net_amount = int(withdraw.amount) - withdraw.calculate_fee()
    r = requests.post('https://pay.ir/api/v1.2/cashout/request?token={}'.format(pay_get_token(withdraw)), data={
        'amount': net_amount,
        'name': withdraw.target_account.owner_name,
        'sheba': withdraw.target_account.shaba_number[2:],
        'uid': withdraw.pk,
    }, proxies=settings.DEFAULT_PROXY, timeout=30)
    r.raise_for_status()
    r = r.json()
    if r.get('status') != 1 or not r.get('data'):
        raise ValueError('API error in Pay.ir settlement - cashout request')

    # Mark as withdraw from Pay system account
    try:
        system_bank_account = SystemBankAccount.objects.get(account_number='PAYIR')
    except SystemBankAccount.DoesNotExist:
        system_bank_account = None

    # Finalize
    data = r['data']
    cashout_id = data.get('cashout_id', 0)
    withdraw.status = withdraw.STATUS.sent
    withdraw.updates = (withdraw.updates or '') + str(data)
    withdraw.blockchain_url = 'nobitex://app/wallet/rls/transaction/WP{}'.format(cashout_id)
    withdraw.withdraw_from = system_bank_account
    withdraw.save(update_fields=['status', 'updates', 'blockchain_url', 'withdraw_from'])
    return data


class BaseSettlement:
    def __init__(self, withdraw):
        self.withdraw: WithdrawRequest = withdraw
        self.uid = str(self.withdraw.pk)

    @property
    def net_amount(self):
        return int(self.withdraw.amount) - int(self.withdraw.calculate_fee())

    def start_settlement(self):
        withdraw_set_going_to_send(self.withdraw)

    def abort(self):
        withdraw_cancel_sending(self.withdraw)

    def get_token(self):
        raise NotImplementedError

    def do_settle(self):
        raise NotImplementedError

    def get_info(self):
        raise NotImplementedError

    def update_status(self, update_all=False):
        raise NotImplementedError


class JibitSettlement(BaseSettlement):
    API_URL = 'https://api.jibit.ir/trf/v1/'

    @staticmethod
    def get_token():
        from exchange.shetab.handlers.jibit import JibitHandler
        return JibitHandler.get_access_token()

    def do_settle(self, options=None):
        # Options
        options = options or {}
        cancellable = options.get('cancellable', True)
        transfer_mode = options.get('transfer_mode', 'ACH')
        submission_mode = options.get('submission_mode', 'BATCH')

        access_token = self.get_token()
        self.start_settlement()

        # Send request
        r = requests.post(self.API_URL + 'transfers', json={
            'batchID': self.uid,
            'submissionMode': submission_mode,
            'transfers': [{
                'transferID': self.uid,
                'transferMode': 'NORMAL' if transfer_mode == 'instant' else 'ACH',
                'destination': self.withdraw.target_account.shaba_number,
                'destinationFirstName': self.withdraw.target_account.user.first_name,
                'destinationLastName': self.withdraw.target_account.user.last_name,
                'amount': self.net_amount,
                'currency': 'RIALS',
                'description': 'واریز {} از نوبیتکس'.format(self.withdraw.pk),
                'cancellable': cancellable,
            }],
        }, headers={
            'Authorization': 'Bearer ' + access_token,
        }, timeout=30)

        # Process response
        log_event(
            'Jibit Settlement - {}: {}'.format(submission_mode, r.status_code if r is not None else '0'), level='info',
            module='settlement', category='general', runner='admin', details=r.text if r is not None else 'None')

        settlement_data = {
            "withdraw": self.withdraw.pk,
            "destination": self.withdraw.target_account.shaba_number,
            "destinationFirstName": self.withdraw.target_account.user.first_name,
            "destinationLastName": self.withdraw.target_account.user.last_name,
            "amount": self.net_amount,
            "transferMode": 'NORMAL' if transfer_mode == 'instant' else 'ACH',
            "submissionMode": submission_mode,
            "cancellable": cancellable,
            "batchID": self.uid,
            "responseStatusCode": r.status_code if r is not None else 0,
            "responseText": r.text if r is not None else 'None'
        }
        log_event(
            'Jibit Settlement Details - withdraw:{}'.format(self.withdraw.pk),
            level='info', module='settlement', category='history', runner='admin', details=json.dumps(settlement_data))

        r.raise_for_status()
        r = r.json()
        if not r.get('submittedCount') or r['submittedCount'] != 1:
            raise ValueError('API error in Jibit settlement - cashout request')

        # Mark as withdraw from Jibit system account
        try:
            system_bank_account = SystemBankAccount.objects.get(account_number='JIBIT')
        except SystemBankAccount.DoesNotExist:
            system_bank_account = None

        # Finalize
        self.withdraw.status = self.withdraw.STATUS.sent
        self.withdraw.updates = (self.withdraw.updates or '') + str(r)
        self.withdraw.blockchain_url = 'nobitex://app/wallet/rls/transaction/WJ{}'.format(self.uid)
        self.withdraw.withdraw_from = system_bank_account
        self.withdraw.save(update_fields=['status', 'updates', 'blockchain_url', 'withdraw_from'])
        return self.uid

    def get_info(self):
        """ Fetch latest Jibit data for this settlement
        """
        r = requests.get(JibitSettlement.API_URL + 'transfers', params={
            'transferID': self.uid,
        }, headers={
            'Authorization': 'Bearer ' + JibitSettlement.get_token(),
        }, timeout=30)
        r.raise_for_status()
        transfers = r.json().get('transfers') or []
        if not transfers:
            return {}
        return transfers[0]

    def update_status(self, update_all=False):
        """ Update bank payment status for the withdraw
        """
        if not settings.IS_PROD:
            return
        info = self.get_info()
        if not info:
            return
        state = info.get('state')
        mode = info.get('transferMode')
        bank_id = info.get('bankTransferID')
        status_url = 'nobitex://withdraw/{}-{}/WJ{}'.format(
            mode or 'ACH',
            state or 'NEW',
            bank_id or self.uid,
        )
        if self.withdraw.blockchain_url != status_url:
            self.withdraw.blockchain_url = status_url
            self.withdraw.save(update_fields=['blockchain_url'])

    @staticmethod
    def normalize_datetime(value):
        return f'{timezone.datetime.utcfromtimestamp(value.timestamp()).isoformat()}Z' if value else None

    @classmethod
    def get_transfers_by_date(cls, start_date, end_date, count):
        response = requests.get(
            cls.API_URL + f'transfers/filter',
            params={
                'state': 'TRANSFERRED',
                'page': 1,
                'size': count,
                'from': cls.normalize_datetime(start_date),
                'to': cls.normalize_datetime(end_date),
            },
            headers={'Authorization': 'Bearer ' + cls.get_token()}, timeout=30)
        transfers = response.json().get('elements', [])

        return transfers


class JibitSettlementV2(BaseSettlement):
    API_URL = 'https://napi.jibit.ir/trf/v2/'

    @classmethod
    def get_token(cls):
        return cache.get('jibit_trf_access_token') or cls.acquire_access_token()

    @classmethod
    def acquire_access_token(cls):
        try:
            r = requests.post(cls.API_URL + 'tokens/generate', json={
                'apiKey': settings.JIBIT_TRF_API_KEY,
                'secretKey': settings.JIBIT_TRF_API_SECRET,
            }, timeout=30)
            r.raise_for_status()
            json_result = r.json()
        except:
            report_exception()
            raise ValueError('JibitAPIError')
        # Save access token
        access_token = json_result['accessToken']
        cache.set('jibit_trf_access_token', access_token, 86000)
        return access_token

    def do_settle(self, options=None):
        # Options
        options = options or {}
        cancellable = options.get('cancellable', True)
        transfer_mode = options.get('transfer_mode', 'ACH')
        submission_mode = options.get('submission_mode', 'BATCH')

        access_token = self.get_token()
        self.start_settlement()
        if self.withdraw.target_account and self.withdraw.target_account.bank_id == 998:
            destination = settings.JIBIT_WITHDRAW_SHABA['shaba']
            destination_firstname = settings.JIBIT_WITHDRAW_SHABA['name']
            destination_lastname = ''
            payment_id = self.withdraw.target_account.shaba_number
            description = f'واریز {self.withdraw.pk} از نوبیتکس با شناسه {payment_id}'
            cancellable = False  # Ordered by the product team for faster settlement

        else:
            destination = self.withdraw.target_account.shaba_number
            destination_firstname = self.withdraw.target_account.user.first_name
            destination_lastname = self.withdraw.target_account.user.last_name
            payment_id = None
            description = f'واریز {self.withdraw.pk} از نوبیتکس'
        # Send request
        r = requests.post(self.API_URL + 'transfers', json={
            'batchID': self.uid,
            'submissionMode': submission_mode,
            'transfers': [{
                'transferID': self.uid,
                'transferMode': 'NORMAL' if transfer_mode == 'instant' else 'ACH',
                'destination': destination,
                'destinationFirstName': destination_firstname,
                'destinationLastName': destination_lastname,
                'amount': self.net_amount,
                'currency': 'RIALS',
                'description': description,
                'cancellable': cancellable,
                'paymentID': payment_id,
            }],
        }, headers={
            'Authorization': 'Bearer ' + access_token,
        }, timeout=30)

        # Process response
        log_event(
            'Jibit Settlement - {}: {}'.format(submission_mode, r.status_code if r is not None else '0'), level='info',
            module='settlement', category='general', runner='admin', details=r.text if r is not None else 'None')

        settlement_data = {
            "withdraw": self.withdraw.pk,
            "destination": self.withdraw.target_account.shaba_number,
            "destinationFirstName": self.withdraw.target_account.user.first_name,
            "destinationLastName": self.withdraw.target_account.user.last_name,
            "amount": self.net_amount,
            "transferMode": 'NORMAL' if transfer_mode == 'instant' else 'ACH',
            "submissionMode": submission_mode,
            "cancellable": cancellable,
            "batchID": self.uid,
            "responseStatusCode": r.status_code if r is not None else 0,
            "responseText": r.text if r is not None else 'None'
        }
        log_event(
            'Jibit Settlement Details - withdraw:{}'.format(self.withdraw.pk),
            level='info', module='settlement', category='history', runner='admin', details=json.dumps(settlement_data))

        r.raise_for_status()
        r = r.json()
        if not r.get('submittedCount') or r['submittedCount'] != 1:
            raise ValueError('API error in Jibit settlement - cashout request')

        # Mark as withdraw from Jibit system account
        try:
            system_bank_account = SystemBankAccount.objects.get(account_number='JIBIT')
        except SystemBankAccount.DoesNotExist:
            system_bank_account = None

        # Finalize
        self.withdraw.status = self.withdraw.STATUS.sent
        self.withdraw.updates = (self.withdraw.updates or '') + str(r)
        self.withdraw.blockchain_url = 'nobitex://app/wallet/rls/transaction/WJ{}'.format(self.uid)
        self.withdraw.withdraw_from = system_bank_account
        self.withdraw.save(update_fields=['status', 'updates', 'blockchain_url', 'withdraw_from'])
        return self.uid

    def get_info(self):
        """ Fetch latest Jibit data for this settlement
        """
        r = requests.get(self.API_URL + 'transfers', params={
            'transferID': self.uid,
        }, headers={
            'Authorization': 'Bearer ' + self.get_token(),
        }, timeout=30)
        r.raise_for_status()
        transfers = r.json().get('transfers') or []
        if not transfers:
            return {}
        return transfers[0]

    def update_status(self, update_all=False):
        """ Update bank payment status for the withdraw
        """
        if not settings.IS_PROD:
            return
        info = self.get_info()
        if not info:
            return
        state = info.get('state')
        mode = info.get('transferMode')
        bank_id = info.get('bankTransferID')
        status_url = 'nobitex://withdraw/{}-{}/WJ{}'.format(
            mode or 'ACH',
            state or 'NEW',
            bank_id or self.uid,
        )
        updating_fields = []
        if self.withdraw.blockchain_url != status_url:
            self.withdraw.blockchain_url = status_url
            updating_fields.append('blockchain_url')

        if update_all and self.withdraw.status == WithdrawRequest.STATUS.manual_accepted:
            from exchange.report.models import DailyWithdraw
            from exchange.report.parsers import parse_daily_withdraw_status
            try:
                state = parse_daily_withdraw_status(info.get('state'))
            except Exception:
                state = None
            if state in [
                # 0,3,4,
                DailyWithdraw.STATUS.initialized,
                DailyWithdraw.STATUS.in_progress,
                DailyWithdraw.STATUS.transferred,
            ]:
                self.withdraw.status = self.withdraw.STATUS.sent
                self.withdraw.withdraw_from = SystemBankAccount.objects.filter(account_number='JIBIT').first() or None
                self.withdraw.updates = (self.withdraw.updates or '') + str(info)
                updating_fields.extend(['status', 'updates', 'withdraw_from'])
        self.withdraw.save(update_fields=updating_fields)

    @staticmethod
    def normalize_datetime(value):
        return value.astimezone(datetime.timezone.utc).isoformat().replace('+00:00', 'Z') if value else None

    @classmethod
    def fetch_withdraws(cls, from_date=None, to_date=None, page=1, size=250, done=False, manually_failed=False):
        try:
            state = None
            if done:
                state = 'TRANSFERRED'
            elif manually_failed:
                state = 'MANUALLY_FAILED'
            params = {
                'page': page,
                'size': size,
                'from': cls.normalize_datetime(from_date),
                'to': cls.normalize_datetime(to_date),
                'state': state,
            }
            response = requests.get(cls.API_URL + f'transfers/filter', params=params, headers={
                'Authorization': 'Bearer ' + cls.get_token(),
            }, timeout=30)
            response.raise_for_status()
            transfers = response.json().get('elements', [])
        except:
            report_exception()
            transfers = []
        return transfers

    @classmethod
    def get_balance(cls):
        """ Fetch latest Jibit data for this settlement
        """
        try:
            response = requests.get(cls.API_URL + 'balances', headers={
                'Authorization': 'Bearer ' + cls.get_token(),
            }, timeout=30)
            response.raise_for_status()
            response = response.json()
        except:
            report_exception()
            return None
        return response


class BaseVandarV3:
    API_URL = 'https://api.vandar.io/v3/'
    API_V2_URL = 'https://api.vandar.io/v2/'
    BUSINESS_NAME = 'NOBITEX' if settings.IS_PROD else 'developers'

    @classmethod
    def get_token(cls):
        return cache.get('vandar_api_token') or cls.acquire_access_token()

    @classmethod
    def acquire_access_token(cls):
        r = None
        try:
            r = requests.post(cls.API_URL + 'login', json={
                'mobile': settings.VANDAR_USERNAME,
                'password': settings.VANDAR_PASSWORD
            }, timeout=30)
            r.raise_for_status()
            r = r.json()
            if 'access_token' not in r:
                raise ValueError('API error in Vandar settlement - login request: {}'.format(r))
            api_token = r['access_token']
        except:
            report_exception()
            raise
        # Save api token
        cache.set('vandar_api_token', api_token, 5 * 24 * 60 * 60)
        return api_token

    @staticmethod
    def normalize_datetime(value):
        return calendar.to_shamsi_date(value, format_='%Y%m%d')

    @staticmethod
    def parse_datetime(value):
        return calendar.parse_shamsi_date(value, '%H:%M:%S - %Y/%m/%d')


class VandarSettlement(BaseVandarV3, BaseSettlement):
    def do_settle(self, is_auto_withdraw=False, options=None):
        if not is_auto_withdraw:
            self.start_settlement()

        # Get api token
        try:
            api_token = self.get_token()
        except:
            if not is_auto_withdraw:
                self.abort()
            raise

        # Determining the amount to send after deducting fees
        # Vandar only accepts Toman values, so we round up the value to not pay less to our customers
        net_amount = int(math.ceil(self.net_amount / 10))  # Convert to Toman and round up

        # Setting Sheba for Vandar ID withdraws
        is_a2a = self.withdraw.target_account.bank_id == BankAccount.BANK_ID.vandar
        if is_a2a:
            iban = Settings.get('vandar_shaba_number')
            if iban is None:
                raise ValueError('Vandar settlement: vandar_shaba_number setting is undefined!')
        else:
            iban = self.withdraw.target_account.shaba_number

        # Send settlement request
        r = requests.post(self.API_URL + f'business/{self.BUSINESS_NAME}/settlement/store', json={
            'amount': net_amount,
            'iban': iban,
            'track_id': self.withdraw.pk,
            'payment_number': self.withdraw.target_account.account_number if is_a2a else self.withdraw.pk,
            'is_instant': is_a2a,
            'type': 'A2A' if is_a2a else 'ACH',
        }, headers={
            'Authorization': f'Bearer {api_token}',
        }, timeout=60)

        # Login if api token is expired!
        if r is not None and r.status_code == 406:
            self.acquire_access_token()
            raise ValueError('API error in Vandar settlement - cashout request: Invalid token}')
        # Handle errors
        if not r.ok:
            details = 'None'
            if r is not None:
                try:
                    details = r.json()
                except:
                    details = r.text
            log_event(
                'vandar Settlement: {}'.format(r.status_code if r is not None else '0'), level='info',
                module='settlement', category='general', runner='admin', details=details)
            raise ValueError(f'API error in Vandar settlement - cashout request: {details}')

        r = r.json()
        if r.get('status') != 1 or not r.get('data'):
            raise ValueError(f'API error in Vandar settlement - cashout request: {r}')
        data = r['data']
        if not data.get('settlement'):
            raise ValueError(f'Error but probably done - cashout request: {r}')
        settlements = data['settlement']

        # Mark as withdraw from Pay system account
        try:
            system_bank_account = SystemBankAccount.objects.get(account_number='VANDAR')
        except SystemBankAccount.DoesNotExist:
            system_bank_account = None

        # Finalize
        self.withdraw.status = WithdrawRequest.STATUS.sent
        self.withdraw.updates = (self.withdraw.updates or '') + str(settlements)
        self.withdraw.blockchain_url = f'nobitex://app/wallet/rls/transaction/WV{self.withdraw.pk}'
        self.withdraw.withdraw_from = system_bank_account
        self.withdraw.save(update_fields=['status', 'updates', 'blockchain_url', 'withdraw_from'])
        return settlements


class TomanSettlement(BaseSettlement):
    API_URL = 'https://settlement.tomanpay.net'
    SANDBOX_API_URL = 'https://settlement-staging.qbitpay.org'
    client = TomanClient()

    TOMAN_STATUS = Choices(
        (-1, 'unknown', 'Unknown'),
        (0, 'created', 'Created'),
        (1, 'failed', 'Failed'),
        (2, 'pending', 'Pending'),
        (3, 'success', 'Success'),
        (4, 'canceled', 'Canceled'),
        (5, 'expired', 'Expired'),
        (6, 'disapproved', 'Disapproved'),
        (8, 'denied', 'Denied'),
    )

    @property
    def base_url(self) -> str:
        if settings.IS_PROD:
            return self.API_URL
        return self.SANDBOX_API_URL

    def get_url(self, path: str) -> str:
        return urljoin(self.base_url, path)

    def do_settle(self, options=None):
        # Options
        options = options or {}
        self.start_settlement()
        destination = self.withdraw.target_account.shaba_number
        destination_full_name = ' '.join((
            self.withdraw.target_account.user.first_name,
            self.withdraw.target_account.user.last_name,
        ))
        tracker_id = self.withdraw.id
        description = f'واریز {self.withdraw.pk} به نوبیتکس'

        response = None
        # Send request
        try:
            response = self.client.request(self.get_url('/settlements/v2/'), 'POST', json={
                'full_name': destination_full_name,
                'amount': self.net_amount,
                'description': description,
                'tracker_id': tracker_id,
                'iban': destination
            })
        except (TomanAuthenticateError, TomanClientError) as ex:
            report_exception()
            response = ex.args[0].response
            result = response.json() if response is not None else None
            raise ValueError(
                f'API error in Toman settlement - cashout request: {result.get("detail") if result else ex}'
            ) from ex
        finally:
            # Process response
            log_event(
                f'Toman Settlement - Single-Step: {response.status_code if response is not None else 0}',
                level='info',
                module='settlement',
                category='general',
                runner='admin',
                details=response.text if response is not None else 'None',
            )

            settlement_data = {
                'withdraw': self.withdraw.pk,
                'destination': self.withdraw.target_account.shaba_number,
                'destinationFirstName': self.withdraw.target_account.user.first_name,
                'destinationLastName': self.withdraw.target_account.user.last_name,
                'amount': self.net_amount,
                'transferMode': 'AUTO',
                'submissionMode': 'Single-Step',
                'cancellable': False,
                'batchID': self.uid,
                'responseStatusCode': response.status_code if response is not None else 0,
                'responseText': response.text if response is not None else 'None'
            }

            log_event(
                f'Toman Settlement Details - withdraw:{self.withdraw.pk}',
                level='info',
                module='settlement',
                category='history',
                runner='admin',
                details=json.dumps(settlement_data),
            )

        # Mark as withdraw from Toman system account
        try:
            system_bank_account = SystemBankAccount.objects.get(account_number='TOMAN')
        except SystemBankAccount.DoesNotExist:
            system_bank_account = None

        # Finalize
        self.withdraw.status = self.withdraw.STATUS.sent
        self.withdraw.updates = (self.withdraw.updates or '') + str(response)
        self.withdraw.blockchain_url = f'nobitex://app/wallet/rls/transaction/WT{self.uid}'
        self.withdraw.withdraw_from = system_bank_account
        self.withdraw.save(update_fields=['status', 'updates', 'blockchain_url', 'withdraw_from'])
        return self.uid

    def get_info(self):
        """Fetch latest Toman data for this settlement"""
        try:
            response = self.client.request(self.get_url(f'/settlements/tracking/{self.uid}'), 'GET')
            response.raise_for_status()
        except (TomanAuthenticateError, TomanClientError):
            report_exception()
            return

        return response.json()

    def update_status(self, update_all=False):
        """Update bank payment status for the withdraw"""
        if not settings.IS_PROD:
            return
        info = self.get_info()
        if not info:
            return
        status = info.get('status')
        bank_id = info.get('bank_id')
        status_url = f'nobitex://withdraw/AUTO-{status}/WT{bank_id}'

        updating_fields = []
        if self.withdraw.blockchain_url != status_url:
            self.withdraw.blockchain_url = status_url
            updating_fields.append('blockchain_url')

        if update_all and self.withdraw.status == WithdrawRequest.STATUS.manual_accepted:
            if int(status) in [
                self.TOMAN_STATUS.created,
                self.TOMAN_STATUS.pending,
                self.TOMAN_STATUS.success,
            ]:
                self.withdraw.status = self.withdraw.STATUS.sent
                self.withdraw.withdraw_from = SystemBankAccount.objects.filter(account_number='TOMAN').first() or None
                self.withdraw.updates = (self.withdraw.updates or '') + str(info)
                updating_fields.extend(['status', 'updates', 'withdraw_from'])
        self.withdraw.save(update_fields=updating_fields)


def settle_withdraw(withdraw, method, options=None):
    if withdraw.updates:
        raise ValueError('AlreadySettled')
    if not settings.IS_PROD:
        raise ValueError('NotAllowedInTestnet')
    if withdraw.is_internal:
        raise ValueError('InternalTransfer')

    result = None
    if method == WithdrawRequest.SETTLE_METHOD.payir:
        result = settle_using_payir(withdraw, options=options)
    elif method == WithdrawRequest.SETTLE_METHOD.vandar:
        result = VandarSettlement(withdraw).do_settle(options=options)
    elif method == WithdrawRequest.SETTLE_METHOD.jibit:
        result = JibitSettlement(withdraw).do_settle(options=options)
    elif method == WithdrawRequest.SETTLE_METHOD.jibit_v2:
        result = JibitSettlementV2(withdraw).do_settle(options=options)
    elif method == WithdrawRequest.SETTLE_METHOD.toman:
        result = TomanSettlement(withdraw).do_settle(options=options)
    return result
