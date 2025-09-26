import datetime
import json
import time
import uuid
from datetime import timedelta
from decimal import Decimal
from threading import Thread
from typing import NoReturn
from unittest import mock
from unittest.mock import PropertyMock, patch

import pytest
from django.core.cache import cache
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils.timezone import now
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase, APITransactionTestCase

from exchange.accounts.models import BankAccount, Tag, User, UserRestriction, UserRestrictionRemoval, UserSms, UserTag
from exchange.accounts.userlevels import UserLevelManager
from exchange.base.calendar import ir_now
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.models import BABYDOGE, NOT_COIN, Currencies, Settings, get_currency_codename
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.features.models import QueueItem
from exchange.security.models import LoginAttempt
from exchange.wallet.estimator import PriceEstimator
from exchange.wallet.models import (
    AutomaticWithdraw,
    AutomaticWithdrawLog,
    AvailableDepositAddress,
    BlacklistWalletAddress,
    Wallet,
    WalletDepositAddress,
    WalletDepositTag,
    WithdrawRequest,
    WithdrawRequestLimit,
    WithdrawRequestPermit,
    WithdrawRequestRestriction,
)
from exchange.wallet.settlement import JibitSettlementV2, TomanSettlement
from exchange.wallet.withdraw import WithdrawProcessor, process_withdraws
from exchange.wallet.withdraw_method import AutomaticWithdrawMethod, ToncoinHLv2Withdraw
from exchange.wallet.withdraw_process import ProcessingWithdrawMethod, withdraw_method
from tests.base.utils import (
    TransactionTestFastFlushMixin,
    check_response,
    create_withdraw_request,
    temporary_withdraw_permissions,
)

withdraw_method_success_response = {'status': 'success', 'hash': '123'}


class WithdrawWithQueueTest(TransactionTestFastFlushMixin, TransactionTestCase):

    def setUp(self):
        super().setUp()
        withdraw_method['ton_hlv2_hotwallet'][0] = ToncoinHLv2Withdraw(running_with_queue=True)
        withdraw_method['ton_hlv2_hotwallet'][0].queue_wait_time = 1

        # Use get_or_create to avoid conflicts in CI
        self.user, _ = User.objects.get_or_create(
            username='withdraw-test-user-1', defaults={'email': 'withdraw-test-user-1@test.com'}
        )
        self.user2, _ = User.objects.get_or_create(
            username='withdraw-test-user-2', defaults={'email': 'withdraw-test-user-2@test.com'}
        )
        Wallet.create_user_wallets(self.user)
        Wallet.create_user_wallets(self.user2)
        self.rial_wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        self.system_rial_account = BankAccount.get_generic_system_account()
        PriceEstimator.get_price_range.clear()

    @patch('exchange.base.connections.load_key', return_value=('user', '1234'))
    @patch('exchange.wallet.withdraw_method.ToncoinHLv2Client.request', return_value=withdraw_method_success_response)
    def test_create_multi_transaction_from_queue(self, mocked_method, mocked_loadkey) -> NoReturn:
        """Test for ton coin.

        This test batch sending ton coin with queue.
        """
        # Create withdraw requests
        ton_withdraw_1 = create_withdraw_request(
            user=self.user,
            currency=Currencies.ton,
            address='UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
            amount=Decimal('3'),
            network='TON',
            status=WithdrawRequest.STATUS.new,
            tag='memo-1',
        )
        ton_withdraw_2 = create_withdraw_request(
            user=self.user,
            currency=Currencies.ton,
            address='UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
            amount=Decimal('4'),
            network='TON',
            status=WithdrawRequest.STATUS.new,
            tag='memo-2',
        )
        ton_withdraw_1.do_verify()
        ton_withdraw_2.do_verify()
        ton_withdraw_1.status = WithdrawRequest.STATUS.processing
        ton_withdraw_1.save()
        ton_withdraw_2.status = WithdrawRequest.STATUS.processing
        ton_withdraw_2.save()
        # Create auto withdraw object to process the withdraws
        a_withdraw_1 = AutomaticWithdraw.objects.create(
            withdraw=ton_withdraw_1, tp=AutomaticWithdraw.TYPE.ton_hlv2_hotwallet, status=AutomaticWithdraw.STATUS.new
        )
        a_withdraw_1.created_at = now() - datetime.timedelta(minutes=30)
        a_withdraw_1.save()
        a_withdraw_2 = AutomaticWithdraw.objects.create(
            withdraw=ton_withdraw_2, tp=AutomaticWithdraw.TYPE.ton_hlv2_hotwallet, status=AutomaticWithdraw.STATUS.new
        )
        a_withdraw_2.created_at = now() - datetime.timedelta(minutes=5)
        a_withdraw_2.save()
        withdraw_method['ton_hlv2_hotwallet'][0].max_multi_withdraw_size_from_queue = 2
        WithdrawProcessor[Currencies.ton].process_withdraws([ton_withdraw_1, ton_withdraw_2], status=WithdrawRequest.STATUS.processing)
        time.sleep(2)
        mocked_method.assert_called_once_with(
            method='create_multisend_transaction',
            params=[
                {
                    'outputs': [
                        {
                            'amount': '0.10000000',
                            'to': 'UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
                            'memo': 'memo-1',
                        },
                        {
                            'amount': '0.10000000',
                            'to': 'UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
                            'memo': 'memo-2',
                        }
                    ]
                },
                '1234',
            ],
            rpc_id='curltext',
        )
        withdraw_method['ton_hlv2_hotwallet'][0].shutdown()
        ton_withdraw_1.refresh_from_db()
        ton_withdraw_2.refresh_from_db()
        a_withdraw_1.refresh_from_db()
        a_withdraw_2.refresh_from_db()
        assert ton_withdraw_1.blockchain_url == 'https://testnet.tonscan.org/tx/123'
        assert ton_withdraw_2.blockchain_url == 'https://testnet.tonscan.org/tx/123'
        assert ton_withdraw_1.status == WithdrawRequest.STATUS.sent
        assert ton_withdraw_2.status == WithdrawRequest.STATUS.sent
        assert a_withdraw_1.status == AutomaticWithdraw.STATUS.done
        assert a_withdraw_2.status == AutomaticWithdraw.STATUS.done

    @patch('exchange.base.connections.load_key', return_value=('user', '1234'))
    @patch('exchange.wallet.withdraw_method.ToncoinHLv2Client.request', return_value=withdraw_method_success_response)
    def test_create_multi_transaction_from_queue_double_spend(self, mocked_method, mocked_loadkey) -> NoReturn:
        """Test for ton coin.

        This test batch sending ton coin with queue.
        """
        # Create withdraw requests
        ton_withdraw_1 = create_withdraw_request(
            user=self.user,
            currency=Currencies.ton,
            address='UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
            amount=Decimal('3'),
            network='TON',
            status=WithdrawRequest.STATUS.new,
            tag='memo-1',
        )
        ton_withdraw_1.do_verify()
        ton_withdraw_1.status = WithdrawRequest.STATUS.processing
        ton_withdraw_1.save()
        # Create auto withdraw object to process the withdraws
        a_withdraw_1 = AutomaticWithdraw.objects.create(
            withdraw=ton_withdraw_1, tp=AutomaticWithdraw.TYPE.ton_hlv2_hotwallet, status=AutomaticWithdraw.STATUS.new
        )
        a_withdraw_1.created_at = now() - datetime.timedelta(minutes=30)
        a_withdraw_1.save()
        withdraw_method['ton_hlv2_hotwallet'][0].max_multi_withdraw_size_from_queue = 1
        WithdrawProcessor[Currencies.ton].process_withdraws([ton_withdraw_1, ton_withdraw_1], status=WithdrawRequest.STATUS.processing)
        WithdrawProcessor[Currencies.ton].process_withdraws([ton_withdraw_1], status=WithdrawRequest.STATUS.processing)
        time.sleep(3)
        mocked_method.assert_called_once_with(
            method='create_multisend_transaction',
            params=[
                {
                    'outputs': [
                        {
                            'amount': '0.10000000',
                            'to': 'UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
                            'memo': 'memo-1',
                        }
                    ]
                },
                '1234',
            ],
            rpc_id='curltext',
        )
        withdraw_method['ton_hlv2_hotwallet'][0].shutdown()
        ton_withdraw_1.refresh_from_db()
        a_withdraw_1.refresh_from_db()
        assert ton_withdraw_1.blockchain_url == 'https://testnet.tonscan.org/tx/123'
        assert ton_withdraw_1.status == WithdrawRequest.STATUS.sent
        assert a_withdraw_1.status == AutomaticWithdraw.STATUS.done


    @patch('exchange.base.connections.load_key', return_value=('user', '1234'))
    @patch('exchange.wallet.withdraw_method.ToncoinHLv2Client.request', return_value=withdraw_method_success_response)
    def test_create_multi_transaction_from_queue_shutdown_phase(self, mocked_method, mocked_loadkey) -> NoReturn:
        """Test for ton coin.

        This test batch sending ton tokens with queue,
        but we shut down the queue before it sends all the transactions to test the shutdown phase.
        it should send all the withdrawals to the hot-wallet before shutdown.
        """
        # Create withdraw requests
        ton_withdraw_1 = create_withdraw_request(
            user=self.user,
            currency=Currencies.ton,
            address='UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
            amount=Decimal('3'),
            network='TON',
            status=WithdrawRequest.STATUS.new,
            tag='memo-1',
        )
        ton_withdraw_2 = create_withdraw_request(
            user=self.user,
            currency=Currencies.ton,
            address='UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
            amount=Decimal('4'),
            network='TON',
            status=WithdrawRequest.STATUS.new,
            tag='memo-2',
        )
        ton_withdraw_3 = create_withdraw_request(
            user=self.user,
            currency=Currencies.ton,
            address='UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
            amount=Decimal('1'),
            network='TON',
            status=WithdrawRequest.STATUS.new,
            tag='memo-3',
        )
        ton_withdraw_1.do_verify()
        ton_withdraw_2.do_verify()
        ton_withdraw_3.do_verify()
        ton_withdraw_1.status = WithdrawRequest.STATUS.processing
        ton_withdraw_1.save()
        ton_withdraw_2.status = WithdrawRequest.STATUS.processing
        ton_withdraw_2.save()
        ton_withdraw_3.status = WithdrawRequest.STATUS.processing
        ton_withdraw_3.save()
        # Create auto withdraw object to process the withdraws
        a_withdraw_1 = AutomaticWithdraw.objects.create(
            withdraw=ton_withdraw_1, tp=AutomaticWithdraw.TYPE.ton_hlv2_hotwallet, status=AutomaticWithdraw.STATUS.new
        )
        a_withdraw_1.created_at = now() - datetime.timedelta(minutes=30)
        a_withdraw_1.save()
        a_withdraw_2 = AutomaticWithdraw.objects.create(
            withdraw=ton_withdraw_2, tp=AutomaticWithdraw.TYPE.ton_hlv2_hotwallet, status=AutomaticWithdraw.STATUS.new
        )
        a_withdraw_2.created_at = now() - datetime.timedelta(minutes=5)
        a_withdraw_2.save()
        a_withdraw_3 = AutomaticWithdraw.objects.create(
            withdraw=ton_withdraw_3, tp=AutomaticWithdraw.TYPE.ton_hlv2_hotwallet, status=AutomaticWithdraw.STATUS.new
        )
        a_withdraw_3.created_at = now() - datetime.timedelta(minutes=5)
        a_withdraw_3.save()
        withdraw_method['ton_hlv2_hotwallet'][0].max_multi_withdraw_size_from_queue = 2
        WithdrawProcessor[Currencies.ton].process_withdraws([ton_withdraw_1, ton_withdraw_2], status=WithdrawRequest.STATUS.processing)
        time.sleep(2)
        mocked_method.assert_called_once_with(
            method='create_multisend_transaction',
            params=[
                {
                    'outputs': [
                        {
                            'amount': '0.10000000',
                            'to': 'UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
                            'memo': 'memo-1',
                        },
                        {
                            'amount': '0.10000000',
                            'to': 'UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
                            'memo': 'memo-2',
                        }
                    ]
                },
                '1234',
            ],
            rpc_id='curltext',
        )
        WithdrawProcessor[Currencies.ton].process_withdraws([ton_withdraw_3], status=WithdrawRequest.STATUS.processing)
        withdraw_method['ton_hlv2_hotwallet'][0].shutdown()
        ton_withdraw_1.refresh_from_db()
        ton_withdraw_2.refresh_from_db()
        ton_withdraw_3.refresh_from_db()
        a_withdraw_1.refresh_from_db()
        a_withdraw_2.refresh_from_db()
        a_withdraw_3.refresh_from_db()
        assert ton_withdraw_1.blockchain_url == 'https://testnet.tonscan.org/tx/123'
        assert ton_withdraw_2.blockchain_url == 'https://testnet.tonscan.org/tx/123'
        assert ton_withdraw_3.blockchain_url == 'https://testnet.tonscan.org/tx/123'
        assert ton_withdraw_1.status == WithdrawRequest.STATUS.sent
        assert ton_withdraw_2.status == WithdrawRequest.STATUS.sent
        assert ton_withdraw_3.status == WithdrawRequest.STATUS.sent
        assert a_withdraw_1.status == AutomaticWithdraw.STATUS.done
        assert a_withdraw_2.status == AutomaticWithdraw.STATUS.done
        assert a_withdraw_3.status == AutomaticWithdraw.STATUS.done


class WithdrawTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='withdraww-test-user1')
        cls.user2 = User.objects.create_user(username='withdraww-test-user2')
        Wallet.create_user_wallets(cls.user)
        Wallet.create_user_wallets(cls.user2)
        cls.rial_wallet = Wallet.get_user_wallet(cls.user, Currencies.rls)
        cls.system_rial_account = BankAccount.get_generic_system_account()
        PriceEstimator.get_price_range.clear()
        cls.processingWithdrawMethod = ProcessingWithdrawMethod(currency=Currencies.ton)

    def create_datetime(self, hour, minute):
        return ir_now().replace(hour=hour, minute=minute)

    def create_rial_withdraw(self, amount, fee=None):
        wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        tr1 = wallet.create_transaction(tp='manual', amount=amount + Decimal('1_000_000'))
        tr1.commit()
        wallet.refresh_from_db()
        request = WithdrawRequest.objects.create(
            wallet=wallet,
            status=WithdrawRequest.STATUS.new,
            target_account=self.system_rial_account,
            amount=amount,
            fee=fee,
        )
        request.fee = request.calculate_fee()
        return request

    def test_withdraw_settlement_method(self):
        w = WithdrawRequest()
        assert w.settlement_method is None
        w.blockchain_url = 'nobitex://app/wallet/rls/transaction/WJ3776917'
        assert w.settlement_method == WithdrawRequest.SETTLE_METHOD.jibit_v2
        w.blockchain_url = 'nobitex://app/wallet/rls/transaction/WV253762'
        assert w.settlement_method == WithdrawRequest.SETTLE_METHOD.vandar
        w.blockchain_url = 'nobitex://app/wallet/rls/transaction/WT253762'
        assert w.settlement_method == WithdrawRequest.SETTLE_METHOD.toman

    def test_get_settlement_manager(self):
        w = WithdrawRequest(id=3776917)
        assert w.get_settlement_manager() is None
        w.blockchain_url = 'nobitex://app/wallet/rls/transaction/WJ3776917'
        settlement_manager = w.get_settlement_manager()
        assert isinstance(settlement_manager, JibitSettlementV2)
        assert settlement_manager.uid == '3776917'
        assert settlement_manager.withdraw == w

        w.blockchain_url = 'nobitex://app/wallet/rls/transaction/WT3776917'
        settlement_manager = w.get_settlement_manager()
        assert isinstance(settlement_manager, TomanSettlement)
        assert settlement_manager.uid == '3776917'
        assert settlement_manager.withdraw == w

    def test_rial_withdraw_accept_dates(self):
        rial_withdraw = WithdrawRequest(
            wallet=Wallet.get_user_wallet(self.user, Currencies.rls),
            status=WithdrawRequest.STATUS.verified,
        )
        assert not rial_withdraw.can_automatically_send(timestamp=self.create_datetime(0, 44))
        assert not rial_withdraw.can_automatically_send(timestamp=self.create_datetime(7, 44))
        assert not rial_withdraw.can_automatically_send(timestamp=self.create_datetime(8, 30))
        assert rial_withdraw.can_automatically_send(timestamp=self.create_datetime(8, 40))
        assert not rial_withdraw.can_automatically_send(timestamp=self.create_datetime(8, 46))
        assert not rial_withdraw.can_automatically_send(timestamp=self.create_datetime(9, 0))
        assert rial_withdraw.can_automatically_send(timestamp=self.create_datetime(9, 45))
        assert rial_withdraw.can_automatically_send(timestamp=self.create_datetime(12, 45))
        assert rial_withdraw.can_automatically_send(timestamp=self.create_datetime(16, 45))
        assert rial_withdraw.can_automatically_send(timestamp=self.create_datetime(19, 45))
        assert rial_withdraw.can_automatically_send(timestamp=self.create_datetime(20, 45))
        assert not rial_withdraw.can_automatically_send(timestamp=self.create_datetime(20, 46))
        assert not rial_withdraw.can_automatically_send(timestamp=self.create_datetime(21, 45))
        assert not rial_withdraw.can_automatically_send(timestamp=self.create_datetime(22, 45))

    def test_rial_withdraw_calculate_fee(self):
        withdraw = self.create_rial_withdraw(Decimal('100_000_0'))
        assert withdraw.fee == Decimal('1_000_0')
        withdraw = self.create_rial_withdraw(Decimal('200_000_0'))
        assert withdraw.fee == Decimal('2_000_0')
        withdraw = self.create_rial_withdraw(Decimal('399_000_0'))
        assert withdraw.fee == Decimal('3_990_0')
        withdraw = self.create_rial_withdraw(Decimal('500_000_0'))
        assert withdraw.fee == Decimal('4_000_0')
        withdraw = self.create_rial_withdraw(Decimal('50_000_000_0'))
        assert withdraw.fee == Decimal('4_000_0')
        withdraw = self.create_rial_withdraw(Decimal('150_000_000_0'))
        assert withdraw.fee == Decimal('4_000_0')
        withdraw = self.create_rial_withdraw(Decimal('300_000_000_0'))
        assert withdraw.fee == Decimal('4_000_0')
        withdraw = self.create_rial_withdraw(Decimal('300_100_000_0'))
        assert withdraw.fee == Decimal('4_000_0')
        withdraw = self.create_rial_withdraw(Decimal('350_000_000_0'))
        assert withdraw.fee == Decimal('4_000_0')
        withdraw = self.create_rial_withdraw(Decimal('450_099_999_9'))
        assert withdraw.fee == Decimal('4_000_0')

    def test_rial_withdraw_no_split(self):
        rial_withdraw = self.create_rial_withdraw(Decimal('39_300_220_1'))
        rial_withdraw.do_verify()
        requests = WithdrawRequest.objects.filter(wallet=self.rial_wallet).order_by('id')
        assert len(requests) == 1
        assert requests[0].wallet == self.rial_wallet
        assert requests[0].status == WithdrawRequest.STATUS.verified
        assert requests[0].target_account == self.system_rial_account
        assert requests[0].amount == Decimal('39_300_220_1')
        assert requests[0].calculate_fee() == Decimal('4_000_0')
        # Equal to max withdraw
        rial_withdraw = self.create_rial_withdraw(Decimal('50_000_000_0'))
        rial_withdraw.do_verify()
        requests = WithdrawRequest.objects.filter(wallet=self.rial_wallet).order_by('id')
        assert len(requests) == 2
        assert requests[1].wallet == self.rial_wallet
        assert requests[1].status == WithdrawRequest.STATUS.verified
        assert requests[1].target_account == self.system_rial_account
        assert requests[1].amount == Decimal('50_000_000_0')
        assert requests[1].calculate_fee() == Decimal('4_000_0')
        # Small amount
        rial_withdraw = self.create_rial_withdraw(Decimal('76_345_1'))
        rial_withdraw.do_verify()
        requests = WithdrawRequest.objects.filter(wallet=self.rial_wallet).order_by('id')
        assert len(requests) == 3
        assert requests[2].wallet == self.rial_wallet
        assert requests[2].status == WithdrawRequest.STATUS.verified
        assert requests[2].target_account == self.system_rial_account
        assert requests[2].amount == Decimal('76_345_1')
        assert requests[2].calculate_fee() == Decimal('763_4')

    def test_rial_withdraw_split(self):
        rial_withdraw = self.create_rial_withdraw(Decimal('179_300_220_1'))
        rial_withdraw.do_verify()
        requests = WithdrawRequest.objects.filter(wallet=self.rial_wallet).order_by('id')
        assert len(requests) == 4
        for i in range(4):
            assert requests[i].wallet == self.rial_wallet
            assert requests[i].status == WithdrawRequest.STATUS.verified
            assert requests[i].target_account == self.system_rial_account
            if i < 3:
                assert requests[i].amount == Decimal('50_000_000_0')
            assert requests[i].fee == Decimal('4_000_0')
        assert requests[3].amount == Decimal('29_300_220_1')

    def test_rial_withdraw_split_vandar(self):
        rial_withdraw = self.create_rial_withdraw(Decimal('179_300_220_1'))
        rial_withdraw.target_account.bank_id = BankAccount.BANK_ID.vandar
        rial_withdraw.target_account.save()
        rial_withdraw.do_verify()
        requests = WithdrawRequest.objects.filter(wallet=self.rial_wallet).order_by('id')
        assert len(requests) == 2
        for i in range(2):
            assert requests[i].wallet == self.rial_wallet
            assert requests[i].status == WithdrawRequest.STATUS.verified
            assert requests[i].target_account == self.system_rial_account
            if i == 0:
                assert requests[i].amount == Decimal('100_000_000_0')
            assert requests[i].fee == Decimal('5_000_0')
        assert requests[1].amount == Decimal('79_300_220_1')

    def test_rial_withdraw_split_no_remaining(self):
        rial_withdraw = self.create_rial_withdraw(Decimal('150_000_000_0'))
        rial_withdraw.do_verify()
        requests = WithdrawRequest.objects.filter(wallet=self.rial_wallet).order_by('id')
        assert len(requests) == 3
        for i in range(3):
            assert requests[i].wallet == self.rial_wallet
            assert requests[i].status == WithdrawRequest.STATUS.verified
            assert requests[i].target_account == self.system_rial_account
            assert requests[i].amount == Decimal('50_000_000_0')
            assert requests[i].fee == Decimal('4_000_0')

    def test_rial_withdraw_split_with_adjust(self):
        rial_withdraw = self.create_rial_withdraw(Decimal('200_012_345_6'))
        rial_withdraw.do_verify()
        requests = WithdrawRequest.objects.filter(wallet=self.rial_wallet).order_by('id')
        assert len(requests) == 5
        for i in range(5):
            assert requests[i].wallet == self.rial_wallet
            assert requests[i].status == WithdrawRequest.STATUS.verified
            assert requests[i].target_account == self.system_rial_account
            if 0 < i < 4:
                assert requests[i].amount == Decimal('50_000_000_0')
            if 0 < i < 4:
                assert requests[i].fee == Decimal('4_000_0')
        assert requests[0].amount == Decimal('49_997_345_6')
        assert requests[0].fee == Decimal('4_000_0')
        assert requests[4].amount == Decimal('15_000_0')
        assert requests[4].fee == Decimal('150_0')

    def test_rial_withdraw_split_large_request(self):
        rial_withdraw = self.create_rial_withdraw(Decimal('450_099_999_9'))
        rial_withdraw.do_verify()
        requests = WithdrawRequest.objects.filter(wallet=self.rial_wallet).order_by('id')
        assert len(requests) == 10
        for i in range(10):
            assert requests[i].wallet == self.rial_wallet
            assert requests[i].status == WithdrawRequest.STATUS.verified
            assert requests[i].target_account == self.system_rial_account
            if i < 9:
                assert requests[i].amount == Decimal('50_000_000_0')
                assert requests[i].fee == Decimal('4_000_0')
        assert requests[9].amount == Decimal('99_999_9')
        assert requests[9].fee == Decimal('999_9')

    def test_withdraw_currency_fee(self):
        assert AutomaticWithdrawMethod.get_withdraw_fee(Currencies.bch, 'BCH') == Decimal('0.0005')
        assert AutomaticWithdrawMethod.get_withdraw_fee(Currencies.bch, 'BCH', Decimal('1')) == Decimal('0.0005')
        assert AutomaticWithdrawMethod.get_withdraw_fee(BABYDOGE, 'BSC') == Decimal('0.6')

    def test_withdraw_get_internal_target_wallet(self):
        address = '1Bm9ziyd4UmQpFiGD86ufHSniPtuq7paZh'
        wallet = Wallet.get_user_wallet(self.user, Currencies.bch)
        tr1 = wallet.create_transaction(tp='manual', amount=Decimal('1'))
        tr1.commit()
        wallet.refresh_from_db()
        withdraw = WithdrawRequest.objects.create(
            wallet=wallet,
            status=WithdrawRequest.STATUS.verified,
            target_address=address,
            amount=Decimal('0.5'),
            network='BCH',
        )
        assert withdraw.get_internal_target_wallet() is None
        # Create BTC address for user
        wallet2_btc = Wallet.get_user_wallet(self.user2, Currencies.btc)
        WalletDepositAddress.objects.create(
            wallet=wallet2_btc,
            currency=Currencies.btc,
            address=address,
        )
        wallet = withdraw.get_internal_target_wallet()
        assert wallet
        assert wallet.currency == Currencies.bch
        assert wallet.address == address
        # Check internal transfer process
        withdraw.status = WithdrawRequest.STATUS.accepted
        withdraw.save(update_fields=['status'])
        WithdrawProcessor[Currencies.bch].process_withdraws([withdraw], withdraw.status)
        assert withdraw.status == 5
        wallet2_bch = Wallet.get_user_wallet(self.user2, Currencies.bch)
        assert wallet2_bch.balance == Decimal('0.5')

    def test_harmony_withdraw_get_internal_target_wallet(self):
        from exchange.blockchain.segwit_address import eth_to_one_address

        harmony_eth_format_address = '0x8447779d6be9dc6ec28a9bfa879839f36d03c1f5'
        wallet_2 = Wallet.get_user_wallet(self.user, Currencies.one)
        tr1 = wallet_2.create_transaction(tp='manual', amount=Decimal('100'))
        tr1.commit()
        wallet_2.refresh_from_db()
        withdraw = WithdrawRequest.objects.create(
            wallet=wallet_2,
            status=WithdrawRequest.STATUS.verified,
            target_address=eth_to_one_address(harmony_eth_format_address),  # Nobitex harmony withdrawal -> ONE format
            amount=Decimal('55'),
            network='ONE',
        )
        assert withdraw.get_internal_target_wallet() is None

        # Create Harmony address for user
        wallet_one = Wallet.get_user_wallet(self.user2, Currencies.one)
        WalletDepositAddress.objects.create(
            wallet=wallet_one,
            currency=Currencies.one,
            address=harmony_eth_format_address,  # Nobitex harmony WalletDepositAddress -> ETH format
        )

        wallet = withdraw.get_internal_target_wallet()
        assert wallet
        assert wallet.currency == Currencies.one
        assert wallet.address == harmony_eth_format_address
        # Check internal transfer process
        withdraw.status = WithdrawRequest.STATUS.accepted
        withdraw.save(update_fields=['status'])
        WithdrawProcessor[Currencies.one].process_withdraws([withdraw], withdraw.status)
        assert withdraw.status == 5
        wallet_one = Wallet.get_user_wallet(self.user2, Currencies.one)
        assert wallet_one.balance == Decimal('55')

    def test_withdraw_get_internal_case_insensitive_target_wallet(self):
        eth_like_address = '0x7b94c06E6CBa8a763B3fC0f8a73A2230d7579dB0'
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt)
        tr1 = wallet.create_transaction(tp='manual', amount=Decimal('1'))
        tr1.commit()
        wallet.refresh_from_db()
        withdraw = WithdrawRequest.objects.create(
            wallet=wallet,
            status=WithdrawRequest.STATUS.verified,
            target_address=eth_like_address,
            amount=Decimal('0.5'),
            network='BSC',
        )
        assert withdraw.get_internal_target_wallet() is None
        # Create BSC address for user
        wallet2 = Wallet.get_user_wallet(self.user2, Currencies.usdt)
        # To test target address in lowercase format
        eth_like_address_lower = eth_like_address.lower()
        WalletDepositAddress.objects.create(
            wallet=wallet2,
            currency=Currencies.usdt,
            address=eth_like_address_lower,
            network='BSC',
        )
        wallet = withdraw.get_internal_target_wallet()
        assert wallet
        assert wallet.currency == Currencies.usdt
        assert wallet.address == eth_like_address_lower
        # Check internal transfer process
        withdraw.status = WithdrawRequest.STATUS.accepted
        withdraw.save(update_fields=['status'])
        WithdrawProcessor[Currencies.usdt].process_withdraws([withdraw], withdraw.status)
        assert withdraw.status == 5
        wallet2 = Wallet.get_user_wallet(self.user2, Currencies.usdt)
        assert wallet2.balance == Decimal('0.5')

    def test_withdraw_log_with_large_description(self):
        s = 'x' * 2000
        log = AutomaticWithdrawLog.objects.create(
            withdraw=self.create_rial_withdraw(Decimal('10_000_000_0')),
            description=s,
        )
        log.refresh_from_db()
        assert log.description == 'x' * 1000

    def test_is_eligible_to_withdraw(self):
        user = self.user
        amount, rls = Decimal('1_000_000_0'), Currencies.rls
        trx_amount, trx = Decimal('1_000'), Currencies.trx
        cache.set('orderbook_TRXIRT_best_active_buy', Decimal('12690'))
        # Check low levels limitations
        user.user_type = User.USER_TYPES.level0
        assert not UserLevelManager.is_eligible_to_withdraw(user, rls, amount)
        assert not UserLevelManager.is_eligible_to_withdraw(user, trx, trx_amount)
        user.user_type = User.USER_TYPES.trader
        assert UserLevelManager.is_eligible_to_withdraw(user, rls, amount)
        assert not UserLevelManager.is_eligible_to_withdraw(user, trx, trx_amount)
        # Check level1 limits and increasing limits
        user.user_type = User.USER_TYPES.level1
        assert UserLevelManager.is_eligible_to_withdraw(user, rls, Decimal('15_000_000_0'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, rls, Decimal('50_100_000_0'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, trx, Decimal('500'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, trx, Decimal('1_000'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, trx, Decimal('80_000'))
        user.get_verification_profile().mobile_identity_confirmed = True
        assert UserLevelManager.is_eligible_to_withdraw(user, trx, Decimal('500'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, trx, Decimal('1_000'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, trx, Decimal('80_000'))
        # Check level 2 limits
        user.user_type = User.USER_TYPES.level2
        user.get_verification_profile().mobile_identity_confirmed = False
        assert UserLevelManager.is_eligible_to_withdraw(user, rls, Decimal('300_000_000_0'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, rls, Decimal('300_100_000_0'))
        assert UserLevelManager.is_eligible_to_withdraw(user, trx, Decimal('5_000'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, trx, Decimal('8_000'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, trx, Decimal('80_000'))
        user.get_verification_profile().mobile_identity_confirmed = True
        assert UserLevelManager.is_eligible_to_withdraw(user, trx, Decimal('150_000'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, trx, Decimal('250_000'))

        # Check level 4 limits
        user.user_type = User.USER_TYPES.trusted
        user.get_verification_profile().mobile_identity_confirmed = False
        assert UserLevelManager.is_eligible_to_withdraw(user, rls, Decimal('100_000_000_000_0'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, rls, Decimal('100_000_000_000_1'))

        user.user_type = User.USER_TYPES.level1
        user.get_verification_profile().mobile_identity_confirmed = False
        limit1 = WithdrawRequestLimit.objects.create(
            user=user, tp=WithdrawRequestLimit.LIMITATION_TYPE.daily_rial,
            limitation=Decimal('21_000_000_0'))
        assert UserLevelManager.is_eligible_to_withdraw(user, rls, Decimal('20_100_000_0'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, trx, Decimal('80_000'))
        limit2 = WithdrawRequestLimit.objects.create(
            user=user, tp=WithdrawRequestLimit.LIMITATION_TYPE.daily_coin,
            limitation=Decimal('150_000_000_0'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, trx, Decimal('100_000'))
        limit3 = WithdrawRequestLimit.objects.create(
            user=user, tp=WithdrawRequestLimit.LIMITATION_TYPE.daily_sum,
            limitation=Decimal('150_000_000_0'))
        # Check deleting limitations
        assert UserLevelManager.is_eligible_to_withdraw(user, trx, Decimal('100_000'))
        limit1.delete()
        assert not UserLevelManager.is_eligible_to_withdraw(user, rls, Decimal('50_100_000_0'))
        limit2.delete()
        assert not UserLevelManager.is_eligible_to_withdraw(user, trx, Decimal('80_000'))
        # Check level2 and limit restriction
        user.user_type = User.USER_TYPES.level2
        user.get_verification_profile().mobile_identity_confirmed = True
        assert not UserLevelManager.is_eligible_to_withdraw(user, rls, Decimal('300_000_000_0'))
        limit3.delete()
        assert UserLevelManager.is_eligible_to_withdraw(user, rls, Decimal('300_000_000_0'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, rls, Decimal('301_000_000_0'))
        limit4 = WithdrawRequestLimit.objects.create(
            user=user, tp=WithdrawRequestLimit.LIMITATION_TYPE.daily_rial,
            limitation=Decimal('310_000_000_0'))
        assert UserLevelManager.is_eligible_to_withdraw(user, rls, Decimal('301_000_000_0'))
        assert UserLevelManager.is_eligible_to_withdraw(user, trx, Decimal('155_000'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, trx, Decimal('250_000'))

    def test_is_eligible_to_withdraw_per_currency(self):
        user = self.user
        cache.set('orderbook_DOGEIRT_best_active_buy', Decimal('11_145_0'))
        cache.set('orderbook_BTCIRT_best_active_buy', Decimal('1_008_542_203_0'))
        btc, doge = Currencies.btc, Currencies.doge
        # Check default user type limits
        user.user_type = User.USER_TYPES.level2
        user.get_verification_profile().mobile_identity_confirmed = True
        assert UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('10_000'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('27_000'))
        assert UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.1'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.3'))
        # Add restriction for currency
        doge_limit = WithdrawRequestLimit.objects.create(
            user=user, tp=WithdrawRequestLimit.LIMITATION_TYPE.daily_currency,
            currency=doge, limitation=Decimal('5_000'))
        btc_limit = WithdrawRequestLimit.objects.create(
            user=user, tp=WithdrawRequestLimit.LIMITATION_TYPE.daily_currency,
            currency=btc, limitation=Decimal('0.06'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('10_000'))
        assert UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('5_000'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.1'))
        assert UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.05'))
        # Check existing withdraws
        create_withdraw_request(user, doge, '250')
        assert not UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('5_000'))
        assert UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('4_750'))
        create_withdraw_request(user, btc, '0.01')
        assert not UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.051'))
        assert UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.045'))
        create_withdraw_request(user, doge, '1000')
        assert not UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('4_750'))
        assert UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('3_750'))
        assert UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.04'))
        # Allow after deleting limit
        doge_limit.delete()
        assert UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('10_000'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.1'))
        btc_limit.delete()
        assert UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('10_000'))
        assert UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.1'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('27_000'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.3'))

    def test_is_eligible_to_withdraw_with_both_restrictions(self):
        user = self.user
        cache.set('orderbook_DOGEIRT_best_active_buy', Decimal('11_145_0'))
        cache.set('orderbook_BTCIRT_best_active_buy', Decimal('1_008_542_203_0'))
        btc, doge = Currencies.btc, Currencies.doge
        user.user_type = User.USER_TYPES.level2
        user.get_verification_profile().mobile_identity_confirmed = True
        assert UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('10_000'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('27_000'))
        assert UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.1'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.3'))
        WithdrawRequestRestriction.objects.create(
            tp=WithdrawRequestLimit.LIMITATION_TYPE.daily_currency,
            currency=doge,
            network='DOGE',
            limitation=Decimal('5_000')
        )
        WithdrawRequestRestriction.objects.create(
            tp=WithdrawRequestLimit.LIMITATION_TYPE.daily_currency,
            currency=btc,
            network='BTC',
            limitation=Decimal('0.06')
        )
        WithdrawRequestLimit.objects.create(
            user=user,
            tp=WithdrawRequestLimit.LIMITATION_TYPE.daily_currency,
            currency=doge,
            limitation=Decimal('3_000')
        )
        WithdrawRequestLimit.objects.create(
            user=user,
            tp=WithdrawRequestLimit.LIMITATION_TYPE.daily_currency,
            currency=btc,
            limitation=Decimal('0.03')
        )
        assert not UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('4_000'), network='doge')
        assert UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('2_000'), network='doge')
        assert not UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.04'), network='btc')
        assert UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.001'), network='btc')

    def test_is_eligible_to_withdraw_total_restriction(self):
        user = self.user
        cache.set('orderbook_DOGEIRT_best_active_buy', Decimal('11_145_0'))
        cache.set('orderbook_BTCIRT_best_active_buy', Decimal('1_008_542_203_0'))
        btc, doge = Currencies.btc, Currencies.doge
        # Check default user type limits
        user.user_type = User.USER_TYPES.level2
        user.get_verification_profile().mobile_identity_confirmed = True
        assert UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('10_000'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('27_000'))
        assert UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.1'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.3'))
        # Add restriction for currency
        doge_limit = WithdrawRequestRestriction.objects.create(
             tp=WithdrawRequestLimit.LIMITATION_TYPE.daily_currency,
            currency=doge,
            network='DOGE',
            limitation=Decimal('5_000'))
        btc_limit = WithdrawRequestRestriction.objects.create(
            tp=WithdrawRequestLimit.LIMITATION_TYPE.daily_currency,
            currency=btc,
            network='BTC',
            limitation=Decimal('0.06'))
        assert not UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('10_000'), network='doge')
        assert UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('5_000'), network='doge')
        assert not UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.1'), network='btc')
        assert UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.05'), network='btc')
        # Check existing withdraws
        create_withdraw_request(user, doge, '250', network='DOGE')
        assert not UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('5_000'), network='doge')
        assert UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('4_750'), network='doge')
        create_withdraw_request(user, btc, '0.01', network='BTC')
        assert not UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.051'), network='btc')
        assert UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.045'), network='btc')
        create_withdraw_request(user, doge, '1000', network='DOGE')
        assert not UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('4_750'), network='doge')
        assert UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('3_750'), network='doge')
        assert UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.04'), network='btc')
        # Allow after deleting limit
        doge_limit.delete()
        assert UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('10_000'), network='doge')
        assert not UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.1'), network='btc')
        btc_limit.delete()
        assert UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('10_000'), network='doge')
        assert UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.1'), network='btc')
        assert not UserLevelManager.is_eligible_to_withdraw(user, doge, Decimal('27_000'), network='doge')
        assert not UserLevelManager.is_eligible_to_withdraw(user, btc, Decimal('0.3'), network='btc')

    def test_is_eligible_to_withdraw_no_restriction(self):
        self.user.user_type = User.USER_TYPES.level2
        self.user.email = 'test@nobitex.ir'
        Settings.set('unlimited_withdraw_users', json.dumps([self.user.email]))
        WithdrawRequestRestriction.objects.create(
            currency=Currencies.btc,
            network='BTC',
            limitation=Decimal('0.01'),
            tp=WithdrawRequestLimit.LIMITATION_TYPE.daily_currency,
        )
        assert UserLevelManager.is_eligible_to_withdraw(self.user, Currencies.btc, Decimal('0.3'), network='BTC')

    def test_blacklist_withdraw(self):
        address = '1Bm9ziyd4UmQpFiGD86ufHSniPtuq7paZh'
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        WalletDepositAddress.objects.create(wallet=wallet, currency=wallet.currency, address=address)
        blacklist = BlacklistWalletAddress.objects.create(address=address, is_withdraw=True, is_deposit=False)
        assert not self.user.restrictions.filter(restriction=UserRestriction.RESTRICTION.WithdrawRequest).exists()
        withdraw = WithdrawRequest(wallet=wallet, target_address=address, amount=Decimal('0.5'))
        assert withdraw.is_in_blacklist()
        withdraw.save()
        assert self.user.restrictions.filter(restriction=UserRestriction.RESTRICTION.WithdrawRequest).exists()

        blacklist.is_active = False
        blacklist.save(update_fields=('is_active',))
        assert not withdraw.is_in_blacklist()

        blacklist.is_active = True
        blacklist.currency = Currencies.btc
        blacklist.save(update_fields=('is_active', 'currency'))
        assert withdraw.is_in_blacklist()

        blacklist.currency = Currencies.doge
        blacklist.save(update_fields=('currency',))
        assert not withdraw.is_in_blacklist()

        blacklist.currency = None
        blacklist.address = 'fooBar'
        blacklist.save(update_fields=('currency', 'address'))
        assert not withdraw.is_in_blacklist()

    def test_blacklist_deposit_address_for_withdraw(self):
        address = '1Bm9ziyd4UmQpFiGD86ufHSniPtuq7paZh'
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        WalletDepositAddress.objects.create(wallet=wallet, currency=wallet.currency, address=address)
        BlacklistWalletAddress.objects.create(address=address, is_withdraw=False, is_deposit=True)
        assert not self.user.restrictions.filter(restriction=UserRestriction.RESTRICTION.WithdrawRequest).exists()
        withdraw = WithdrawRequest(wallet=wallet, target_address=address, amount=Decimal('0.5'))
        assert not withdraw.is_in_blacklist()
        withdraw.save()
        assert not self.user.restrictions.filter(restriction=UserRestriction.RESTRICTION.WithdrawRequest).exists()

    def test_blacklist_withdraw_address_case_insensitive(self):
        address = '1Bm9ziyd4UmQpFiGD86ufHSniPtuq7paZh'
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        WalletDepositAddress.objects.create(wallet=wallet, currency=wallet.currency, address=address)
        blacklist = BlacklistWalletAddress.objects.create(address=address, is_withdraw=True, is_deposit=False)
        assert not self.user.restrictions.filter(restriction=UserRestriction.RESTRICTION.WithdrawRequest).exists()
        withdraw = WithdrawRequest(wallet=wallet, target_address=address.lower(), amount=Decimal('0.5'))
        assert withdraw.is_in_blacklist()
        withdraw.save()
        assert self.user.restrictions.filter(restriction=UserRestriction.RESTRICTION.WithdrawRequest).exists()

    @override_settings(IS_TESTNET=True, WITHDRAW_CREATE_TX_VERIFY=False)
    def test_testnet_withdraw_process(self):
        address = Wallet.get_user_wallet(self.user2, Currencies.btc).get_current_deposit_address(create=True, network='BTC')
        withdraw = create_withdraw_request(
            self.user, Currencies.btc, amount='0.1', address=address.address,
            status=3, created_at=now(), network='BTC', withdraw_type=WithdrawRequest.TYPE.internal
        )
        withdraw_2 = create_withdraw_request(
            self.user, Currencies.btc, amount='0.1', address='327ySURPg6JS1awGKteGMSCrq7DFsASjCH',
            status=3, created_at=now(), network='BTC',
        )
        Settings.set("withdraw_enabled", "yes")
        process_withdraws()
        withdraw.refresh_from_db()
        assert withdraw.status == 5
        assert withdraw_2.status == 3

    @patch(
        'exchange.wallet.withdraw_method.ToncoinTokenHLv2Withdraw.network',
        new_callable=PropertyMock,
        return_value='mainnet',
    )
    @patch('exchange.base.connections.load_key', return_value=('user', '1234'))
    @patch('exchange.wallet.withdraw_method.ToncoinHLv2Client.request', return_value=withdraw_method_success_response)
    def test_batch_withdraw_token_notcoin(self, mocked_method, *args) -> NoReturn:
        """Test for not coin.

        This test batch sending ton tokens like not coin.
        """
        # Create withdraw requests
        not_withdraw_1 = create_withdraw_request(
            user=self.user,
            currency=NOT_COIN,
            address='UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
            amount=Decimal('1000'),
            network='TON',
            status=1,
            tag='memo1',
        )
        not_withdraw_2 = create_withdraw_request(
            user=self.user,
            currency=NOT_COIN,
            address='UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
            amount=Decimal('1000'),
            network='TON',
            status=1,
            tag='memo2',
        )
        not_withdraw_1.do_verify()
        not_withdraw_2.do_verify()
        not_withdraw_1.status = 7
        not_withdraw_1.save()
        not_withdraw_2.status = 7
        not_withdraw_2.save()
        # Create autowithdraw object to process the withdraws
        a_withdraw_1 = AutomaticWithdraw.objects.create(
            withdraw=not_withdraw_1, tp=AutomaticWithdraw.TYPE.ton_token_hlv2_hotwallet, status=0
        )
        a_withdraw_1.created_at = now() - datetime.timedelta(minutes=40)
        a_withdraw_1.save()
        a_withdraw_2 = AutomaticWithdraw.objects.create(
            withdraw=not_withdraw_2, tp=AutomaticWithdraw.TYPE.ton_token_hlv2_hotwallet, status=0
        )
        a_withdraw_2.created_at = now() - datetime.timedelta(minutes=4)
        a_withdraw_2.save()

        WithdrawProcessor[NOT_COIN].process_withdraws([not_withdraw_1, not_withdraw_2], 7)
        mocked_method.assert_called_once_with(
            method='create_multisend_token_transaction',
            params={
                'outputs': [
                    {
                        'to': 'UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
                        'amount': '0.100000000',
                        'contract': 'EQAvlWFDxGF2lXm67y4yzC17wYKD9A0guwPkMs1gOsM__NOT',
                        'memo': 'memo1',
                    },
                    {
                        'to': 'UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
                        'amount': '0.100000000',
                        'contract': 'EQAvlWFDxGF2lXm67y4yzC17wYKD9A0guwPkMs1gOsM__NOT',
                        'memo': 'memo2',
                    },
                ],
                'password': '1234',
            },
            rpc_id='curltext',
        )
        not_withdraw_1.refresh_from_db()
        not_withdraw_2.refresh_from_db()
        assert not_withdraw_1.blockchain_url == 'https://testnet.tonscan.org/tx/123'
        assert not_withdraw_2.blockchain_url == 'https://testnet.tonscan.org/tx/123'

    @patch(
        'exchange.wallet.withdraw_method.ToncoinTokenHLv2Withdraw.network',
        new_callable=PropertyMock,
        return_value='mainnet',
    )
    @patch('exchange.base.connections.load_key', return_value=('user', '1234'))
    @patch('exchange.wallet.withdraw_method.ToncoinHLv2Client.request', return_value=withdraw_method_success_response)
    def test_batch_withdraw_token_toncoin_multi_hot(self, mocked_method, *args) -> NoReturn:
        """Test for not coin.

        This test batch sending ton tokens like not coin.
        """
        # Create withdraw requests
        ton_withdraw_1 = create_withdraw_request(
            user=self.user,
            currency=Currencies.ton,
            address='UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
            amount=Decimal('1000'),
            network='TON',
            status=1,
            tag='memo1',
            pk=100,
        )
        ton_withdraw_2 = create_withdraw_request(
            user=self.user,
            currency=Currencies.ton,
            address='UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
            amount=Decimal('1000'),
            network='TON',
            status=1,
            tag='memo2',
            pk=101,
        )
        ton_withdraw_1.do_verify()
        ton_withdraw_2.do_verify()
        ton_withdraw_1.status = WithdrawRequest.STATUS.verified
        ton_withdraw_1.save()
        ton_withdraw_2.status = WithdrawRequest.STATUS.verified
        ton_withdraw_2.save()

        # Process withdraws
        Settings.set("withdraw_enabled", "yes")
        process_withdraws(hotwallet_numbers=2)
        ton_withdraw_1.refresh_from_db()
        ton_withdraw_2.refresh_from_db()
        assert ton_withdraw_1.status == WithdrawRequest.STATUS.accepted
        assert ton_withdraw_2.status == WithdrawRequest.STATUS.verified

        process_withdraws(hotwallet_index=1, hotwallet_numbers=2)
        ton_withdraw_1.refresh_from_db()
        ton_withdraw_2.refresh_from_db()

        assert ton_withdraw_1.status == WithdrawRequest.STATUS.accepted
        assert ton_withdraw_2.status == WithdrawRequest.STATUS.accepted

        # Process withdraws
        process_withdraws(hotwallet_numbers=2)
        ton_withdraw_1.refresh_from_db()
        ton_withdraw_2.refresh_from_db()
        assert ton_withdraw_1.status == WithdrawRequest.STATUS.processing
        assert ton_withdraw_2.status == WithdrawRequest.STATUS.accepted

        process_withdraws(hotwallet_index=1, hotwallet_numbers=2)
        ton_withdraw_1.refresh_from_db()
        ton_withdraw_2.refresh_from_db()

        assert ton_withdraw_1.status == WithdrawRequest.STATUS.processing
        assert ton_withdraw_2.status == WithdrawRequest.STATUS.processing

        # Modify created_at in auto withdraw object
        a_withdraw_1 = AutomaticWithdraw.objects.get(withdraw=ton_withdraw_1)
        a_withdraw_2 = AutomaticWithdraw.objects.get(withdraw=ton_withdraw_2)
        a_withdraw_1.created_at = now() - datetime.timedelta(minutes=10)
        a_withdraw_1.save()
        a_withdraw_2.created_at = now() - datetime.timedelta(minutes=10)
        a_withdraw_2.save()

        # Process withdraws
        process_withdraws(hotwallet_numbers=2)
        ton_withdraw_1.refresh_from_db()
        ton_withdraw_2.refresh_from_db()
        assert ton_withdraw_1.status == WithdrawRequest.STATUS.sent
        assert ton_withdraw_2.status == WithdrawRequest.STATUS.processing

        process_withdraws(hotwallet_index=1, hotwallet_numbers=2)
        ton_withdraw_1.refresh_from_db()
        ton_withdraw_2.refresh_from_db()

        assert ton_withdraw_1.status == WithdrawRequest.STATUS.sent
        assert ton_withdraw_2.status == WithdrawRequest.STATUS.sent

        assert ton_withdraw_1.blockchain_url == 'https://testnet.tonscan.org/tx/123'
        assert ton_withdraw_2.blockchain_url == 'https://testnet.tonscan.org/tx/123'

        # Assert url of withdraw method
        assert withdraw_method['ton_hlv2_hotwallet'][0].get_withdraw_client().url == 'http://localhost:6071'
        assert withdraw_method['ton_hlv2_hotwallet'][1].get_withdraw_client().url == 'http://localhost:6072'

    @patch(
        'exchange.wallet.withdraw_method.ToncoinTokenHLv2Withdraw.network',
        new_callable=PropertyMock,
        return_value='mainnet',
    )
    @patch('exchange.base.connections.load_key', return_value=('user', '1234'))
    @patch('exchange.wallet.withdraw_method.ToncoinHLv2Client.request', return_value=withdraw_method_success_response)
    def test_batch_withdraw_token_toncoin_without_multi_hot(self, mocked_method, *args) -> NoReturn:
        """Test for not coin.

        This test batch sending ton tokens like not coin.
        """
        # Create withdraw requests
        ton_withdraw_1 = create_withdraw_request(
            user=self.user,
            currency=Currencies.ton,
            address='UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
            amount=Decimal('1000'),
            network='TON',
            status=1,
            tag='memo1',
            pk=100,
        )
        ton_withdraw_2 = create_withdraw_request(
            user=self.user,
            currency=Currencies.ton,
            address='UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
            amount=Decimal('1000'),
            network='TON',
            status=1,
            tag='memo2',
            pk=101,
        )
        ton_withdraw_1.do_verify()
        ton_withdraw_2.do_verify()
        ton_withdraw_1.status = WithdrawRequest.STATUS.verified
        ton_withdraw_1.save()
        ton_withdraw_2.status = WithdrawRequest.STATUS.verified
        ton_withdraw_2.save()

        # Process withdraws
        Settings.set("withdraw_enabled", "yes")
        process_withdraws()
        ton_withdraw_1.refresh_from_db()
        ton_withdraw_2.refresh_from_db()
        assert ton_withdraw_1.status == WithdrawRequest.STATUS.accepted
        assert ton_withdraw_2.status == WithdrawRequest.STATUS.accepted

        # Process withdraws
        process_withdraws()
        ton_withdraw_1.refresh_from_db()
        ton_withdraw_2.refresh_from_db()
        assert ton_withdraw_1.status == WithdrawRequest.STATUS.processing
        assert ton_withdraw_2.status == WithdrawRequest.STATUS.processing

        # Modify created_at in auto withdraw object
        a_withdraw_1 = AutomaticWithdraw.objects.get(withdraw=ton_withdraw_1)
        a_withdraw_2 = AutomaticWithdraw.objects.get(withdraw=ton_withdraw_2)
        a_withdraw_1.created_at = now() - datetime.timedelta(minutes=10)
        a_withdraw_1.save()
        a_withdraw_2.created_at = now() - datetime.timedelta(minutes=10)
        a_withdraw_2.save()

        # Process withdraws
        process_withdraws()
        ton_withdraw_1.refresh_from_db()
        ton_withdraw_2.refresh_from_db()
        assert ton_withdraw_1.status == WithdrawRequest.STATUS.sent
        assert ton_withdraw_2.status == WithdrawRequest.STATUS.sent

        assert ton_withdraw_1.blockchain_url == 'https://testnet.tonscan.org/tx/123'
        assert ton_withdraw_2.blockchain_url == 'https://testnet.tonscan.org/tx/123'

    @patch('exchange.base.connections.load_key', return_value=('user', '1234'))
    @patch('exchange.wallet.withdraw_method.ToncoinHLv2Client.request', return_value=withdraw_method_success_response)
    def test_batch_withdraw_ton(self, mocked_method, mocked_loadkey) -> NoReturn:
        """Test for not coin.

        This test batch sending ton tokens like not coin.
        """
        # Create withdraw requests
        ton_withdraw_1 = create_withdraw_request(
            user=self.user,
            currency=Currencies.ton,
            address='UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
            amount=Decimal('1'),
            network='TON',
            status=1,
            tag='memo1',
        )
        ton_withdraw_2 = create_withdraw_request(
            user=self.user,
            currency=Currencies.ton,
            address='UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
            amount=Decimal('2'),
            network='TON',
            status=1,
            tag='memo2',
        )
        ton_withdraw_1.do_verify()
        ton_withdraw_2.do_verify()
        ton_withdraw_1.status = 7
        ton_withdraw_1.save()
        ton_withdraw_2.status = 7
        ton_withdraw_2.save()
        # Create autowithdraw object to process the withdraws
        a_withdraw_1 = AutomaticWithdraw.objects.create(
            withdraw=ton_withdraw_1, tp=AutomaticWithdraw.TYPE.ton_hlv2_hotwallet, status=0
        )
        a_withdraw_1.created_at = now() - datetime.timedelta(minutes=40)
        a_withdraw_1.save()
        a_withdraw_2 = AutomaticWithdraw.objects.create(
            withdraw=ton_withdraw_2, tp=AutomaticWithdraw.TYPE.ton_hlv2_hotwallet, status=0
        )
        a_withdraw_2.created_at = now() - datetime.timedelta(minutes=4)
        a_withdraw_2.save()

        WithdrawProcessor[Currencies.ton].process_withdraws([ton_withdraw_1, ton_withdraw_2], 7)
        mocked_method.assert_called_once_with(
            method='create_multisend_transaction',
            params=[
                {
                    'outputs': [
                        {
                            'amount': '0.10000000',
                            'to': 'UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
                            'memo': 'memo1',
                        },
                        {
                            'amount': '0.10000000',
                            'to': 'UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
                            'memo': 'memo2',
                        },
                    ]
                },
                '1234',
            ],
            rpc_id='curltext',
        )
        ton_withdraw_1.refresh_from_db()
        ton_withdraw_2.refresh_from_db()
        assert ton_withdraw_1.blockchain_url == 'https://testnet.tonscan.org/tx/123'
        assert ton_withdraw_2.blockchain_url == 'https://testnet.tonscan.org/tx/123'

    def test_tagcoins_internal_withdraw(self):
        AvailableDepositAddress.objects.create(
            currency=Currencies.ton, address='EQDomrTUCdh_yzZT8R2Pw5A7LIlXWRWIwKyJxV2boi9cFegy'
        )
        user1_dogs_wallet = Wallet.get_user_wallet(user=self.user, currency=Currencies.dogs)
        user1_dogs_wallet.balance = Decimal('1000000')
        user1_dogs_wallet.save()
        user2_ton_wallet = Wallet.get_user_wallet(user=self.user2, currency=Currencies.ton)
        user2_ton_tag = user2_ton_wallet.get_current_deposit_tag(create=True)
        # so far user2 hasnt dogs
        assert not WalletDepositTag.objects.filter(wallet__user=self.user2, currency=Currencies.dogs).exists()

        dogs_withdraw = create_withdraw_request(
            user=self.user,
            currency=Currencies.dogs,
            address='EQDomrTUCdh_yzZT8R2Pw5A7LIlXWRWIwKyJxV2boi9cFegy',
            amount=Decimal('1000'),
            network='TON',
            status=1,
            tag=str(user2_ton_tag.tag),
        )
        dogs_withdraw.do_verify()
        WithdrawProcessor[Currencies.dogs].process_withdraws([dogs_withdraw], 2)
        dogs_withdraw.refresh_from_db()
        # this makes sure internal transfer process makes the target wallet for the destination user if needed
        assert (
            dogs_withdraw.get_internal_target_wallet()
            == WalletDepositTag.objects.filter(wallet__user=self.user2, currency=Currencies.dogs).first()
        )

    @patch('exchange.base.connections.load_key', return_value=('user', '1234'))
    @patch('exchange.wallet.withdraw_method.ToncoinHLv2Client.request', return_value=withdraw_method_success_response)
    def test_tagcoins_internal_withdraw_invalid_tag(self, mocked_method, mocked_loadkey):
        AvailableDepositAddress.objects.create(
            currency=Currencies.ton, address='EQDomrTUCdh_yzZT8R2Pw5A7LIlXWRWIwKyJxV2boi9cFegy'
        )
        user1_ton_wallet = Wallet.get_user_wallet(user=self.user, currency=Currencies.ton)
        user1_ton_wallet.balance = Decimal('1000000')
        user1_ton_wallet.save()

        ton_withdraw = create_withdraw_request(
            user=self.user,
            currency=Currencies.ton,
            address='EQDomrTUCdh_yzZT8R2Pw5A7LIlXWRWIwKyJxV2boi9cFegy',
            amount=Decimal('1000'),
            network='TON',
            status=WithdrawRequest.STATUS.new,
            tag="test",
        )
        ton_withdraw.do_verify()
        WithdrawProcessor[Currencies.ton].process_withdraws([ton_withdraw], WithdrawRequest.STATUS.verified)
        ton_withdraw.refresh_from_db()
        assert ton_withdraw.status == WithdrawRequest.STATUS.accepted
        assert ton_withdraw.auto_withdraw.status == AutomaticWithdraw.STATUS.accepted

        ton_withdraw.auto_withdraw.created_at = now() - datetime.timedelta(minutes=40)
        WithdrawProcessor[Currencies.ton].process_withdraws([ton_withdraw], WithdrawRequest.STATUS.accepted)
        ton_withdraw.refresh_from_db()
        assert ton_withdraw.status == WithdrawRequest.STATUS.processing
        assert ton_withdraw.auto_withdraw.status == AutomaticWithdraw.STATUS.failed

        WithdrawProcessor[Currencies.ton].process_withdraws([ton_withdraw], WithdrawRequest.STATUS.processing)
        ton_withdraw.refresh_from_db()
        assert ton_withdraw.status == WithdrawRequest.STATUS.processing
        assert ton_withdraw.auto_withdraw.status == AutomaticWithdraw.STATUS.failed
        mocked_method.assert_not_called()

    @patch('exchange.base.connections.load_key', return_value=('user', '1234'))
    @patch('exchange.wallet.withdraw_method.ToncoinHLv2Client.request', return_value=withdraw_method_success_response)
    def test_tagcoins_internal_withdraw_without_tag(self, mocked_method, mocked_loadkey):
        AvailableDepositAddress.objects.create(
            currency=Currencies.ton, address='EQDomrTUCdh_yzZT8R2Pw5A7LIlXWRWIwKyJxV2boi9cFegy'
        )
        user1_ton_wallet = Wallet.get_user_wallet(user=self.user, currency=Currencies.ton)
        user1_ton_wallet.balance = Decimal('1000000')
        user1_ton_wallet.save()

        ton_withdraw = create_withdraw_request(
            user=self.user,
            currency=Currencies.ton,
            address='EQDomrTUCdh_yzZT8R2Pw5A7LIlXWRWIwKyJxV2boi9cFegy',
            amount=Decimal('1000'),
            network='TON',
            status=WithdrawRequest.STATUS.new,
        )
        ton_withdraw.do_verify()
        WithdrawProcessor[Currencies.ton].process_withdraws([ton_withdraw], WithdrawRequest.STATUS.verified)
        ton_withdraw.refresh_from_db()
        assert ton_withdraw.status == WithdrawRequest.STATUS.accepted
        assert ton_withdraw.auto_withdraw.status == AutomaticWithdraw.STATUS.accepted

        WithdrawProcessor[Currencies.ton].process_withdraws([ton_withdraw], WithdrawRequest.STATUS.accepted)
        ton_withdraw.refresh_from_db()
        assert ton_withdraw.status == WithdrawRequest.STATUS.processing
        assert ton_withdraw.auto_withdraw.status == AutomaticWithdraw.STATUS.failed

        ton_withdraw.auto_withdraw.created_at = now() - datetime.timedelta(minutes=40)
        WithdrawProcessor[Currencies.ton].process_withdraws([ton_withdraw], WithdrawRequest.STATUS.processing)
        ton_withdraw.refresh_from_db()
        assert ton_withdraw.status == WithdrawRequest.STATUS.processing
        assert ton_withdraw.auto_withdraw.status == AutomaticWithdraw.STATUS.failed
        mocked_method.assert_not_called()

    @patch('exchange.base.connections.load_key', return_value=('user', '1234'))
    @patch('exchange.wallet.withdraw_method.RippleClient.request', return_value=withdraw_method_success_response)
    def test_tagcoins_ripple_external_withdraw(self, mocked_method, mocked_loadkey):
        user1_xrp_wallet = Wallet.get_user_wallet(user=self.user, currency=Currencies.xrp)
        user1_xrp_wallet.balance = Decimal('1000000')
        user1_xrp_wallet.save()

        xrp_withdraw = create_withdraw_request(
            user=self.user,
            currency=Currencies.xrp,
            address='EQDomrTUCdh_yzZT8R2Pw5A7LIlXWRWIwKyJxV2boi9cFegU',
            amount=Decimal('1000'),
            network='XRP',
            status=WithdrawRequest.STATUS.new,
            tag=394552874,
        )
        xrp_withdraw.do_verify()
        WithdrawProcessor[Currencies.xrp].process_withdraws([xrp_withdraw], WithdrawRequest.STATUS.verified)
        xrp_withdraw.refresh_from_db()
        assert xrp_withdraw.status == WithdrawRequest.STATUS.accepted
        assert xrp_withdraw.auto_withdraw.status == AutomaticWithdraw.STATUS.accepted

        xrp_withdraw.auto_withdraw.created_at = now() - datetime.timedelta(minutes=40)
        WithdrawProcessor[Currencies.xrp].process_withdraws([xrp_withdraw], WithdrawRequest.STATUS.accepted)
        xrp_withdraw.refresh_from_db()
        assert xrp_withdraw.status == WithdrawRequest.STATUS.sent
        assert xrp_withdraw.auto_withdraw.status == AutomaticWithdraw.STATUS.done

    @patch('exchange.base.connections.load_key', return_value=('user', '1234'))
    @patch('exchange.wallet.withdraw_method.SonicHDClient.request', return_value=withdraw_method_success_response)
    def test_sonic_external_withdraw(self, mocked_method, mocked_loadkey):
        user1_s_wallet = Wallet.get_user_wallet(user=self.user, currency=Currencies.s)
        user1_s_wallet.balance = Decimal('2000')
        user1_s_wallet.save()

        s_withdraw = create_withdraw_request(
            user=self.user,
            currency=Currencies.s,
            address='0x32631223a3B8f7bB28DC3c067d5F880902730dFa',
            amount=Decimal('500'),
            network='SONIC',
            status=WithdrawRequest.STATUS.new,
        )
        s_withdraw.do_verify()
        WithdrawProcessor[Currencies.s].process_withdraws([s_withdraw], WithdrawRequest.STATUS.verified)
        s_withdraw.refresh_from_db()
        assert s_withdraw.status == WithdrawRequest.STATUS.accepted
        assert s_withdraw.auto_withdraw.status == AutomaticWithdraw.STATUS.accepted

        s_withdraw.auto_withdraw.created_at = now() - datetime.timedelta(minutes=40)
        WithdrawProcessor[Currencies.s].process_withdraws([s_withdraw], WithdrawRequest.STATUS.accepted)
        s_withdraw.refresh_from_db()
        assert s_withdraw.status == WithdrawRequest.STATUS.sent
        assert s_withdraw.auto_withdraw.status == AutomaticWithdraw.STATUS.done

    def test_dynamic_maximum_withdraw(self):
        usdt_currency = Currencies.usdt
        usdt_currency_name = get_currency_codename(usdt_currency)
        usdt_default_network = CURRENCY_INFO[usdt_currency]['default_network']
        default_max_withdraw_amount = AutomaticWithdrawMethod.get_withdraw_max(usdt_currency)
        self.assertEqual(
            Decimal(CURRENCY_INFO[usdt_currency]['network_list'][usdt_default_network]['withdraw_max']),
            default_max_withdraw_amount,
        )

        new_expected_max_withdraw_amount = 1000
        max_withdraw_key = f'withdraw_max_{usdt_currency_name}_{usdt_default_network.lower()}'
        Settings.set(max_withdraw_key, new_expected_max_withdraw_amount)
        new_max_withdraw_amount = AutomaticWithdrawMethod.get_withdraw_max(usdt_currency)
        self.assertEqual(Decimal(new_expected_max_withdraw_amount), new_max_withdraw_amount)

    def test_dynamic_minimum_withdraw(self):
        usdt_currency = Currencies.usdt
        usdt_currency_name = get_currency_codename(usdt_currency)
        usdt_default_network = CURRENCY_INFO[usdt_currency]['default_network']
        default_min_withdraw_amount = AutomaticWithdrawMethod.get_withdraw_min(usdt_currency)
        self.assertEqual(
            Decimal(CURRENCY_INFO[usdt_currency]['network_list'][usdt_default_network]['withdraw_min']),
            default_min_withdraw_amount,
        )

        new_expected_min_withdraw_amount = 500
        min_withdraw_key = f'withdraw_min_{usdt_currency_name}_{usdt_default_network.lower()}'
        Settings.set(min_withdraw_key, new_expected_min_withdraw_amount)
        new_min_withdraw_amount = AutomaticWithdrawMethod.get_withdraw_min(usdt_currency)
        self.assertEqual(Decimal(new_expected_min_withdraw_amount), new_min_withdraw_amount)

    def test_dynamic_minimum_withdraw_pseudo_network(self):
        eth_currency = Currencies.eth
        eth_currency_name = get_currency_codename(eth_currency)
        wrapped_eth_contract_address = "0x82af49447d8a07e3bd95bd0d56f35241523fbab1"
        arb_network = 'ARB'
        default_min_withdraw_amount_for_pseudo_network = AutomaticWithdrawMethod.get_withdraw_min(
            eth_currency, network=arb_network, contract_address=wrapped_eth_contract_address
        )
        self.assertEqual(
            Decimal(
                CURRENCY_INFO[eth_currency]['network_list'][arb_network]['contract_addresses'][
                    wrapped_eth_contract_address
                ]['withdraw_min']
            ),
            default_min_withdraw_amount_for_pseudo_network,
        )

        new_expected_min_withdraw_amount = 1
        min_withdraw_key = f'withdraw_min_{eth_currency_name}_{arb_network.lower()}_{wrapped_eth_contract_address}'
        Settings.set(min_withdraw_key, new_expected_min_withdraw_amount)
        new_min_withdraw_amount = AutomaticWithdrawMethod.get_withdraw_min(
            eth_currency, network=arb_network, contract_address=wrapped_eth_contract_address
        )
        self.assertEqual(Decimal(new_expected_min_withdraw_amount), new_min_withdraw_amount)

    def test_get_rial_value_summation_for_rial_and_coin(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        request = WithdrawRequest.objects.create(
            wallet=wallet,
            status=WithdrawRequest.STATUS.waiting,
            target_account=self.system_rial_account,
            amount=Decimal('100_000_0'),
        )
        request.rial_value = None
        request.save(update_fields=['rial_value'])

        dt_day = ir_now() - datetime.timedelta(days=1)
        WithdrawRequest.get_rial_value_summation_for_rial_and_coin(self.user, dt_day)


class WithdrawsApiTest(APITestCase):
    user: User

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        Wallet.create_user_wallets(cls.user)
        cls.user.user_type = User.USER_TYPES.level1
        cls.user.mobile = '0936*****63'
        cls.user.save(update_fields=('user_type', 'mobile'))
        cls.vp = cls.user.get_verification_profile()
        cls.vp.mobile_confirmed = True
        cls.vp.mobile_identity_confirmed = True
        cls.vp.save(update_fields=('mobile_confirmed', 'mobile_identity_confirmed'))
        cls.bank_account = BankAccount.objects.create(
            user=cls.user,
            account_number='0123456',
            shaba_number='IR830170000000010810111001',
            owner_name=cls.user.get_full_name(),
            bank_name='ملی',
            bank_id=BankAccount.BANK_ID.melli,
            confirmed=True,
        )

    def setUp(self):
        cache.clear()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        self.bitcoin_wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        LoginAttempt.objects.create(user=self.user, ip='31.56.129.161', is_successful=False)

    def _test_successful_withdraws_list(self, filters=None, results=None, has_next=False):
        data = self.client.get('/users/wallets/withdraws/list', filters).json()
        assert data
        assert data['status'] == 'ok'
        assert len(data['withdraws']) == len(results)
        assert {item['id'] for item in data['withdraws']} == {w.id for w in results}
        assert data['hasNext'] == has_next

    def _test_unsuccessful_withdraws_list(self, wallet, status_code):
        response = self.client.get('/users/wallets/withdraws/list', {'wallet': wallet.id})
        assert response.status_code == status_code

    def test_withdraws_list_no_withdraws(self):
        self._test_successful_withdraws_list(results=[])

    def test_withdraws_list_all_withdraws(self):
        withdraws = [
            create_withdraw_request(self.user, Currencies.btc, '0.01'),
            create_withdraw_request(self.user, Currencies.rls, '10000000'),
            create_withdraw_request(self.user, Currencies.rls, '16000000'),
            create_withdraw_request(self.user, Currencies.usdt, '140'),
        ]
        self._test_successful_withdraws_list(results=withdraws)

    def test_withdraws_list_wallet_withdraws(self):
        withdraws = [
            create_withdraw_request(self.user, Currencies.btc, '0.03'),
            create_withdraw_request(self.user, Currencies.btc, '0.01'),
            create_withdraw_request(self.user, Currencies.rls, '10000000'),
        ]
        self._test_successful_withdraws_list({'wallet': withdraws[0].wallet_id}, results=withdraws[:2])

    def test_withdraws_list_statuses(self):
        withdraws = [
            create_withdraw_request(self.user, Currencies.btc, '0.01', status=WithdrawRequest.STATUS.done),
            create_withdraw_request(self.user, Currencies.btc, '0.02', status=WithdrawRequest.STATUS.new),
            create_withdraw_request(self.user, Currencies.rls, '10000000', status=WithdrawRequest.STATUS.rejected),
            create_withdraw_request(self.user, Currencies.rls, '16000000', status=WithdrawRequest.STATUS.accepted),
            create_withdraw_request(self.user, Currencies.usdt, '140', status=WithdrawRequest.STATUS.verified),
        ]
        self._test_successful_withdraws_list(results=withdraws[:1] + withdraws[2:])
        self._test_successful_withdraws_list({'wallet': withdraws[0].wallet_id}, results=[withdraws[0]])

    def test_withdraws_list_date_filter(self):
        withdraws = [
            create_withdraw_request(self.user, Currencies.btc, '0.01', created_at='2022-04-03 17:10:00.000+03:30'),
            create_withdraw_request(self.user, Currencies.usdt, '140', created_at='2022-04-09 21:45:00.000+03:30'),
            create_withdraw_request(self.user, Currencies.btc, '0.02', created_at='2022-04-11 08:19:00.000+03:30'),
        ]
        wallet = withdraws[0].wallet_id
        self._test_successful_withdraws_list({'from': '2022-04-01', 'to': '2022-04-10'}, results=withdraws[:2])
        self._test_successful_withdraws_list({'from': '2022-04-05', 'to': '2022-04-15'}, results=withdraws[1:])
        self._test_successful_withdraws_list(
            {'wallet': wallet, 'from': '2022-04-01', 'to': '2022-04-10'}, results=[withdraws[0]]
        )
        self._test_successful_withdraws_list(
            {'wallet': wallet, 'from': '2022-04-01', 'to': '2022-04-15'}, results=[withdraws[0], withdraws[2]]
        )
        self._test_successful_withdraws_list({'wallet': wallet, 'from': '2022-04-11'}, results=[withdraws[2]])
        self._test_successful_withdraws_list({'to': '2022-04-11'}, results=withdraws[:2])

    def test_withdraws_list_pagination(self):
        usdt_withdraws = [create_withdraw_request(self.user, Currencies.usdt, 100) for _ in range(23)]
        btc_withdraws = [create_withdraw_request(self.user, Currencies.btc, '0.01') for _ in range(5)]
        wallet = usdt_withdraws[0].wallet_id
        self._test_successful_withdraws_list({'wallet': wallet}, results=usdt_withdraws[3:], has_next=True)
        self._test_successful_withdraws_list({'wallet': wallet, 'page': 2}, results=usdt_withdraws[:3], has_next=False)
        self._test_successful_withdraws_list({'wallet': wallet, 'pageSize': 30}, results=usdt_withdraws, has_next=False)
        self._test_successful_withdraws_list({'pageSize': 5}, results=btc_withdraws, has_next=True)
        self._test_successful_withdraws_list({'pageSize': 5, 'page': 2}, results=usdt_withdraws[18:], has_next=True)
        self._test_successful_withdraws_list({'pageSize': 5, 'page': 6}, results=usdt_withdraws[:3], has_next=False)
        self._test_successful_withdraws_list(
            {'wallet': wallet, 'pageSize': 10, 'page': 3}, results=usdt_withdraws[:3], has_next=False
        )

    def test_withdraws_list_wrong_wallet(self):
        margin_wallet = Wallet.get_user_wallet(self.user, Currencies.rls, Wallet.WALLET_TYPE.margin)
        self._test_unsuccessful_withdraws_list(margin_wallet, status.HTTP_404_NOT_FOUND)

        other_user = User.objects.get(pk=202)
        other_user_wallet = Wallet.get_user_wallet(other_user, Currencies.rls)
        self._test_unsuccessful_withdraws_list(other_user_wallet, status.HTTP_404_NOT_FOUND)

    def test_confirm_crypto_withdraw_request_successfully(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt)
        wallet.balance = 1000
        wallet.save()
        response = self.client.post(
            '/users/wallets/withdraw',
            {
                'wallet': wallet.id,
                'amount': 100,
                'network': 'ETH',
                'address': '0xec1d2C8Eab4F31440aB2749D51B07feac1537d04',
            },
            HTTP_USER_AGENT='Android/5.7.2',
        )
        check_response(response, 200, 'ok')
        withdraw_id = response.json()['withdraw']['id']
        withdraw_request = WithdrawRequest.objects.get(pk=withdraw_id)
        assert withdraw_request.wallet == wallet
        assert withdraw_request.amount == Decimal('100')
        assert withdraw_request.target_address == '0xec1d2C8Eab4F31440aB2749D51B07feac1537d04'
        assert withdraw_request.fee

    def test_confirm_withdraw_request_successfully(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        wallet.balance = 550_000_000_0
        wallet.save()
        wallet.create_transaction(tp='manual', amount='1140000').commit()
        response = self.client.post(
            '/users/wallets/withdraw',
            {
                'wallet': wallet.id,
                'amount': 50_000_000_0,
                'address': self.bank_account.id,
            },
            HTTP_USER_AGENT='Android/5.7.2',
        )
        check_response(response, 200, 'ok')
        withdraw_id = response.json()['withdraw']['id']
        withdraw_request = WithdrawRequest.objects.get(pk=withdraw_id)

        # confirm with otp and ok
        response = self.client.post(
            '/users/wallets/withdraw-confirm',
            data={'withdraw': withdraw_request.id, 'otp': withdraw_request.otp},
            HTTP_USER_AGENT='Android/5.7.2',
        )
        withdraw_request.refresh_from_db()
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['status'] == 'ok'
        assert WithdrawRequest.objects.filter(
            wallet=Wallet.get_user_wallet(self.user, Currencies.rls),
            amount=Decimal(50_000_000_0),
            network='FIAT_MONEY',
            tag=None,
            fee=Decimal('40000'),
            invoice=None,
            contract_address=None,
        ).exists()

    def test_restriction_in_confirm_withdraw_request(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt)
        wallet.create_transaction(tp='manual', amount='1140.36').commit()
        response = self.client.post(
            '/users/wallets/withdraw',
            {
                'wallet': wallet.id,
                'amount': 300,
                'address': '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce',
                'network': 'BSC',
            },
            HTTP_USER_AGENT='Android/5.7.2',
        )
        check_response(response, 200, 'ok')
        withdraw_id = response.json()['withdraw']['id']
        withdraw_request = WithdrawRequest.objects.get(pk=withdraw_id)

        UserRestriction.add_restriction(self.user, UserRestriction.RESTRICTION.WithdrawRequest)

        # confirm with otp and ok
        response = self.client.post(
            '/users/wallets/withdraw-confirm',
            data={'withdraw': withdraw_request.id, 'otp': withdraw_request.otp},
            HTTP_USER_AGENT='Android/5.7.2',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {'code': 'WithdrawUnavailable', 'message': 'WithdrawUnavailable', 'status': 'failed'}
        withdraw_request.refresh_from_db()
        assert withdraw_request.status == WithdrawRequest.STATUS.new

    def test_restriction_with_used_permit_in_confirm_withdraw_request(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        UserRestriction.add_restriction(self.user, UserRestriction.RESTRICTION.WithdrawRequestRial)
        WithdrawRequestPermit.objects.create(
            user=self.user,
            amount_limit=Decimal('1000000'),
            currency=Currencies.rls,
            effective_time=ir_now() + datetime.timedelta(days=1),
        )
        wallet.create_transaction(tp='manual', amount='1140000').commit()
        response = self.client.post(
            '/users/wallets/withdraw',
            {
                'wallet': wallet.id,
                'amount': 150000,
                'address': self.bank_account.id,
            },
            HTTP_USER_AGENT='Android/5.7.2',
        )
        check_response(response, 200, 'ok')
        withdraw_id = response.json()['withdraw']['id']
        withdraw_request = WithdrawRequest.objects.get(pk=withdraw_id)

        # confirm with otp and ok
        response = self.client.post(
            '/users/wallets/withdraw-confirm',
            data={'withdraw': withdraw_request.id, 'otp': withdraw_request.otp},
            HTTP_USER_AGENT='Android/5.7.2',
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['status'] == 'ok'

    def test_restriction_with_new_permit_in_confirm_withdraw_request(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt)
        withdraw_permit = WithdrawRequestPermit.objects.create(
            user=self.user,
            amount_limit=Decimal('100000000'),
            currency=Currencies.usdt,
            effective_time=ir_now() + datetime.timedelta(days=1),
        )
        wallet.create_transaction(tp='manual', amount='1140.36').commit()
        response = self.client.post(
            '/users/wallets/withdraw',
            {
                'wallet': wallet.id,
                'amount': 300,
                'address': '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce',
                'network': 'BSC',
            },
            HTTP_USER_AGENT='Android/5.7.2',
        )
        check_response(response, 200, 'ok')
        withdraw_id = response.json()['withdraw']['id']
        withdraw_request = WithdrawRequest.objects.get(pk=withdraw_id)
        UserRestriction.add_restriction(self.user, UserRestriction.RESTRICTION.WithdrawRequestCoin)

        # confirm with otp and ok
        response = self.client.post(
            '/users/wallets/withdraw-confirm',
            data={'withdraw': withdraw_request.id, 'otp': withdraw_request.otp},
            HTTP_USER_AGENT='Android/5.7.2',
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['status'] == 'ok'
        withdraw_permit.refresh_from_db()
        assert withdraw_permit.is_active == False
        assert withdraw_permit.withdraw_request == withdraw_request

    @staticmethod
    def _test_successful_withdraw_add_response(response, amount, address, currency, network, tag=None, invoice=None):
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data
        assert data['status'] == 'ok'
        assert data['withdraw']['id']
        assert data['withdraw']['createdAt']
        assert data['withdraw']['status'] == 'New'
        assert Decimal(data['withdraw']['amount']) == amount
        assert data['withdraw']['address'] == address
        assert data['withdraw']['currency'] == currency
        assert data['withdraw']['network'] == network
        assert data['withdraw']['tag'] == tag
        assert data['withdraw']['invoice'] == invoice
        assert data['withdraw']['is_cancelable']
        assert not data['withdraw']['blockchain_url']

    @staticmethod
    def _test_successful_withdraw_add_response_short(response):
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data
        assert data['status'] == 'ok'
        assert data['withdraw']['id']

    @staticmethod
    def _test_unsuccessful_withdraw_add_response(response, code, status_code=None):
        assert response.status_code == status_code or status.HTTP_200_OK
        data = response.json()
        assert data
        assert data['status'] == 'failed'
        assert data['code'] == code

    def test_withdraw_add_for_wrong_wallet(self):
        other_user = User.objects.get(pk=202)
        wallet_ids = (
            0,
            Wallet.get_user_wallet(self.user, Currencies.rls, tp=Wallet.WALLET_TYPE.margin).id,
            Wallet.get_user_wallet(other_user, Currencies.rls).id,
        )
        for wallet_id in wallet_ids:
            response = self.client.post('/users/wallets/withdraw', {
                'wallet': wallet_id,
            })
            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_withdraw_add_invalid_amount(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': '2,000,000',
        })
        self._test_unsuccessful_withdraw_add_response(response, 'ParseError', status.HTTP_400_BAD_REQUEST)

    def test_withdraw_add_invalid_no_tag(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt)
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': '12.35',
            'noTag': '0',
        })
        self._test_unsuccessful_withdraw_add_response(response, 'ParseError', status.HTTP_400_BAD_REQUEST)

    def test_withdraw_add_empty_address(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt)
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': '12.35',
        })
        self._test_unsuccessful_withdraw_add_response(response, 'MissingTargetAddress')
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': '12.35',
            'address': '    ',
        })
        self._test_unsuccessful_withdraw_add_response(response, 'MissingTargetAddress')

    def test_withdraw_add_insufficient_balance(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': 2_000_000_0,
            'address': self.bank_account.id,
        })
        self._test_unsuccessful_withdraw_add_response(response, 'InsufficientBalance')

    def test_withdraw_add_for_level0_user(self):
        self.user.user_type = User.USER_TYPES.level0
        self.user.save(update_fields=('user_type',))
        wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': 100_000_0,
            'address': self.bank_account.id,
        })
        self._test_unsuccessful_withdraw_add_response(response, 'WithdrawAmountLimitation')

    @patch('exchange.accounts.userlevels.UserLevelManager.is_eligible_to_withdraw')
    def test_withdraw_add_with_no_verified_mobile(self, is_eligible_to_withdraw):
        self.user.verification_profile.delete()
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        wallet.create_transaction(tp='manual', amount='0.02').commit()
        is_eligible_to_withdraw.return_value = True
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': '0.002',
            'address': '1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2',
        })
        self._test_unsuccessful_withdraw_add_response(response, 'InvalidMobileNumber')

    def test_rial_withdraw_add(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        wallet.create_transaction(tp='manual', amount=200_000_0).commit()
        amount = 100_000_0
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': amount,
            'address': self.bank_account.id,
        })
        self._test_successful_withdraw_add_response(
            response,
            amount=amount,
            address=self.bank_account.display_name,
            currency='rls',
            network='FIAT_MONEY'
        )

    def test_rial_withdraw_add_to_wrong_bank_account(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': 50_000_0,
            'address': 'LRf3vuTMy4UwD5b72G84hmkfGBQYJeTwUs',
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': 50_000_0,
            'address': '0',
        })
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_rial_withdraw_add_to_unconfirmed_bank_account(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        self.bank_account.confirmed = False
        self.bank_account.save(update_fields=('confirmed',))
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': 50_000_0,
            'address': self.bank_account.id,
        })
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_rial_withdraw_add_to_deleted_bank_account(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        self.bank_account.is_deleted = True
        self.bank_account.save(update_fields=('is_deleted',))
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': 50_000_0,
            'address': self.bank_account.id,
        })
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_coin_withdraw_add_without_network(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt)
        wallet.create_transaction(tp='manual', amount='150.45').commit()
        amount = Decimal('115.6')
        address = '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce'
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': amount,
            'address': address,
        })
        self._test_successful_withdraw_add_response(
            response,
            amount=amount,
            address=address,
            currency='usdt',
            network='ETH',
        )

    def test_coin_withdraw_add_with_network(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt)
        wallet.create_transaction(tp='manual', amount='1140.36').commit()
        amount = 300
        address = '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce'
        network = 'BSC'
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': amount,
            'address': address,
            'network': network,
        })
        self._test_successful_withdraw_add_response(
            response,
            amount=amount,
            address=address,
            currency='usdt',
            network=network,
        )

    def test_coin_withdraw_add_wrong_address(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.xlm)
        wallet.create_transaction(tp='manual', amount='150.45').commit()
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': 100,
            'address': '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce',
        })
        self._test_unsuccessful_withdraw_add_response(response, 'InvalidTargetAddress')

    def test_coin_withdraw_add_in_tag_required_network_with_tag(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.bnb)
        wallet.create_transaction(tp='manual', amount='48.25').commit()
        amount = Decimal('23.43')
        address = 'bnb1jzdy3vy3h0ux0j7qqcutfnsjm2xnsa5mru7gtj'
        tag = '904325'
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': amount,
            'address': address,
            'tag': tag,
        })
        self._test_successful_withdraw_add_response(
            response,
            amount=amount,
            address=address,
            currency='bnb',
            network='BNB',
            tag=tag,
        )

    def test_coin_withdraw_add_in_tag_required_network_without_tag(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.bnb)
        wallet.create_transaction(tp='manual', amount='47').commit()
        amount = Decimal('3.4')
        address = 'bnb1jzdy3vy3h0ux0j7qqcutfnsjm2xnsa5mru7gtj'
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': amount,
            'address': address,
            'noTag': True,
        })
        self._test_successful_withdraw_add_response(
            response,
            amount=amount,
            address=address,
            currency='bnb',
            network='BNB',
            tag=None,
        )

    def test_coin_withdraw_add_with_conflicting_tag_and_no_tag_params(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.bnb)
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': '3.4',
            'address': 'bnb1jzdy3vy3h0ux0j7qqcutfnsjm2xnsa5mru7gtj',
            'tag': 'test1234',
            'noTag': True,
        })
        self._test_unsuccessful_withdraw_add_response(response, 'RedundantTag')

    @patch('exchange.accounts.userlevels.UserLevelManager.is_eligible_to_withdraw')
    def test_coin_withdraw_add_via_invoice(self, is_eligible_to_withdraw):
        pytest.importorskip('secp256k1')
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        wallet.create_transaction(tp='manual', amount='0.00307').commit()
        invoice = (
            'lntb200u1p308869pqyzg6qhp5fd4ndlhyly47gvfjtupk4t6z9wd8s78gt80j2suc0jcrgltgkgds0kncvsf2md0awe9l'
            'zpafsp2gcc8cffgd0x6nt70azz6qum3e7t68kptnu7zzq2ttfpud67syncdrrzyjjwqu2jkdrcesq4slrzhp9jgqkp4grs'
        )
        is_eligible_to_withdraw.return_value = True
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'invoice': invoice,
        })
        self._test_successful_withdraw_add_response(
            response,
            amount=Decimal('0.0002005'),  # includes fee
            address='03e7156ae33b0a208d0744199163177e909e80176e55d97a2f221ede0f934dd9ad',
            currency='btc',
            network='BTCLN',
            invoice=invoice,
        )

    def test_coin_withdraw_add_invalid_invoice(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'invoice': 'lntb200u1p308869',
        })
        self._test_unsuccessful_withdraw_add_response(response, 'InvalidInvoice')

    @override_settings(IS_PROD=True)
    def test_coin_withdraw_add_testnet_invoice_in_prod(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        invoice = (
            'lntb200u1p308869pqyzg6qhp5fd4ndlhyly47gvfjtupk4t6z9wd8s78gt80j2suc0jcrgltgkgds0kncvsf2md0awe9l'
            'zpafsp2gcc8cffgd0x6nt70azz6qum3e7t68kptnu7zzq2ttfpud67syncdrrzyjjwqu2jkdrcesq4slrzhp9jgqkp4grs'
        )
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'invoice': invoice,
        })
        self._test_unsuccessful_withdraw_add_response(response, 'InvalidInvoice')

    def test_coin_withdraw_add_empty_amount_invoice(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        invoice = (
            'lntb1p308869pqyzg6qhp5ey0wpunenhu3tm7vz9a6qc7etcxt7r273ehv55mnxvamnvrvtufsx2apmrt26a7ujcafzx'
            'r5c6v8u7vgr4dly7ee2zg6uvmze4pvv39qt4vrupsd5y324nduse8lrsfvgj0q7hl9qjmpxj0f3g3pcvw3augq6304a4'
        )
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'invoice': invoice,
        })
        self._test_unsuccessful_withdraw_add_response(response, 'InvalidInvoice')

    def test_coin_withdraw_on_lightning_network_without_invoice(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': '0.002',
            'address': '03e7156ae33b0a208d0744199163177e909e80176e55d97a2f221ede0f934dd9ad',
            'network': 'BTCLN',
        })
        self._test_unsuccessful_withdraw_add_response(response, 'InvalidInvoice')

    def _test_withdraw_add_with_restriction(self, coin_success=False, rial_success=False):
        for currency, amount, address, success in (
            (Currencies.usdt, 500, '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce', coin_success),
            (Currencies.rls, 100_000_0, self.bank_account.id, rial_success),
        ):
            wallet = Wallet.get_user_wallet(self.user, currency)
            wallet.create_transaction(tp='manual', amount=amount).commit()
            response = self.client.post('/users/wallets/withdraw', {
                'wallet': wallet.id,
                'amount': amount,
                'address': address,
            })
            if success:
                self._test_successful_withdraw_add_response_short(response)
            else:
                self._test_unsuccessful_withdraw_add_response(response, 'WithdrawUnavailable')

    def test_withdraw_add_with_total_restriction(self):
        UserRestriction.add_restriction(user=self.user, restriction='WithdrawRequest')
        self._test_withdraw_add_with_restriction()

    def test_withdraw_add_with_rial_restriction(self):
        UserRestriction.add_restriction(user=self.user, restriction='WithdrawRequestRial')
        self._test_withdraw_add_with_restriction(coin_success=True)

    def test_withdraw_add_with_coin_restriction(self):
        UserRestriction.add_restriction(user=self.user, restriction='WithdrawRequestCoin')
        self._test_withdraw_add_with_restriction(rial_success=True)

    @patch('exchange.accounts.signals.Settings.get_flag', return_value=True)
    def test_coin_withdraw_restriction_with_new_device_login(self, mock_get_flag):
        rial_wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        rial_wallet.create_transaction(tp='manual', amount=2_000_000_0).commit()
        rial_withdraw_request = {
            'wallet': rial_wallet.id,
            'amount': 100_000_0,
            'address': self.bank_account.id,
        }

        usdt_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt)
        usdt_wallet.create_transaction(tp='manual', amount='1500.45').commit()
        address = '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce'
        usdt_withdraw_request = {
            'wallet': usdt_wallet.id,
            'amount': Decimal('115.6'),
            'address': address,
        }

        login_attempt = LoginAttempt.objects.create(user=self.user, is_known=True, is_successful=True)
        login_attempt.created_at = now() - timedelta(minutes=4)
        login_attempt.save(update_fields=['created_at'])

        response = self.client.post('/users/wallets/withdraw', rial_withdraw_request)
        self._test_successful_withdraw_add_response(
            response, amount=100_000_0, address=self.bank_account.display_name, currency='rls', network='FIAT_MONEY')

        response = self.client.post('/users/wallets/withdraw', usdt_withdraw_request)
        self._test_successful_withdraw_add_response(
            response, amount=Decimal('115.6'), address=address, currency='usdt', network='ETH')

        login_attempt.created_at = now() - timedelta(seconds=101)
        login_attempt.save(update_fields=['created_at'])

        response = self.client.post('/users/wallets/withdraw', rial_withdraw_request)
        self._test_successful_withdraw_add_response(
            response, amount=100_000_0, address=self.bank_account.display_name, currency='rls', network='FIAT_MONEY')

        response = self.client.post('/users/wallets/withdraw', usdt_withdraw_request)
        self._test_successful_withdraw_add_response(
            response, amount=Decimal('115.6'), address=address, currency='usdt', network='ETH')

        login_attempt.is_known = False
        login_attempt.save(update_fields=['is_known'])

        response = self.client.post('/users/wallets/withdraw', rial_withdraw_request)
        self._test_successful_withdraw_add_response(
            response, amount=100_000_0, address=self.bank_account.display_name, currency='rls', network='FIAT_MONEY')

        response = self.client.post('/users/wallets/withdraw', usdt_withdraw_request)
        self._test_successful_withdraw_add_response(
            response, amount=Decimal('115.6'), address=address, currency='usdt', network='ETH')

        login_attempt.created_at = now() - timedelta(seconds=99)
        login_attempt.save(update_fields=['created_at'])

        response = self.client.post('/users/wallets/withdraw', rial_withdraw_request)
        self._test_successful_withdraw_add_response(
            response, amount=100_000_0, address=self.bank_account.display_name, currency='rls', network='FIAT_MONEY')

        response = self.client.post('/users/wallets/withdraw', usdt_withdraw_request)
        self._test_unsuccessful_withdraw_add_response(response, 'WithdrawUnavailableNewDevice', status.HTTP_200_OK)

        user_restrictions = UserRestriction.objects.filter(
            user=self.user,
            restriction=UserRestriction.RESTRICTION.WithdrawRequestCoin,
            considerations='ایجاد محدودیت یک ساعته برداشت رمز ارز به علت لاگین با دستگاه جدید'
        )
        assert user_restrictions
        assert user_restrictions.count() == 1
        user_restriction_removal = UserRestrictionRemoval.objects.filter(
            restriction=user_restrictions.first(),
            is_active=True
        )
        assert user_restriction_removal
        assert user_restriction_removal.count() == 1

        user_sms = UserSms.objects.filter(user=self.user,
                                          tp=UserSms.TYPES.new_device_withdrawal_restriction_notif,
                                          to=self.user.mobile,
                                          text='۱ساعت',
                                          template=UserSms.TEMPLATES.new_device_withdrawal_restriction_notif)
        assert user_sms.count() == 1

    def test_withdraws_decimals_limit(self):
        """
            To make sure withdraws can be registered only with a specific number as decimals limit(for end-users)
        """
        temporary_withdraw_permissions(user=self.user, currency=Currencies.ada)
        ada_decimal_places = 6  # we know it by default
        ada_wallet = Wallet.get_user_wallet(user=self.user, currency=Currencies.ada)
        ada_wallet.balance = Decimal('10000')
        ada_wallet.save()
        ada_withdraw_data = {
            'wallet': ada_wallet.pk,
            'amount': '30.0000001',
            'address': 'addr1vxw96rx9arvgem7vhdgv3a9u8na07nynhyj7wfn3w96rtggvzfqeq',
        }
        response = self.client.post(path='/users/wallets/withdraw', data=ada_withdraw_data).json()
        assert response.get('message') == f'Coin maximum decimal places is {ada_decimal_places}'
        ada_withdraw_data = {
            'wallet': ada_wallet.pk,
            'amount': '30.000001',
            'address': 'addr1vxw96rx9arvgem7vhdgv3a9u8na07nynhyj7wfn3w96rtggvzfqeq',
        }
        response = self.client.post(path='/users/wallets/withdraw', data=ada_withdraw_data).json()
        assert response.get('message') != f'Coin maximum decimal places is {ada_decimal_places}'

    def test_rial_withdraw_add_vandar(self):
        Settings.set_dict('withdraw_id', dict(vandar_withdraw_enabled=True))
        req_vandar_withdraw = QueueItem.objects.create(
            feature=QueueItem.FEATURES.vandar_withdraw,
            user=self.user,
        )
        req_vandar_withdraw.enable_feature()

        wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        wallet.create_transaction(tp='manual', amount=2_000_000_0).commit()
        amount = 100_000_0

        bank_account = BankAccount.objects.create(
            user=self.user,
            account_number='137520183000155',
            shaba_number='137520183000155',
            owner_name=self.user.get_full_name(),
            bank_name='وندار',
            bank_id=BankAccount.BANK_ID.vandar,
            confirmed=True,
        )
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': amount,
            'address': bank_account.id,
        })
        self._test_successful_withdraw_add_response(
            response,
            amount=amount,
            address=bank_account.display_name,
            currency='rls',
            network='FIAT_MONEY'
        )

    def test_rial_withdraw_add_vandar_limit(self):
        Settings.set_dict('withdraw_id', dict(vandar_withdraw_enabled=True))
        req_vandar_withdraw = QueueItem.objects.create(
            feature=QueueItem.FEATURES.vandar_withdraw,
            user=self.user,
        )
        req_vandar_withdraw.enable_feature()

        self.user.user_type = User.USER_TYPES.trusted
        self.user.save()

        wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        wallet.create_transaction(tp='manual', amount=10_000_000_000_0).commit()

        bank_account = BankAccount.objects.create(
            user=self.user,
            account_number='137520183000155',
            shaba_number='137520183000155',
            owner_name=self.user.get_full_name(),
            bank_name='وندار',
            bank_id=BankAccount.BANK_ID.vandar,
            confirmed=True,
        )

        amount = Decimal('500_000_000_0')
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': amount,
            'address': bank_account.id,
        })
        self._test_successful_withdraw_add_response(
            response,
            amount=amount,
            address=bank_account.display_name,
            currency='rls',
            network='FIAT_MONEY'
        )

        amount = Decimal('500_000_001_0')
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': amount,
            'address': bank_account.id,
        })
        self._test_unsuccessful_withdraw_add_response(
            response,
            'AmountTooHigh',
            'msgBankAmountHigh',
        )

    def test_rial_withdraw_add_vandar_system_disabled(self):
        Settings.set_dict('withdraw_id', dict())

        wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        wallet.create_transaction(tp='manual', amount=2_000_000_0).commit()
        amount = 100_000_0

        bank_account = BankAccount.objects.create(
            user=self.user,
            account_number='137520183000155',
            shaba_number='137520183000155',
            owner_name=self.user.get_full_name(),
            bank_name='وندار',
            bank_id=BankAccount.BANK_ID.vandar,
            confirmed=True,
        )
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': amount,
            'address': bank_account.id,
        })
        self._test_unsuccessful_withdraw_add_response(
            response,
            'VandarPaymentIdDeactivated',
            'Vandar withdraw is disabled.',
        )

    def test_rial_withdraw_add_vandar_feature_disabled(self):
        Settings.set_dict('withdraw_id', dict(vandar_withdraw_enabled=True))

        wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        wallet.create_transaction(tp='manual', amount=2_000_000_0).commit()
        amount = 100_000_0

        bank_account = BankAccount.objects.create(
            user=self.user,
            account_number='137520183000155',
            shaba_number='137520183000155',
            owner_name=self.user.get_full_name(),
            bank_name='وندار',
            bank_id=BankAccount.BANK_ID.vandar,
            confirmed=True,
        )
        response = self.client.post('/users/wallets/withdraw', {
            'wallet': wallet.id,
            'amount': amount,
            'address': bank_account.id,
        })
        self._test_unsuccessful_withdraw_add_response(
            response,
            'VandarWithdrawNotEnabled',
            'Vandar withdraw is not available for this user.',
        )

    @mock.patch('exchange.wallet.views.credit_check_if_user_could_withdraw',)
    def test_vip_credit_restriction(self, check_if_user_could_withdraw_mock:  mock.MagicMock,):
        check_if_user_could_withdraw_mock.side_effect = (False, False,)
        expected_calls = []
        for currency, amount, address, in (
            (Currencies.usdt, 500, '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce',),
            (Currencies.rls, 100_000_0, self.bank_account.id,),
        ):
            wallet = Wallet.get_user_wallet(self.user, currency)
            wallet.create_transaction(tp='manual', amount=amount).commit()
            response = self.client.post('/users/wallets/withdraw', {
                'wallet': wallet.id,
                'amount': amount,
                'address': address,
            })
            self._test_unsuccessful_withdraw_add_response(response, 'WithdrawUnavailableCreditDebt')
            expected_calls.append(mock.call(self.user.id, currency, Decimal(str(amount))))
        check_if_user_could_withdraw_mock.assert_has_calls(expected_calls)

    @mock.patch('exchange.wallet.models.WithdrawRequest.recheck_request', return_value=False)
    def test_check_daily_summation_in_withdraw_by_user_level2(self, withdraw_check_mock):
        self.user.user_type = User.USER_TYPES.level2

        self.user.save()
        rial_wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        rial_wallet.create_transaction(tp='manual', amount=10_000_000_000_0).commit()

        btc_wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        btc_wallet.create_transaction(tp='manual', amount=10).commit()
        btc_withdraw = create_withdraw_request(
            user=self.user,
            currency=Currencies.btc,
            address='UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
            amount=Decimal('7'),
            network='BTC',
            status=WithdrawRequest.STATUS.verified,
        )
        btc_withdraw.rial_value = Decimal('310_000_000_0')
        btc_withdraw.save()
        WithdrawRequest.objects.create(
            wallet=rial_wallet,
            amount=Decimal('290_000_000_0'),
            status=WithdrawRequest.STATUS.verified,
            target_account=self.bank_account,
        )

        response = self.client.post(
            '/users/wallets/withdraw',
            {
                'wallet': rial_wallet.id,
                'amount': 1500000,
                'address': self.bank_account.id,
            },
        )
        assert response.json() == {
            'code': 'WithdrawAmountLimitation',
            'message': 'WithdrawAmountLimitation',
            'status': 'failed',
        }

    @mock.patch('exchange.wallet.models.WithdrawRequest.recheck_request', return_value=False)
    def test_check_monthly_summation_in_withdraw_by_user_level2(self, withdraw_check_mock):
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()
        rial_wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        rial_wallet.create_transaction(tp='manual', amount=10_000_000_000_0).commit()

        btc_wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        btc_wallet.create_transaction(tp='manual', amount=10).commit()
        btc_withdraw = create_withdraw_request(
            user=self.user,
            currency=Currencies.btc,
            address='UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2L60cT09oYG3zW',
            amount=Decimal('7'),
            network='BTC',
            status=WithdrawRequest.STATUS.verified,
            created_at=ir_now() - datetime.timedelta(days=29),
        )
        btc_withdraw.rial_value = Decimal('17_800_000_000_0')
        btc_withdraw.save()
        WithdrawRequest.objects.create(
            wallet=rial_wallet,
            amount=Decimal('200_000_000_0'),
            status=WithdrawRequest.STATUS.verified,
            target_account=self.bank_account,
            created_at=ir_now() - datetime.timedelta(days=29),
        )

        response = self.client.post(
            '/users/wallets/withdraw',
            {
                'wallet': rial_wallet.id,
                'amount': 1500000,
                'address': self.bank_account.id,
            },
        )
        assert response.json() == {
            'code': 'WithdrawAmountLimitation',
            'message': 'WithdrawAmountLimitation',
            'status': 'failed',
        }

    def test_withdrawal_with_user_tag_and_max_rial_withdrawal_amount_successful(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        wallet.create_transaction(tp='manual', amount=5_000_000_000_0).commit()
        amount = 5_000_000_000_0
        self.user.user_type = User.USER_TYPES.trusted
        self.user.save()
        Settings.set('max_rial_withdrawal', amount)
        Settings.set('max_new_withdrawal_request', 40)
        Settings.set('max_verified_withdrawal_request', '10')
        over_shaba_limit_tag = Tag.objects.create(name='برداشت بیشتر از محدودیت شبا')
        UserTag.objects.create(user=self.user, tag=over_shaba_limit_tag)
        response = self.client.post(
            '/users/wallets/withdraw',
            {
                'wallet': wallet.id,
                'amount': amount,
                'address': self.bank_account.id,
            },
        )
        self._test_successful_withdraw_add_response(
            response, amount=amount, address=self.bank_account.display_name, currency='rls', network='FIAT_MONEY'
        )

    def test_withdrawal_without_tag_exceeding_shaba_limit_failed(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        wallet.create_transaction(tp='manual', amount=5_000_000_000_0).commit()
        amount = 5_000_000_000_0
        self.user.user_type = User.USER_TYPES.trusted
        self.user.save()
        Settings.set('max_rial_withdrawal', amount)
        response = self.client.post(
            '/users/wallets/withdraw',
            {
                'wallet': wallet.id,
                'amount': amount,
                'address': self.bank_account.id,
            },
        )
        assert response.json() == {
            'code': 'ShabaWithdrawCannotProceed',
            'message': 'Shaba withdraw cannot proceed. Daily Shaba withdraw limit Exceeded.',
            'status': 'failed',
        }

    def test_withdrawal_with_tag_user_level_3_failed(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        wallet.create_transaction(tp='manual', amount=5_000_000_000_0).commit()
        amount = 5_000_000_000_0
        self.user.user_type = User.USER_TYPES.verified
        self.user.save()
        Settings.set('max_rial_withdrawal', amount)
        response = self.client.post(
            '/users/wallets/withdraw',
            {
                'wallet': wallet.id,
                'amount': amount,
                'address': self.bank_account.id,
            },
        )
        assert response.json() == {
            'code': 'WithdrawAmountLimitation',
            'message': 'WithdrawAmountLimitation',
            'status': 'failed',
        }

    def test_withdrawal_with_tag_exceeding_5b_limit_failed(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        wallet.create_transaction(tp='manual', amount=5_000_000_000_1).commit()
        amount = 5_000_000_000_1
        self.user.user_type = User.USER_TYPES.trusted
        self.user.save()
        Settings.set('max_rial_withdrawal', amount)
        response = self.client.post(
            '/users/wallets/withdraw',
            {
                'wallet': wallet.id,
                'amount': amount,
                'address': self.bank_account.id,
            },
        )
        assert response.json() == {
            'code': 'ShabaWithdrawCannotProceed',
            'message': 'Shaba withdraw cannot proceed. Daily Shaba withdraw limit Exceeded.',
            'status': 'failed',
        }

    def test_withdrawal_due_to_exceeding_new_request_limit_failed(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        wallet.create_transaction(tp='manual', amount=5_000_000_0).commit()
        amount = 5_000_000_0
        self.user.user_type = User.USER_TYPES.trusted
        self.user.save()
        Settings.set('max_new_withdrawal_request', '0')
        response = self.client.post(
            '/users/wallets/withdraw',
            {
                'wallet': wallet.id,
                'amount': amount,
                'address': self.bank_account.id,
            },
        )
        assert response.json() == {
            'status': 'failed',
            'code': 'WithdrawLimitReached',
            'message': 'msgWithdrawLimitReached',
        }

    def test_withdrawal_due_to_exceeding_verified_request_limit_failed(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        wallet.create_transaction(tp='manual', amount=5_000_000_0).commit()
        amount = 5_000_000_0
        self.user.user_type = User.USER_TYPES.trusted
        self.user.save()
        Settings.set('max_new_withdrawal_request', '40')
        Settings.set('max_verified_withdrawal_request', '0')
        response = self.client.post(
            '/users/wallets/withdraw',
            {
                'wallet': wallet.id,
                'amount': amount,
                'address': self.bank_account.id,
            },
        )
        assert response.json() == {
            'status': 'failed',
            'code': 'WithdrawLimitReached',
            'message': 'msgWithdrawLimitReached',
        }

    def test_withdraw_creation_disabled_for_pseudo_networks(self):

        # Disable WETH-ETH creation
        weth_contract_address = CurrenciesNetworkName.CURRENCIES_PSEUDO_NETWORKS.get(Currencies.eth, {}).get('WETH-ETH')
        Settings.set(f'withdraw_creation_eth_eth_{weth_contract_address}', 'no')

        # Verify level 2 user and set 2FA
        User.objects.filter(pk=self.user.pk).update(
            user_type=User.USER_TYPES.verified,
            requires_2fa=True,
        )

        # Create a TOTPDevice for the user
        device = TOTPDevice.objects.create(
            user=self.user, name='test-device', confirmed=True  # Set to True to allow OTP verification
        )

        # Get the secret key from the TOTPDevice (binary key)
        secret_key = device.bin_key

        # Generate a valid OTP token for the current time using django_otp.oath.totp
        # The totp function expects the key, time step (default 30s), and digits (default 6)
        totp_token = totp(
            key=secret_key,
            step=device.step,  # Default is 30 seconds
            digits=device.digits,  # Default is 6 digits
        )

        # Convert the token to a string with leading zeros if needed
        totp_token = f"{totp_token:06d}"  # Ensure 6-digit format

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        wallet = Wallet.get_user_wallet(self.user, Currencies.eth)
        wallet.balance = 2
        wallet.save()

        json_response = self.client.get(
            '/users/wallets/withdraw',
            {
                'wallet': wallet.id,
                'amount': 0.5,
                'address': '0x0077732907bFC6208933Cfd2a51aFB8f33cA5958',
                'network': 'WETH-ETH',
            },
            HTTP_X_TOTP=totp_token,
        ).json()
        self.assertEqual(json_response.get('status'), 'failed')
        self.assertEqual(json_response.get('code'), 'NewWithdrawSuspended')


class WithdrawAPITransactionTestCase(TransactionTestFastFlushMixin, APITransactionTestCase):
    user: User

    def setUp(self):
        cache.clear()
        super().setUp()
        self.user = User.objects.create_user(username='WithdrawAPITransactionTestCase@nobitex.ir')
        Token.objects.create(user=self.user)

        Wallet.create_user_wallets(self.user)
        self.user.user_type = User.USER_TYPES.level2
        self.user.mobile = '0936*****63'
        self.user.save(update_fields=('user_type', 'mobile'))
        vp = self.user.get_verification_profile()
        vp.mobile_confirmed = True
        vp.save(update_fields=('mobile_confirmed',))
        self.bank_account = BankAccount.objects.create(
            user=self.user,
            account_number='0123456',
            shaba_number='IR830170000000010810111001',
            owner_name=self.user.get_full_name(),
            bank_name='ملت',
            bank_id=BankAccount.BANK_ID.mellat,
            confirmed=True,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        self.bitcoin_wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        LoginAttempt.objects.create(user=self.user, ip='31.56.129.161', is_successful=False)

    def tearDown(self):
        self.user.delete()
        return super().tearDown()

    def create_new_withdraws(self, count, token=None):
        withdraw_new_list = [
            create_withdraw_request(self.user, Currencies.rls, 400_000_000_0, status=WithdrawRequest.STATUS.new)
            for _ in range(count)
        ]
        for w in withdraw_new_list:
            w.bank_account = self.bank_account
            if token:
                w.token = token
            w.save()
        return withdraw_new_list

    @mock.patch('exchange.accounts.userlevels.UserLevelManager.is_eligible_to_withdraw')
    @mock.patch('exchange.security.models.AddressBook.are_2fa_and_otp_required')
    @mock.patch('exchange.wallet.models.WithdrawRequest.recheck_request')
    def test_concurrent_withdraw_confirm_over_sheba_limit(
        self, recheck_request: mock.MagicMock, mock_2fa: mock.MagicMock, mock_is_eligible: mock.MagicMock
    ):
        recheck_request.side_effect = None
        mock_2fa.return_value = False
        mock_is_eligible.return_value = True

        user = self.user
        wallet = Wallet.get_user_wallet(user, Currencies.rls)
        wallet.balance = 500_000_000_0
        wallet.save(update_fields=('balance',))

        withdraw_list = self.create_new_withdraws(count=2)
        withdraw_confirm_list = []

        def wrapper(withdraw_id):
            _resp = self.client.post(
                '/users/wallets/withdraw-confirm',
                {
                    'withdraw': withdraw_id,
                    'address': self.bank_account.id,
                },
            )
            withdraw_confirm_list.append(_resp.json())

        threads = [Thread(target=wrapper, args=(wd.id,)) for wd in withdraw_list]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        status_codes = [(resp.get('status'), resp.get('code')) for resp in withdraw_confirm_list]

        self.assertTrue(('ok', None) in status_codes)
        self.assertTrue(('failed', 'ShabaWithdrawCannotProceed') in status_codes)

    @mock.patch('exchange.accounts.userlevels.UserLevelManager.is_eligible_to_withdraw')
    @mock.patch('exchange.security.models.AddressBook.are_2fa_and_otp_required')
    @mock.patch('exchange.wallet.models.WithdrawRequest.recheck_request')
    def test_concurrent_withdraw_direct_over_sheba_limit(
        self, recheck_request: mock.MagicMock, mock_2fa: mock.MagicMock, mock_is_eligible: mock.MagicMock
    ):
        recheck_request.side_effect = None
        mock_2fa.return_value = False
        mock_is_eligible.return_value = True

        user = self.user
        wallet = Wallet.get_user_wallet(user, Currencies.rls)
        wallet.balance = 1000_000_000_0
        wallet.save(update_fields=('balance',))

        token = uuid.uuid4()
        withdraw_list = self.create_new_withdraws(count=2, token=token)

        confirm_responses = []

        def wrapper(wd_id):
            _resp = self.client.get(f'/direct/confirm-withdraw/{wd_id}/{token}')
            confirm_responses.append(_resp)

        threads = [Thread(target=wrapper, args=(wd.id,)) for wd in withdraw_list]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        context_status_list = []
        for resp in confirm_responses:
            if isinstance(resp.context, list):
                context_status_list.append(resp.context[-1].get('status', 'success'))
            else:
                context_status_list.append(resp.context.get('status', 'success'))

        assert sorted(context_status_list) == ['shaba_limited', 'success']


class AvaxWithdraw(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)
        self.wallet = Wallet.objects.create(user=self.user, currency=Currencies.avax)
        self.wallet2 = Wallet.objects.create(user=self.user2, currency=Currencies.avax)

    def test_avax_withdraw_get_internal_target_wallet(self):
        address = '0x5b3857c22d0C65668f1A38946486F8Af6Ae3A37a'
        wallet = Wallet.get_user_wallet(self.user, Currencies.avax)
        assert self.wallet == wallet
        tr1 = wallet.create_transaction(tp='manual', amount=Decimal('1'))
        tr1.commit()
        wallet.refresh_from_db()
        assert wallet.balance == Decimal('1')
        withdraw = WithdrawRequest.objects.create(
            wallet=wallet,
            status=WithdrawRequest.STATUS.verified,
            target_address=address,
            amount=Decimal('0.5'),
            network=CurrenciesNetworkName.AVAX,
        )
        assert withdraw.get_internal_target_wallet() is None

        wallet2 = Wallet.get_user_wallet(self.user2, Currencies.avax)
        assert self.wallet2 == wallet2
        address_lower = address.lower()  # eth like addresses will store in lower format in  WalletDepositAddress model
        WalletDepositAddress.objects.create(
            wallet=wallet2,
            currency=Currencies.avax,
            address=address_lower,
        )
        internal_wallet = withdraw.get_internal_target_wallet()
        assert internal_wallet is not None
        assert internal_wallet.currency == Currencies.avax
        assert internal_wallet.address == address_lower
        # Check internal transfer process
        withdraw.status = WithdrawRequest.STATUS.accepted
        withdraw.save(update_fields=['status'])
        WithdrawProcessor[Currencies.avax].process_withdraws([withdraw], withdraw.status)
        assert withdraw.status == 5
        wallet2.refresh_from_db()
        assert wallet2.balance == Decimal('0.5')


class RialWithdrawsWithoutOTPTest(APITestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        Wallet.create_user_wallets(self.user)
        self.user.user_type = User.USER_TYPES.level1
        self.user.mobile = '0936*****63'
        self.user.save(update_fields=('user_type', 'mobile'))
        vp = self.user.get_verification_profile()
        vp.mobile_confirmed = True
        vp.save(update_fields=('mobile_confirmed',))
        self.bank_account = BankAccount.objects.create(
            user=self.user,
            account_number='0123456',
            shaba_number='IR830170000000010810111001',
            owner_name=self.user.get_full_name(),
            bank_name='ملی',
            bank_id=BankAccount.BANK_ID.melli,
            confirmed=True,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        self.bitcoin_wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        LoginAttempt.objects.create(user=self.user, ip='31.56.129.161', is_successful=False)
        self.wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        self.wallet.balance = 1_000_000_000_0
        self.wallet.save()

    def test_rial_withdraw_without_otp(self):
        lst_withdraw_otp = UserSms.objects.filter(
            user=self.user, tp=UserSms.TYPES.verify_withdraw, to=self.user.mobile, template=UserSms.TEMPLATES.withdraw
        )
        assert not lst_withdraw_otp
        Settings.set('remove_rial_otp', 'yes')
        response = self.client.post(
            '/users/wallets/withdraw',
            {
                'wallet': self.wallet.id,
                'amount': 100_000_0,
                'address': self.bank_account.id,
            },
            HTTP_USER_AGENT='Android/5.7.2',
        )
        check_response(response, 200, 'ok')
        withdraw_id = response.json()['withdraw']['id']
        withdraw_request = WithdrawRequest.objects.get(pk=withdraw_id)
        lst_withdraw_otp = UserSms.objects.filter(
            user=self.user, tp=UserSms.TYPES.verify_withdraw, to=self.user.mobile, template=UserSms.TEMPLATES.withdraw
        )
        assert not lst_withdraw_otp

        # confirm without otp
        response = self.client.post(
            '/users/wallets/withdraw-confirm',
            data={
                'withdraw': withdraw_request.id,
            },
            HTTP_USER_AGENT='Android/5.7.2',
        )
        check_response(response, 200, 'ok')

    def test_rial_withdraw_with_unsupported_agent(self):
        """
        Test with a user agent that does not support the new withdrawal process method.
        In the new method, we have removed the OTP (SMS)
        """
        lst_withdraw_otp = UserSms.objects.filter(
            user=self.user, tp=UserSms.TYPES.verify_withdraw, to=self.user.mobile, template=UserSms.TEMPLATES.withdraw
        )
        assert not lst_withdraw_otp
        response = self.client.post(
            '/users/wallets/withdraw',
            {
                'wallet': self.wallet.id,
                'amount': 100_000_0,
                'address': self.bank_account.id,
            },
            HTTP_USER_AGENT='Android/5.7.0',
        )
        check_response(response, 200, 'ok')
        withdraw_id = response.json()['withdraw']['id']
        withdraw_request = WithdrawRequest.objects.get(pk=withdraw_id)
        lst_withdraw_otp = UserSms.objects.filter(
            user=self.user, tp=UserSms.TYPES.verify_withdraw, to=self.user.mobile, template=UserSms.TEMPLATES.withdraw
        )
        assert lst_withdraw_otp

        # confirm without otp and failed
        response = self.client.post(
            '/users/wallets/withdraw-confirm',
            data={
                'withdraw': withdraw_request.id,
            },
            HTTP_USER_AGENT='Android/5.7.0',
        )
        check_response(response, 200, 'failed')

        # confirm with otp and ok
        response = self.client.post(
            '/users/wallets/withdraw-confirm',
            data={'withdraw': withdraw_request.id, 'otp': withdraw_request.otp},
            HTTP_USER_AGENT='Android/5.7.0',
        )
        check_response(response, 200, 'ok')

    def test_rial_withdraw_with_release_flag(self):
        """
        Test with a user agent that supports the new withdrawal process method but the release flag is not True yet
        In the new method, we have removed the OTP (SMS)
        """
        lst_withdraw_otp = UserSms.objects.filter(
            user=self.user, tp=UserSms.TYPES.verify_withdraw, to=self.user.mobile, template=UserSms.TEMPLATES.withdraw
        )
        assert not lst_withdraw_otp
        Settings.set('remove_rial_otp', 'no')
        response = self.client.post(
            '/users/wallets/withdraw',
            {
                'wallet': self.wallet.id,
                'amount': 100_000_0,
                'address': self.bank_account.id,
            },
            HTTP_USER_AGENT='Android/5.7.2',
        )
        check_response(response, 200, 'ok')
        withdraw_id = response.json()['withdraw']['id']
        withdraw_request = WithdrawRequest.objects.get(pk=withdraw_id)
        lst_withdraw_otp = UserSms.objects.filter(
            user=self.user, tp=UserSms.TYPES.verify_withdraw, to=self.user.mobile, template=UserSms.TEMPLATES.withdraw
        )
        assert lst_withdraw_otp

        # confirm without otp and failed
        response = self.client.post(
            '/users/wallets/withdraw-confirm',
            data={
                'withdraw': withdraw_request.id,
            },
            HTTP_USER_AGENT='Android/5.7.0',
        )
        check_response(response, 200, 'failed')

        # confirm with otp and ok
        response = self.client.post(
            '/users/wallets/withdraw-confirm',
            data={'withdraw': withdraw_request.id, 'otp': withdraw_request.otp},
            HTTP_USER_AGENT='Android/5.7.0',
        )
        check_response(response, 200, 'ok')

    def test_coin_withdraw(self):
        # Send an OTP SMS even if the user agent is of a higher version
        lst_withdraw_otp = UserSms.objects.filter(
            user=self.user, tp=UserSms.TYPES.verify_withdraw, to=self.user.mobile, template=UserSms.TEMPLATES.withdraw
        )
        assert not lst_withdraw_otp
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt)
        wallet.create_transaction(tp='manual', amount='1140.36').commit()
        amount = 300
        address = '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce'
        network = 'BSC'
        response = self.client.post(
            '/users/wallets/withdraw',
            {
                'wallet': wallet.id,
                'amount': amount,
                'address': address,
                'network': network,
            },
            HTTP_USER_AGENT='Android/5.7.2',
        )
        check_response(response, 200, 'ok')
        withdraw_id = response.json()['withdraw']['id']
        withdraw_request = WithdrawRequest.objects.get(pk=withdraw_id)
        lst_withdraw_otp = UserSms.objects.filter(
            user=self.user, tp=UserSms.TYPES.verify_withdraw, to=self.user.mobile, template=UserSms.TEMPLATES.withdraw
        )
        assert lst_withdraw_otp

        # confirm without otp and failed
        response = self.client.post(
            '/users/wallets/withdraw-confirm',
            data={
                'withdraw': withdraw_request.id,
            },
            HTTP_USER_AGENT='Android/5.7.2',
        )
        check_response(response, 200, 'failed')

        # confirm with otp and ok
        response = self.client.post(
            '/users/wallets/withdraw-confirm',
            data={'withdraw': withdraw_request.id, 'otp': withdraw_request.otp},
            HTTP_USER_AGENT='Android/5.7.2',
        )
        check_response(response, 200, 'ok')
