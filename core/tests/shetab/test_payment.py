from unittest.mock import MagicMock

import pytest
from django.test import TestCase
from django.utils import timezone

from exchange.accounts.models import BankAccount, BankCard, User
from exchange.base.models import Currencies
from exchange.shetab.crons import SyncShetabDepositsCron
from exchange.shetab.models import ShetabDeposit
from exchange.wallet.models import Wallet, WithdrawRequest


@pytest.mark.slow
@pytest.mark.interactive
class DepositTestMixin:
    """Test `deposit` and `withdraw` brokers

    Use in conjunction with `LiveServerTestCase`.
    Set broker key and an amount in subclass respectively.
    """
    broker = None
    amount = 500_0
    port = 8008

    @staticmethod
    def get_user():
        return User.objects.get(pk=201)

    def get_new_deposit(self, selected_card=None):
        return ShetabDeposit.objects.create(
            user=self.get_user(),
            amount=self.amount,
            selected_card=selected_card,
            broker=getattr(ShetabDeposit.BROKER, self.broker),
        )

    def get_bank_cark_number(self):
        card_number = input('Enter card number to initiate deposit test: [leave blank to skip]')
        if not card_number:
            self.skipTest('Stingy test runner detected!  U_U')
        return BankCard.objects.create(user=self.get_user(), card_number=card_number, confirmed=True)

    def test_deposit(self):
        wallet = Wallet.get_user_wallet(self.get_user(), currency=Currencies.rls)
        bank_card = self.get_bank_cark_number()
        deposit = self.get_new_deposit(selected_card=bank_card)
        request = MagicMock()
        request.build_absolute_uri.return_value = self.live_server_url
        deposit.sync(request)
        print('Pay to deposit:\n', deposit.get_pay_redirect_url())
        input('Done with payment? [press Enter to continue]')
        deposit.refresh_from_db()
        assert deposit.is_status_done
        wallet.refresh_from_db()
        assert wallet.balance == self.amount - deposit.fee

    def test_deposit_sync_before_payment_by_cron(self):
        deposit = self.get_new_deposit()
        ShetabDeposit.objects.filter(pk=deposit.pk).update(created_at=timezone.now() - timezone.timedelta(minutes=9))
        request = MagicMock()
        request.build_absolute_uri.return_value = self.live_server_url
        deposit.sync(request)
        SyncShetabDepositsCron().run()
        deposit.refresh_from_db()
        assert deposit.status_code == deposit.STATUS.pay_new

    def test_deposit_sync_after_payment_cancel(self):
        deposit = self.get_new_deposit()
        request = MagicMock()
        request.build_absolute_uri.return_value = self.live_server_url
        deposit.sync(request)
        print('Open link, then cancel the payment:\n', deposit.get_pay_redirect_url())
        input('Done canceling? [press Enter to continue]')
        deposit.refresh_from_db()
        assert deposit.status_code == ShetabDeposit.STATUS.confirmation_failed

    def test_deposit_sync_after_successful_payment_with_failed_callback_by_cron(self):
        self.get_bank_cark_number()
        deposit = self.get_new_deposit()
        ShetabDeposit.objects.filter(pk=deposit.pk).update(created_at=timezone.now() - timezone.timedelta(minutes=9))
        request = MagicMock()
        request.build_absolute_uri.return_value = 'http://wrong.server'
        deposit.sync(request)
        print('Pay, but expect failure on callback:\n', deposit.get_pay_redirect_url())
        input('Done with payment? [press Enter to continue]')
        SyncShetabDepositsCron().run()
        deposit.refresh_from_db()
        assert deposit.is_status_done

    def test_deposit_nonexistent_card(self):
        deposit = self.get_new_deposit()
        request = MagicMock()
        request.build_absolute_uri.return_value = self.live_server_url
        deposit.sync(request)
        print('Pay to deposit:\n', deposit.get_pay_redirect_url())
        input('Done with payment? [press Enter to continue]')
        deposit.refresh_from_db()
        assert deposit.status_code == ShetabDeposit.STATUS.invalid_card

    def test_deposit_data_fetch(self):
        handler = ShetabDeposit(broker=getattr(ShetabDeposit.BROKER, self.broker)).handler
        end = timezone.now()
        start = end.replace(year=2021, month=12, day=12)
        values = handler.fetch_deposits(start, end, size=20)
        assert values


@pytest.mark.slow
@pytest.mark.interactive
class WithdrawTestMixin:
    """Test `deposit` and `withdraw` brokers

    Set broker key and an amount in subclass respectively.
    """
    broker = None
    amount = 5_000_0

    @staticmethod
    def get_user():
        return User.objects.get(pk=201)

    def test_withdraw(self):
        shaba_number = input('Enter shaba number to initiate withdraw test: [leave blank to skip]')
        if not shaba_number:
            self.skipTest('Abstemious test runner detected!  XoX')
        user = self.get_user()
        wallet = Wallet.get_user_wallet(user, currency=Currencies.rls)
        wallet.balance = self.amount
        wallet.save(update_fields=['balance'])
        bank_account = BankAccount.objects.create(user=user, shaba_number=shaba_number, confirmed=True)
        withdraw = WithdrawRequest.objects.create(
            wallet=wallet, target_account=bank_account, amount=self.amount, status=WithdrawRequest.STATUS.accepted,
        )
        settlement_manager = withdraw.get_settlement_manager(getattr(WithdrawRequest.SETTLE_METHOD, self.broker))
        settlement_manager.do_settle(options={'cancellable': False, 'transfer_mode': 'instant'})
        withdraw.refresh_from_db()
        assert withdraw.status == withdraw.STATUS.sent
        result = settlement_manager.get_info()
        assert result

    def test_withdraw_data_fetch(self):
        manager = WithdrawRequest().get_settlement_manager(getattr(WithdrawRequest.SETTLE_METHOD, self.broker))
        end = timezone.now()
        start = end.replace(year=2021, month=12, day=12)
        values = manager.fetch_withdraws(start, end, size=20)
        assert values


class JibitPaymentTest(DepositTestMixin, WithdrawTestMixin, TestCase):
    broker = 'jibit_v2'
    amount = 5_000_0


class JibitPaymentV1Test(DepositTestMixin, WithdrawTestMixin, TestCase):
    broker = 'jibit'
    amount = 10_000_0
