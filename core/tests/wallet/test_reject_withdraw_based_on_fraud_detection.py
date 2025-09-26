from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils.timezone import timedelta
from django.utils.timezone import now

from exchange.accounts.models import User, BankAccount, UserRestriction
from exchange.base.models import Currencies, Settings
from exchange.wallet.models import Wallet, WithdrawRequest, AutomaticWithdraw, \
    AutomaticWithdrawLog
from exchange.wallet.withdraw import WithdrawProcessor
from tests.base.utils import create_withdraw_request


class WithdrawRejectionTest(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        Wallet.create_user_wallets(self.user)
        self.system_rial_account = BankAccount.get_generic_system_account()

    def add_restriction(self, considerations):
        UserRestriction.add_restriction(
            self.user,
            UserRestriction.RESTRICTION.WithdrawRequestCoin,
            considerations=considerations,
            duration=timedelta(hours=72),
        )
        Settings.set('withdrawal_restrictions', f'["{considerations}"]')

    @override_settings(WITHDRAW_FRAUD_ENABLED=True)
    @override_settings(WITHDRAW_CREATE_TX_VERIFY=True)
    def test_reject_withdraw_concurrency(self):
        wallet = Wallet.get_user_wallet(self.user, currency=Currencies.btc)
        withdraw = create_withdraw_request(
            self.user,
            Currencies.btc,
            amount='0.1',
            created_at=now(),
            network='BTC',
            status=1,
            address='bc1qnz8ppdlzgkf73r3vy842dhp5uat57ul2aachww'
        )
        wallet.refresh_from_db()
        assert wallet.balance == Decimal('0.1')
        withdraw.do_verify()
        wallet.refresh_from_db()
        assert withdraw.transaction
        assert withdraw.transaction.pk
        assert wallet.balance == Decimal('0')
        restriction_coin = UserRestriction.RESTRICTION.WithdrawRequestCoin
        assert not UserRestriction.is_restricted(self.user, restriction_coin)
        self.add_restriction(considerations='محدودیت قانون برداشت ۱')
        assert UserRestriction.is_restricted(self.user, restriction_coin)
        withdraw.cancel_request()
        withdraw.status = WithdrawRequest.STATUS.verified
        WithdrawProcessor[Currencies.btc].process_withdraws([withdraw], withdraw.status)
        wallet.refresh_from_db()
        assert wallet.balance == Decimal('0.1')

    @override_settings(WITHDRAW_FRAUD_ENABLED=True)
    @override_settings(WITHDRAW_CREATE_TX_VERIFY=False)
    def test_reject_withdraw_based_on_fraud(self):
        wallet = Wallet.get_user_wallet(self.user, currency=Currencies.btc)
        withdraw = create_withdraw_request(
            self.user,
            Currencies.btc,
            amount='0.1',
            created_at=now(),
            network='BTC',
            status=1,
            address='bc1qnz8ppdlzgkf73r3vy842dhp5uat57ul2aachww'
        )
        automatic_withdraw = AutomaticWithdraw.objects.create(
            withdraw=withdraw,
            tp=AutomaticWithdraw.TYPE.parity,
        )
        auto_log = AutomaticWithdrawLog.objects.create(withdraw=withdraw)
        wallet.refresh_from_db()

        assert wallet.balance == Decimal('0.1')
        assert automatic_withdraw.withdraw == withdraw
        assert auto_log.withdraw == withdraw
        assert automatic_withdraw.status == AutomaticWithdraw.STATUS.new
        withdraw.do_verify()
        wallet.refresh_from_db()
        assert not withdraw.transaction
        assert wallet.balance == Decimal('0.1')
        restriction_coin = UserRestriction.RESTRICTION.WithdrawRequestCoin
        assert not UserRestriction.is_restricted(self.user, restriction_coin)
        self.add_restriction(considerations='محدودیت قانون برداشت ۱')
        assert UserRestriction.is_restricted(self.user, restriction_coin)
        WithdrawProcessor[Currencies.btc].process_withdraws([withdraw], withdraw.status)
        wallet.refresh_from_db()
        auto_log.refresh_from_db()
        automatic_withdraw.refresh_from_db()
        assert wallet.balance == Decimal('0.1')
        assert not withdraw.transaction
        assert withdraw.status == WithdrawRequest.STATUS.rejected
        assert automatic_withdraw.status == AutomaticWithdraw.STATUS.canceled
        assert auto_log.status == 8
