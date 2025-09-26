import copy
import datetime
import json
from decimal import Decimal
from unittest.mock import call, patch

import pytz
import responses
from django.core.cache import cache
from django.test import TestCase, override_settings

from exchange.accounts.models import Notification, User
from exchange.base.models import RIAL
from exchange.base.parsers import parse_choices, parse_utc_timestamp_ms
from exchange.direct_debit.models import DailyDirectDeposit, DirectDeposit
from exchange.direct_debit.services import DirectDebitUpdateDeposit
from exchange.direct_debit.tasks import task_update_direct_deposit
from exchange.wallet.models import Transaction, Wallet
from tests.base.utils import mock_on_commit
from tests.direct_debit.helper import DirectDebitMixins


@override_settings(IS_PROD=True)
class UpdateDirectDepositTaskTests(DirectDebitMixins, TestCase):
    fixtures = ('test_data',)

    def setUp(self):
        self.direct_debit_ref_module = Transaction.REF_MODULES['DirectDebitUserTransaction']
        self.sample_faraboom_response = {
            'currency': 'IRR',
            'description': 'Nobitex Direct Debit Transaction',
            'destination_bank': 'SINAIR',
            'destination_deposit': '361-813-2295556-1',
            'source_bank': 'SINAIR',
            'source_deposit': '119-813-2295556-1',
            'transaction_type': 'NORMAL',
            'reference_id': '00001718724123545112',
            'trace_id': 'd3742532d7fe40c69910fe6d3686c7ae',
            'transaction_amount': 10000000,
            'transaction_time': 1718724120000,
            'batch_id': '1008713',
            'commission_amount': 0,
            'status': 'SUCCEED',
            'is_over_draft': False,
        }
        self.sample_faraboom_response2 = {
            'currency': 'IRR',
            'description': 'Nobitex Direct Debit Transaction',
            'destination_bank': 'SINAIR',
            'destination_deposit': '361-813-2295556-2',
            'source_bank': 'SINAIR',
            'source_deposit': '119-813-2295556-2',
            'transaction_type': 'NORMAL',
            'reference_id': '00001718724123545113',
            'trace_id': 'd3742532d7fe40c69910fe6d3686c7ad',
            'transaction_amount': 20000000,
            'transaction_time': 1718724120000,
            'batch_id': '1008714',
            'commission_amount': 0,
            'status': 'SUCCEED',
            'is_over_draft': False,
        }
        self.trace_id = self.sample_faraboom_response['trace_id']
        self.trace_id2 = self.sample_faraboom_response2['trace_id']
        self.user = User.objects.get(id=201)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        self.request_feature(self.user, 'done')

        self.contract = self.create_contract(user=self.user)
        self.contract.trace_id = 'cdklcdke-b7jk-5hg-997c-b991acdac3b6'
        self.contract.contract_id = 'kr7JBZLrkMNZ'
        self.contract.save()

        self.deposit = None
        self.deposit_datetime = parse_utc_timestamp_ms(1718724120000)
        self.deposit_datetime = self.deposit_datetime.astimezone(pytz.timezone('Asia/Tehran'))

        self.url = (
            f'{self.base_url}'
            f'/v1/payman/pay/trace?trace-id='
            f'{self.trace_id}'
            f'&date='
            f'{self.deposit_datetime.date().isoformat()}'
        )
        self.url2 = (
            f'{self.base_url}'
            f'/v1/payman/pay/trace?trace-id='
            f'{self.trace_id2}'
            f'&date='
            f'{self.deposit_datetime.date().isoformat()}'
        )
        Notification.objects.filter(user=self.user, message__contains='خوش آمدید').delete()

        cache.set('direct_debit_access_token', 'test_direct_debit_access_token')

    def tearDown(self):
        DirectDeposit.objects.all().delete()
        DailyDirectDeposit.objects.all().delete()

    def make_deposit(self, status=DirectDeposit.STATUS.succeed, do_commit=True):
        deposit = self.create_deposit(
            user=self.user,
            contract=self.contract,
            amount=Decimal('1_000_000_0'),
            trace_id=self.trace_id,
            reference_id=self.sample_faraboom_response['reference_id'],
            batch_id=self.sample_faraboom_response['batch_id'],
            deposited_at=self.deposit_datetime,
            status=status,
        )
        if do_commit:
            deposit.commit_deposit()
        return deposit

    def make_daily_direct_deposit(self, data):
        data = copy.copy(data)
        data.pop('currency')
        data.pop('destination_deposit')
        data.pop('source_deposit')
        data.pop('transaction_time')
        data.pop('commission_amount')
        data.pop('batch_id')
        data.pop('is_over_draft')
        data['status'] = parse_choices(
            DirectDeposit.STATUS,
            data['status'].lower(),
        )
        data['server_date'] = parse_utc_timestamp_ms(self.sample_faraboom_response['transaction_time'])
        data['contract_id'] = self.contract.contract_id
        return DailyDirectDeposit.objects.create(**data)

    def test_not_diff(self):
        # nothing happened because it is not a diff case
        self.deposit = self.make_deposit()
        self.daily_deposit = self.make_daily_direct_deposit(self.sample_faraboom_response)
        if self.deposit:
            self.daily_deposit.deposit = self.deposit
            self.daily_deposit.save()

        deposit_count = DirectDeposit.objects.count()
        daily_deposit_count = DailyDirectDeposit.objects.count()

        task_update_direct_deposit([self.trace_id])

        assert DirectDeposit.objects.count() == deposit_count
        assert DailyDirectDeposit.objects.count() == daily_deposit_count

        assert self.deposit.status == DirectDeposit.STATUS.succeed

    @responses.activate
    @patch('exchange.direct_debit.models.DirectDepositSuccessfulNotification.send_email')
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_not_diff_update_daily(self, mock_on_commit, mock_send_email):
        # daily deposit should be updated cuz of difference between daily deposit and deposit
        # this case list of the diff report, and we should exclude it by updating the daily record
        self.deposit = self.make_deposit()
        self.daily_deposit = self.make_daily_direct_deposit(self.sample_faraboom_response)
        if self.deposit:
            self.daily_deposit.deposit = self.deposit
            self.daily_deposit.status = DirectDeposit.STATUS.in_progress
            self.daily_deposit.save()

        assert self.deposit.transaction
        assert self.deposit.status == DirectDeposit.STATUS.succeed
        assert self.daily_deposit.status == DirectDeposit.STATUS.in_progress

        deposit_count = DirectDeposit.objects.count()
        daily_deposit_count = DailyDirectDeposit.objects.count()

        responses.get(url=self.url, json=self.sample_faraboom_response, status=200)
        task_update_direct_deposit([self.trace_id])

        assert DirectDeposit.objects.count() == deposit_count
        assert DailyDirectDeposit.objects.count() == daily_deposit_count

        self.daily_deposit.refresh_from_db()
        self.deposit.refresh_from_db()
        assert self.deposit.status == DirectDeposit.STATUS.succeed
        assert self.daily_deposit.status == DirectDeposit.STATUS.succeed

    @responses.activate
    def test_in_progress_status(self):
        self.daily_deposit = self.make_daily_direct_deposit(self.sample_faraboom_response)

        assert not self.deposit
        assert not DirectDeposit.objects.exists()

        _response = self.sample_faraboom_response
        _response.update({'status': 'IN_PROGRESS'})

        responses.get(url=self.url, json=_response, status=200)
        task_update_direct_deposit([self.trace_id])

        direct_deposit = DirectDeposit.objects.first()
        assert direct_deposit is not None
        assert direct_deposit.status == DirectDeposit.STATUS.in_progress

    @responses.activate
    @patch('exchange.direct_debit.models.DirectDepositSuccessfulNotification.send_email')
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_succeed_status(self, mock_on_commit, mock_send_email):
        self.daily_deposit = self.make_daily_direct_deposit(self.sample_faraboom_response)

        assert not Notification.objects.filter(user=self.user).exists()

        user_wallet = Wallet.get_user_wallet(user=self.user, currency=RIAL)
        assert user_wallet.balance == 0

        assert not DirectDeposit.objects.filter(
            trace_id=self.daily_deposit.trace_id,
            contract_id=self.contract.id,
        ).exists()
        assert not Transaction.objects.filter(ref_module=self.direct_debit_ref_module, wallet__user=self.user).exists()

        responses.get(url=self.url, json=self.sample_faraboom_response, status=200)
        task_update_direct_deposit([self.trace_id])

        deposit = DirectDeposit.objects.filter(
            trace_id=self.daily_deposit.trace_id,
            contract_id=self.contract.id,
        ).first()
        assert deposit
        assert deposit.transaction
        assert deposit.created_at == self.daily_deposit.server_date
        third_party = deposit.third_party_response
        assert third_party['trace_id'] == self.sample_faraboom_response['trace_id']
        assert third_party['status'].lower() == self.sample_faraboom_response['status'].lower()

        transaction = Transaction.objects.filter(
            ref_module=self.direct_debit_ref_module, wallet__user=self.user
        ).first()
        assert transaction
        assert transaction == deposit.transaction

        user_wallet.refresh_from_db()
        assert user_wallet.balance == transaction.amount == Decimal('9980000.0000000000')

        notification = Notification.objects.filter(user=self.user).first()
        assert notification
        assert notification.message == (
            f'مبلغ 998000 تومان از حساب {self.contract.bank.name} به کیف پول اسپات شما واریز مستقیم شد.'
        )
        mock_send_email.assert_called_once_with(bank_name=self.contract.bank.name, amount=9980000)

    @responses.activate
    def test_succeed_status_exist_in_nobitex_with_transaction(self):
        self.daily_deposit = self.make_daily_direct_deposit(self.sample_faraboom_response)
        self.deposit = self.make_deposit(status=DirectDeposit.STATUS.failed, do_commit=True)
        self.deposit.status = DirectDeposit.STATUS.failed
        self.deposit.save()
        self.daily_deposit.deposit = self.deposit
        self.daily_deposit.save()

        # there is not such this case but for corner cases
        # if transaction.exists() it definitely is succeeded

        user_wallet = Wallet.get_user_wallet(user=self.user, currency=RIAL)
        assert user_wallet.balance == self.deposit.net_amount

        deposit = DirectDeposit.objects.filter(
            trace_id=self.daily_deposit.trace_id,
            contract_id=self.contract.id,
        ).first()
        assert deposit
        assert deposit.status == DirectDeposit.STATUS.failed
        transaction = Transaction.objects.filter(
            ref_module=self.direct_debit_ref_module, wallet__user=self.user
        ).first()
        assert transaction

        responses.get(url=self.url, json=self.sample_faraboom_response, status=200)
        task_update_direct_deposit([self.trace_id])

        deposit.refresh_from_db()
        assert deposit.status == DirectDeposit.STATUS.failed  # must handle manually and it's ok
        assert deposit.transaction

        transaction = Transaction.objects.filter(
            ref_module=self.direct_debit_ref_module, wallet__user=self.user
        ).first()
        assert transaction
        assert transaction == deposit.transaction

        user_wallet.refresh_from_db()
        assert user_wallet.balance == transaction.amount == self.deposit.net_amount

        assert not Notification.objects.filter(user=self.user).exists()

    @responses.activate
    def test_failed_status(self):
        self.sample_faraboom_response['status'] = 'FAILED'
        self.daily_deposit = self.make_daily_direct_deposit(self.sample_faraboom_response)

        assert self.daily_deposit.status == DailyDirectDeposit.STATUS.failed

        user_wallet = Wallet.get_user_wallet(user=self.user, currency=RIAL)
        assert user_wallet.balance == 0

        assert not DirectDeposit.objects.filter(
            trace_id=self.daily_deposit.trace_id,
            contract_id=self.contract.id,
        ).exists()
        assert not Transaction.objects.filter(ref_module=self.direct_debit_ref_module, wallet__user=self.user).exists()

        responses.get(url=self.url, json=self.sample_faraboom_response, status=200)
        task_update_direct_deposit([self.trace_id])

        deposit = DirectDeposit.objects.filter(
            trace_id=self.daily_deposit.trace_id,
            contract_id=self.contract.id,
        ).first()
        assert deposit
        assert deposit.status == DirectDeposit.STATUS.failed
        assert not deposit.transaction
        assert deposit.third_party_response == {
            'currency': 'IRR',
            'description': 'Nobitex Direct Debit Transaction',
            'destination_bank': 'SINAIR',
            'destination_deposit': '361-813-2295556-1',
            'source_bank': 'SINAIR',
            'source_deposit': '119-813-2295556-1',
            'transaction_type': 'NORMAL',
            'reference_id': '00001718724123545112',
            'trace_id': 'd3742532d7fe40c69910fe6d3686c7ae',
            'transaction_amount': 10000000,
            'transaction_time': 1718724120000,
            'batch_id': '1008713',
            'commission_amount': 0,
            'status': 'failed',
        }

        assert not Transaction.objects.filter(ref_module=self.direct_debit_ref_module, wallet__user=self.user).exists()

        user_wallet.refresh_from_db()
        assert user_wallet.balance == 0

        assert not Notification.objects.filter(user=self.user).exists()

    @responses.activate
    def test_reversed_status(self):
        self.sample_faraboom_response['status'] = 'REVERSED'
        self.daily_deposit = self.make_daily_direct_deposit(self.sample_faraboom_response)

        assert self.daily_deposit.status == DailyDirectDeposit.STATUS.reversed

        user_wallet = Wallet.get_user_wallet(user=self.user, currency=RIAL)
        assert user_wallet.balance == 0

        assert not DirectDeposit.objects.filter(
            trace_id=self.daily_deposit.trace_id,
            contract_id=self.contract.id,
        ).exists()
        assert not Transaction.objects.filter(ref_module=self.direct_debit_ref_module, wallet__user=self.user).exists()

        responses.get(url=self.url, json=self.sample_faraboom_response, status=200)
        task_update_direct_deposit([self.trace_id])

        deposit = DirectDeposit.objects.filter(
            trace_id=self.daily_deposit.trace_id,
            contract_id=self.contract.id,
        ).first()
        assert deposit
        assert deposit.status == DirectDeposit.STATUS.reversed
        assert not deposit.transaction
        assert deposit.third_party_response == {
            'currency': 'IRR',
            'description': 'Nobitex Direct Debit Transaction',
            'destination_bank': 'SINAIR',
            'destination_deposit': '361-813-2295556-1',
            'source_bank': 'SINAIR',
            'source_deposit': '119-813-2295556-1',
            'transaction_type': 'NORMAL',
            'reference_id': '00001718724123545112',
            'trace_id': 'd3742532d7fe40c69910fe6d3686c7ae',
            'transaction_amount': 10000000,
            'transaction_time': 1718724120000,
            'batch_id': '1008713',
            'commission_amount': 0,
            'status': 'reversed',
        }

        assert not Transaction.objects.filter(ref_module=self.direct_debit_ref_module, wallet__user=self.user).exists()

        user_wallet.refresh_from_db()
        assert user_wallet.balance == 0

        assert not Notification.objects.filter(user=self.user).exists()

    @responses.activate
    @patch('exchange.direct_debit.models.DirectDepositSuccessfulNotification.send_email')
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_succeed_status_multiple_trace_id(self, mock_on_commit, mock_send_email):
        self.daily_deposit = self.make_daily_direct_deposit(self.sample_faraboom_response)
        self.daily_deposit2 = self.make_daily_direct_deposit(self.sample_faraboom_response2)

        assert not Notification.objects.filter(user=self.user).exists()

        user_wallet = Wallet.get_user_wallet(user=self.user, currency=RIAL)
        assert user_wallet.balance == 0

        assert not DirectDeposit.objects.filter(
            trace_id=self.daily_deposit.trace_id,
            contract_id=self.contract.id,
        ).exists()
        assert not DirectDeposit.objects.filter(
            trace_id=self.daily_deposit2.trace_id,
            contract_id=self.contract.id,
        ).exists()
        assert not Transaction.objects.filter(ref_module=self.direct_debit_ref_module, wallet__user=self.user).exists()

        responses.get(url=self.url, json=self.sample_faraboom_response, status=200)
        responses.get(url=self.url2, json=self.sample_faraboom_response2, status=200)
        task_update_direct_deposit([self.trace_id, self.trace_id2])

        assert DirectDeposit.objects.count() == 2
        deposit1 = DirectDeposit.objects.filter(
            trace_id=self.daily_deposit.trace_id,
            contract_id=self.contract.id,
        ).first()
        assert deposit1
        assert deposit1.transaction

        deposit2 = DirectDeposit.objects.filter(
            trace_id=self.daily_deposit2.trace_id,
            contract_id=self.contract.id,
        ).first()
        assert deposit2
        assert deposit2.transaction

        transactions = Transaction.objects.filter(ref_module=self.direct_debit_ref_module, wallet__user=self.user)
        amount = 0
        for transaction in transactions:
            assert transaction
            assert transaction in [deposit1.transaction, deposit2.transaction]
            amount += transaction.amount

        user_wallet.refresh_from_db()
        assert user_wallet.balance == amount == Decimal('29940000.0000000000')

        assert Notification.objects.filter(user=self.user).count() == 2

        calls = [
            call(bank_name=self.contract.bank.name, amount=9980000),
            call(bank_name=self.contract.bank.name, amount=19960000),
        ]
        mock_send_email.assert_has_calls(calls)

    @responses.activate
    @patch('exchange.direct_debit.models.DirectDepositSuccessfulNotification.send_email')
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_succeed_status_without_daily_deposit(self, mock_on_commit, mock_send_email):
        self.deposit = self.make_deposit(do_commit=False)
        ten_days_ago = self.deposit_datetime - datetime.timedelta(days=10)
        self.deposit.created_at = ten_days_ago
        self.deposit.save()

        assert not Notification.objects.filter(user=self.user).exists()

        user_wallet = Wallet.get_user_wallet(user=self.user, currency=RIAL)
        assert user_wallet.balance == 0

        assert not DailyDirectDeposit.objects.filter(
            trace_id=self.deposit.trace_id,
        ).exists()
        assert not Transaction.objects.filter(ref_module=self.direct_debit_ref_module, wallet__user=self.user).exists()

        url = (
            f'{self.base_url}'
            f'/v1/payman/pay/trace?trace-id='
            f'{self.trace_id}'
            f'&date='
            f'{ten_days_ago.date().isoformat()}'
        )
        responses.get(url=url, json=self.sample_faraboom_response, status=200)
        task_update_direct_deposit([self.trace_id])

        daily_deposit = DailyDirectDeposit.objects.filter(
            trace_id=self.deposit.trace_id,
            contract_id=self.contract.contract_id,
        ).first()
        assert daily_deposit
        assert daily_deposit.deposit == self.deposit

        self.deposit.refresh_from_db()
        transaction = Transaction.objects.filter(
            ref_module=self.direct_debit_ref_module, wallet__user=self.user
        ).first()
        assert transaction
        assert transaction == self.deposit.transaction
        assert int(self.deposit.created_at.timestamp() * 1000) == self.sample_faraboom_response['transaction_time']

        user_wallet.refresh_from_db()
        assert user_wallet.balance == transaction.amount == Decimal('9980000.0000000000')

        notification = Notification.objects.filter(user=self.user).first()
        assert notification
        assert notification.message == (
            f'مبلغ 998000 تومان از حساب {self.contract.bank.name} به کیف پول اسپات شما واریز مستقیم شد.'
        )
        mock_send_email.assert_called_once_with(bank_name=self.contract.bank.name, amount=9980000)

    @responses.activate
    @patch('exchange.direct_debit.models.DirectDepositSuccessfulNotification.send_email')
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_succeed_status_without_daily_deposit_insufficient_balance_status(self, mock_on_commit, mock_send_email):
        self.deposit = self.make_deposit(do_commit=False)
        self.deposit.status = self.deposit.STATUS.insufficient_balance
        self.deposit.created_at = self.deposit_datetime
        self.deposit.save()

        assert not Notification.objects.filter(user=self.user).exists()

        user_wallet = Wallet.get_user_wallet(user=self.user, currency=RIAL)
        assert user_wallet.balance == 0

        assert not DailyDirectDeposit.objects.filter(
            trace_id=self.deposit.trace_id,
        ).exists()
        assert not Transaction.objects.filter(ref_module=self.direct_debit_ref_module, wallet__user=self.user).exists()

        self.sample_faraboom_response['status'] = 'FAILED'
        responses.get(url=self.url, json=self.sample_faraboom_response, status=200)
        task_update_direct_deposit([self.trace_id])

        daily_deposit = DailyDirectDeposit.objects.filter(
            trace_id=self.deposit.trace_id,
            contract_id=self.contract.contract_id,
        ).first()
        assert daily_deposit
        assert daily_deposit.deposit == self.deposit

        self.deposit.refresh_from_db()
        assert self.deposit.status == self.deposit.STATUS.insufficient_balance
        transaction = Transaction.objects.filter(
            ref_module=self.direct_debit_ref_module, wallet__user=self.user
        ).first()
        assert not transaction

        user_wallet.refresh_from_db()
        assert user_wallet.balance == 0

        notification = Notification.objects.filter(user=self.user).first()
        assert not notification
        mock_send_email.assert_not_called()

    @responses.activate
    @patch('exchange.direct_debit.models.DirectDepositSuccessfulNotification.send_email')
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_succeed_status_without_daily_deposit_not_found_in_faraboom(self, mock_on_commit, mock_send_email):
        self.deposit = self.make_deposit(do_commit=False)
        self.deposit.status = self.deposit.STATUS.in_progress
        self.deposit.created_at = self.deposit_datetime
        self.deposit.save()

        assert not Notification.objects.filter(user=self.user).exists()

        user_wallet = Wallet.get_user_wallet(user=self.user, currency=RIAL)
        assert user_wallet.balance == 0

        assert not DailyDirectDeposit.objects.filter(
            trace_id=self.deposit.trace_id,
        ).exists()
        assert not Transaction.objects.filter(ref_module=self.direct_debit_ref_module, wallet__user=self.user).exists()

        responses.get(url=self.url, json={}, status=400)
        task_update_direct_deposit([self.trace_id])

        self.deposit.refresh_from_db()
        assert self.deposit.status == self.deposit.STATUS.failed

        daily_deposit = DailyDirectDeposit.objects.filter(
            trace_id=self.deposit.trace_id,
            contract_id=self.contract.contract_id,
        ).first()
        assert not daily_deposit

        self.deposit.refresh_from_db()
        transaction = Transaction.objects.filter(
            ref_module=self.direct_debit_ref_module, wallet__user=self.user
        ).first()
        assert not transaction

        user_wallet.refresh_from_db()
        assert user_wallet.balance == Decimal('0')

    @responses.activate
    @patch('exchange.direct_debit.models.DirectDepositSuccessfulNotification.send_email')
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_daily_deposit_has_no_deposit_succeed_status(self, mock_on_commit, mock_send_email):

        # Create a DailyDirectDeposit row with no linked deposit.
        DailyDirectDeposit.objects.create(
            trace_id=self.trace_id,
            status=DailyDirectDeposit.STATUS.succeed,
            server_date=self.deposit_datetime,
            contract_id=self.contract.contract_id,
            transaction_amount=10000000,
        )
        assert not DirectDeposit.objects.filter(trace_id=self.trace_id).exists()
        user_wallet = Wallet.get_user_wallet(user=self.user, currency=RIAL)
        assert user_wallet.balance == 0

        succeed_response = dict(self.sample_faraboom_response)
        succeed_response['status'] = 'SUCCEED'
        responses.get(url=self.url, json=succeed_response, status=200)

        task_update_direct_deposit([self.trace_id])
        deposit = DirectDeposit.objects.filter(trace_id=self.trace_id).first()
        assert deposit is not None
        assert deposit.status == DirectDeposit.STATUS.succeed
        assert deposit.transaction is not None

        user_wallet.refresh_from_db()
        transaction = Transaction.objects.filter(
            ref_module=self.direct_debit_ref_module, wallet__user=self.user
        ).first()
        assert transaction is not None
        assert user_wallet.balance == transaction.amount

        notification = Notification.objects.filter(user=self.user).first()
        assert notification is not None
        assert 'واریز مستقیم شد' in notification.message
        mock_send_email.assert_called_once()

    def test_daily_deposit_without_deposit_attaches_existing_deposit(self):
        # Create DailyDirectDeposit without linked deposit
        daily_deposit = DailyDirectDeposit.objects.create(
            trace_id=self.trace_id,
            status=DailyDirectDeposit.STATUS.in_progress,
            server_date=self.deposit_datetime,
            contract_id=self.contract.contract_id,
            transaction_amount=10000000,
        )

        # Create a matching DirectDeposit but not linked
        deposit = self.make_deposit(do_commit=False)
        daily_deposit.refresh_from_db()
        assert daily_deposit.deposit is None

        # Should attach deposit to daily_deposit
        task_update_direct_deposit([self.trace_id])

        daily_deposit.refresh_from_db()
        assert daily_deposit.deposit == deposit

    def test_daily_deposit_without_deposit_attaches_new_deposit(self):
        daily_deposit = DailyDirectDeposit.objects.create(
            trace_id=self.trace_id,
            status=DailyDirectDeposit.STATUS.in_progress,
            server_date=self.deposit_datetime,
            contract_id=self.contract.contract_id,
            transaction_amount=10000000,
        )
        task_update_direct_deposit([self.trace_id])

        daily_deposit.refresh_from_db()
        assert daily_deposit.deposit is not None
        assert daily_deposit.trace_id == daily_deposit.deposit.trace_id

    @responses.activate
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_succeed_status_integrity_error_on_transaction(self, ـ):
        self.daily_deposit = self.make_daily_direct_deposit(self.sample_faraboom_response)
        self.deposit = self.make_deposit()

        self.deposit.transaction = None
        self.deposit.save()

        _transaction = Transaction.objects.filter(
            ref_module=Transaction.REF_MODULES['DirectDebitUserTransaction'],
            ref_id=self.deposit.id,
        ).first()
        assert _transaction

        responses.get(url=self.url, json=self.sample_faraboom_response, status=200)
        task_update_direct_deposit([self.trace_id])

        self.deposit.refresh_from_db()
        assert self.deposit
        assert self.deposit.transaction
        assert _transaction == self.deposit.transaction

    def test_update_third_party_response_field_first_time(self):
        self.deposit = self.make_deposit()
        assert self.deposit.third_party_response == {}

        update_client = DirectDebitUpdateDeposit(self.deposit.trace_id)
        update_client._update_third_party_response('test error message')

        self.deposit.refresh_from_db()
        assert self.deposit.third_party_response == {'diff_try_response': 'test error message'}

    def test_update_third_party_response_field_with_json_value(self):
        self.deposit = self.make_deposit()
        self.deposit.third_party_response = {'test_key': 'test_value'}
        self.deposit.save()

        assert self.deposit.third_party_response == {'test_key': 'test_value'}

        update_client = DirectDebitUpdateDeposit(self.deposit.trace_id)
        update_client._update_third_party_response('test error message')

        self.deposit.refresh_from_db()
        assert self.deposit.third_party_response == {
            'test_key': 'test_value',
            'diff_try_response': 'test error message',
        }

    def test_update_third_party_response_field_with_string_value(self):
        self.deposit = self.make_deposit()
        self.deposit.third_party_response = 'test_bad_error_response'
        self.deposit.save()

        assert self.deposit.third_party_response == 'test_bad_error_response'

        update_client = DirectDebitUpdateDeposit(self.deposit.trace_id)
        update_client._update_third_party_response('test error message')

        self.deposit.refresh_from_db()
        assert self.deposit.third_party_response == {
            'error_response': 'test_bad_error_response',
            'diff_try_response': 'test error message',
        }
