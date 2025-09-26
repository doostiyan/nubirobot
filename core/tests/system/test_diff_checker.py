from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils.timezone import now

from exchange.accounts.models import User, BankAccount
from exchange.base.models import Currencies, ADDRESS_TYPE, Settings
from exchange.system.checker import DiffChecker
from exchange.wallet.models import Wallet, ConfirmedWalletDeposit
from exchange.wallet.withdraw import WithdrawProcessor
from tests.base.utils import create_deposit, create_trade, create_withdraw_request


class DiffCheckerTest(TestCase):

    def setUp(self):
        self.user1 = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)
        Wallet.create_user_wallets(self.user1)
        Wallet.create_user_wallets(self.user2)

        self.system_rial_account = BankAccount.get_generic_system_account()

    def setup_scenario(self, user1=None, user2=None):
        if not user1:
            user1 = self.user1
        if not user2:
            user2 = self.user2
        currency = Currencies.btc
        address = 'bc1qnz8ppdlzgkf73r3vy842dhp5uat57ul2aachww'
        tx_hash = 'fb7517cd9159fdc73535b86c8ec8145bbed30ba6962a9360fa9c8828834f90d1'
        wallet = Wallet.get_user_wallet(user1, currency)
        cache_key = f'diff_checker_wallets_last_transaction_{wallet.id}'
        cache.delete(cache_key)
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('0')
        create_deposit(user=user1, currency=currency, address=address, amount=Decimal('1'), tx_hash=tx_hash, type=ADDRESS_TYPE.segwit)
        create_trade(user1, user2, src_currency=currency, amount=Decimal('0.01'), price=Decimal('2.7e9'))
        create_trade(user1, user2, src_currency=currency, amount=Decimal('0.02'), price=Decimal('2.7e9'))
        create_trade(user1, user2, src_currency=currency, amount=Decimal('0.03'), price=Decimal('2.7e9'))
        create_withdraw_request(
            user1, currency, amount='0.179', address=address,
            status=4, created_at=now(), network='BTC',
        )
        return wallet

    def test_check_diff_when_system_honest(self):
        wallet = self.setup_scenario()
        wallet.refresh_from_db()
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('0')

    def test_check_diff_when_system_malicious(self):
        wallet = self.setup_scenario()
        wallet.refresh_from_db()
        tr1 = wallet.create_transaction(tp='deposit', amount=Decimal('0.2'))
        tr1.commit()
        wallet.refresh_from_db()
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('0.2')
        # Run again to test cache method
        tr1 = wallet.create_transaction(tp='manual', amount=Decimal('1.2'))
        tr1.commit()
        wallet.refresh_from_db()
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('0.2')
        tr1 = wallet.create_transaction(tp='manual', amount=Decimal('0.2'))
        tr1.commit()
        wallet.refresh_from_db()
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('0.2')

    def test_check_diff_when_system_malicious_v2(self):
        wallet = self.setup_scenario()
        wallet.refresh_from_db()
        tr1 = wallet.create_transaction(tp='withdraw', amount=Decimal('-0.2'))
        tr1.commit()
        wallet.refresh_from_db()
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('-0.2')
        # Run again to test cache method
        tr1 = wallet.create_transaction(tp='manual', amount=Decimal('0.2'))
        tr1.commit()
        wallet.refresh_from_db()
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('-0.2')
        wallet.refresh_from_db()
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('-0.2')

    def test_check_diff_when_system_malicious_and_fix(self):
        wallet = self.setup_scenario()
        wallet.refresh_from_db()
        tr1 = wallet.create_transaction(tp='deposit', amount=Decimal('0.2'))
        tr1.commit()
        wallet.refresh_from_db()
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('0.2')
        # Run again to test cache method
        tr1 = wallet.create_transaction(tp='withdraw', amount=Decimal('-0.2'))
        tr1.commit()
        wallet.refresh_from_db()
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('0')

    def test_check_diff_when_reject_withdraw_without_confirmed(self):
        wallet = self.setup_scenario()
        wallet.refresh_from_db()
        address = 'bc1qnz8ppdlzgkf73r3vy842dhp5uat57ul2aachww'
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('0')
        withdraw = create_withdraw_request(
            self.user1, Currencies.btc, amount='0.1', address=address,
            status=2, created_at=now(), network='BTC',
        )
        withdraw.system_reject_request()
        wallet.refresh_from_db()
        diff = DiffChecker.check_wallet_diff(wallet)
        assert wallet.balance == Decimal('1.16')
        assert diff == Decimal('0')

    def test_check_diff_when_reject_withdraw_without_confirmed_v2(self):
        wallet = self.setup_scenario()
        wallet.refresh_from_db()
        address = '3C2pqjaPNjHWeXjWkZChGfcDabUQB2Sdk9'
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('0')
        withdraw = create_withdraw_request(
            self.user1, Currencies.btc, amount='0.1', address=address,
            status=3, created_at=now(), network='BTC',
        )
        withdraw.system_reject_request()
        wallet.refresh_from_db()
        diff = DiffChecker.check_wallet_diff(wallet)
        assert wallet.balance == Decimal('1.16')
        assert diff == Decimal('0')

    def test_check_diff_when_reject_withdraw_without_confirmed_v3(self):
        wallet = self.setup_scenario()
        wallet.refresh_from_db()
        address = 'bc1qnz8ppdlzgkf73r3vy842dhp5uat57ul2aachww'
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('0')
        withdraw = create_withdraw_request(
            self.user1, Currencies.btc, amount='0.1', address=address,
            status=1, created_at=now(), network='BTC',
        )
        Settings.set('withdraw_check_daily_diff', 'disabled')
        withdraw.do_verify()
        WithdrawProcessor[Currencies.btc].process_withdraws([withdraw], withdraw.status)
        WithdrawProcessor[Currencies.btc].process_withdraws([withdraw], withdraw.status)
        wallet.refresh_from_db()
        assert withdraw.transaction
        assert withdraw.transaction.pk
        assert wallet.balance == Decimal('1.16')
        withdraw.system_reject_request()
        wallet.refresh_from_db()
        diff = DiffChecker.check_wallet_diff(wallet)
        assert wallet.balance == Decimal('1.16')
        assert diff == Decimal('0')
        tr1 = wallet.create_transaction(tp='withdraw', amount=Decimal('-0.1'))
        tr1.commit()
        wallet.refresh_from_db()
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('-0.1')

    @override_settings(WITHDRAW_CREATE_TX_VERIFY=False)
    def test_check_diff_when_reject_internal_withdraw_old_manner(self):
        wallet = self.setup_scenario()
        wallet.refresh_from_db()
        address = 'bc1qnz8ppdlzgkf73r3vy842dhp5uat57ul2aachww'
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('0')
        assert wallet.balance == Decimal('1.06')
        withdraw = create_withdraw_request(
            self.user1, Currencies.btc, amount='0.1', address=address,
            status=3, created_at=now(), network='BTC',
        )
        Settings.set('withdraw_check_daily_diff', 'disabled')
        WithdrawProcessor[Currencies.btc].process_withdraws([withdraw], withdraw.status)
        wallet.refresh_from_db()
        withdraw.system_reject_request()
        wallet.refresh_from_db()
        assert withdraw.transaction
        assert withdraw.transaction.pk
        diff = DiffChecker.check_wallet_diff(wallet)
        assert wallet.balance == Decimal('1.16')
        assert diff == Decimal('0')
        tr1 = wallet.create_transaction(tp='withdraw', amount=Decimal('-0.1'))
        tr1.commit()
        wallet.refresh_from_db()
        assert wallet.balance == Decimal('1.06')
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('-0.1')

    def test_check_diff_when_create_invoice(self):
        wallet = self.setup_scenario()
        wallet.refresh_from_db()
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('0')
        assert wallet.balance == Decimal('1.06')
        deposit = ConfirmedWalletDeposit.objects.create(
            tx_hash='GvgjwjPql9/Vvxni15iQF17AnMTU4Mg5Q39sryLAeHg=',
            _wallet=wallet,
            amount=Decimal('0.0000100000'),
            invoice='lntb10u1ps0lm6upp5rtuz8s3na2tal4dlr83d0xysza0vp8xy6nsvsw2r0ak27gkq0puqdqqcqzpgxqyz5vqsp530du3j3ytpl7nxlytauqfy36t3yc9f7u5hu6rk5864d6rt7fmsfq9qyyssqzuqlkk3aqenxvjw5glynmaltdgpf95wyaxrfh4w2kuvngdjgnnc3a4tz5vk0k57t4037gmzkyx598veavrf40vnysq4xuwedlrsdm8sqkt6qze',
        )
        wallet.refresh_from_db()
        assert wallet.balance == Decimal('1.06')
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('0')

    def test_check_diff_when_cancel_withdraw(self):
        wallet = self.setup_scenario()
        wallet.refresh_from_db()
        address = 'bc1qnz8ppdlzgkf73r3vy842dhp5uat57ul2aachww'
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('0')
        withdraw = create_withdraw_request(
            self.user1, Currencies.btc, amount='0.1', address=address,
            status=3, created_at=now(), network='BTC',
        )
        withdraw.cancel_request()
        wallet.refresh_from_db()
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('0')

    def test_check_diff_when_deposit_to_legacy(self):
        # TODO: Checker currently doesn't support fee in deposit
        wallet = self.setup_scenario()
        wallet.refresh_from_db()
        currency = Currencies.btc
        address = '3C2pqjaPNjHWeXjWkZChGfcDabUQB2Sdk9'
        tx_hash = 'fd286244a89d1ab9a74c904ceaa2b33c3cae452e5ed31c3b46378dd6b2f203d0'
        create_deposit(user=self.user1, currency=currency, address=address, amount=Decimal('1'), tx_hash=tx_hash,
                       type=ADDRESS_TYPE.standard)
        wallet.refresh_from_db()
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('0')

    def test_check_diff_internal_transaction(self):
        wallet = self.setup_scenario()
        wallet.refresh_from_db()
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('0')
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('0')
        address = '327ySURPg6JS1awGKteGMSCrq7DFsASjCH'
        tx_hash = 'ca3f27c6c1cb5f01ab976e589deda7f2c67ce3046f4b24d3dbed2d202f2804b3'
        create_deposit(user=self.user2, currency=Currencies.btc, address=address, amount=Decimal('1'), tx_hash=tx_hash,
                       type=ADDRESS_TYPE.segwit)
        wallet_2 = Wallet.get_user_wallet(self.user2, Currencies.btc)
        withdraw = create_withdraw_request(
            self.user1, Currencies.btc, amount='0.1', address=address,
            status=3, created_at=now(), network='BTC',
        )
        WithdrawProcessor[Currencies.btc].process_withdraws([withdraw], withdraw.status)
        assert withdraw.get_internal_target_wallet() == wallet_2.get_current_deposit_address()
        withdraw.cancel_request()
        withdraw.refresh_from_db()
        withdraw.system_reject_request()
        wallet.refresh_from_db()
        assert wallet.balance == Decimal('1.16')
        diff = DiffChecker.check_wallet_diff(wallet)
        assert diff == Decimal('0')
        wallet_2 = Wallet.get_user_wallet(self.user2, Currencies.btc)
        diff = DiffChecker.check_wallet_diff(wallet_2)
        assert diff == Decimal('0')
