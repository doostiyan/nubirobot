import datetime
import copy
from decimal import Decimal
from unittest.mock import patch

import pytz
from django.test import TestCase
from django.utils.timezone import now

from exchange.accounts.models import User, Notification
from exchange.base.models import Currencies, ADDRESS_TYPE
from exchange.blockchain.models import Transaction as BlockchainTransaction
from exchange.wallet.deposit import save_deposit_from_blockchain_transaction
from exchange.wallet.deposit_diff import DepositDiffChecker, BlockchainExplorer
from exchange.wallet.models import Wallet, WalletDepositAddress, ConfirmedWalletDeposit
from exchange.wallet.withdraw import WithdrawProcessor
from tests.base.utils import create_deposit, create_withdraw_request
from tests.wallet.utils import get_data


class DepositDiffTest(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)
        Wallet.create_user_wallets(self.user)
        Wallet.create_user_wallets(self.user2)
        self.response = get_data('deposit_diff_data/response')
        self.create_deposit_object_ltc()

    def create_deposit_object_ltc(self):
        ltc = Currencies.ltc
        ltc_address = 'LezhvSsYxyXo3MHen1khthBPBLwx9eD95Y'
        tx_hash = '68e4221dbb9dc4f19d0b969d70f9f8bdadf32186873d40bb1a340dd08bf362b4'
        tx_amount = Decimal('1.59')
        tx_date = datetime.datetime(2019, 2, 21, 6, 20, 31, 0, pytz.utc)
        wallet = Wallet.get_user_wallet(self.user, ltc)
        addr = WalletDepositAddress.objects.create(
            wallet=wallet,
            address=ltc_address,
        )
        tx = BlockchainTransaction(
            address=ltc_address,
            hash=tx_hash,
            timestamp=tx_date,
            value=tx_amount,
            confirmations=6,
            is_double_spend=False,
        )
        save_deposit_from_blockchain_transaction(tx, addr)

    def create_deposit_object_bsc(self):
        bsc = Currencies.bnb
        bsc_address = '0x8c20dc04e9af42e73b7f3b85b2061193f02e7129'
        tx_hash = '0xa05fd546cf5a56b6087b49c244eb76a1ff75fde3836f04cfaef26a11fbd5af6c'
        tx_amount = Decimal('5')
        tx_date = datetime.datetime(2022, 3, 9, 6, 2, 58, 28, pytz.utc)
        wallet = Wallet.get_user_wallet(self.user, bsc)
        addr = WalletDepositAddress.objects.create(
            wallet=wallet,
            address=bsc_address,
        )
        tx = BlockchainTransaction(
            address=bsc_address,
            hash=tx_hash,
            timestamp=tx_date,
            value=tx_amount,
            confirmations=6,
            is_double_spend=False,
        )
        save_deposit_from_blockchain_transaction(tx, addr)

    @patch.object(BlockchainExplorer, 'get_transactions_values_by_address')
    @patch.object(Notification, 'notify_admins')
    def test_deposit_diff_notifs_status_failed(self, mocked_notification, mocked_explorer):
        response = copy.deepcopy(self.response)
        response[0]['value'] = Decimal('0')
        mocked_explorer.return_value = response
        mocked_notification.return_value = 'Deposit has diff'
        DepositDiffChecker.recheck_confirmed_deposits()
        mocked_explorer.assert_called_once()
        mocked_notification.assert_called_once()

    @patch.object(BlockchainExplorer, 'get_transactions_values_by_address')
    @patch.object(Notification, 'notify_admins')
    def test_deposit_diff_notifs_mismatch_value(self, mocked_notification, mocked_explorer):
        response = copy.deepcopy(self.response)
        response[0]['value'] = Decimal('1.5')
        mocked_explorer.return_value = response
        mocked_notification.return_value = 'Deposit has diff'
        DepositDiffChecker.recheck_confirmed_deposits()
        mocked_explorer.assert_called_once()
        mocked_notification.assert_called_once()

    @patch.object(BlockchainExplorer, 'get_transactions_values_by_address')
    @patch.object(Notification, 'notify_admins')
    def test_deposit_diff_notifs_no_diff(self, mocked_notification, mocked_explorer):
        mocked_explorer.return_value = self.response
        mocked_notification.return_value = 'Deposit has diff'
        assert not ConfirmedWalletDeposit.objects.last().rechecked
        DepositDiffChecker.recheck_confirmed_deposits()
        mocked_explorer.assert_called_once()
        mocked_notification.assert_not_called()
        assert ConfirmedWalletDeposit.objects.last().rechecked

    @patch.object(BlockchainExplorer, 'get_transactions_values_by_address')
    def test_deposit_diff_notifs_status_failed_multiple_deposits(self, mocked_explorer):
        response2 = get_data('deposit_diff_data/response2')
        mocked_explorer.return_value = self.response + response2
        self.create_deposit_object_bsc()
        with patch.object(Notification, 'notify_admins', return_value='Deposit has diff') as mocked_notification:
            DepositDiffChecker.recheck_confirmed_deposits()
            mocked_explorer.assert_called()
            mocked_notification.assert_called_once()

    def test_deposit_diff_internal_deposits(self):
        currency = Currencies.btc
        address = 'bc1qnz8ppdlzgkf73r3vy842dhp5uat57ul2aachww'
        tx_hash = 'fb7517cd9159fdc73535b86c8ec8145bbed30ba6962a9360fa9c8828834f90d1'
        create_deposit(user=self.user, currency=currency, address=address, amount=Decimal('1'), tx_hash=tx_hash,
                       type=ADDRESS_TYPE.segwit)
        address_2 = '327ySURPg6JS1awGKteGMSCrq7DFsASjCH'
        tx_hash = 'ca3f27c6c1cb5f01ab976e589deda7f2c67ce3046f4b24d3dbed2d202f2804b3'
        create_deposit(
            user=self.user2, currency=Currencies.btc, address=address_2, amount=Decimal('1'), tx_hash=tx_hash,
            type=ADDRESS_TYPE.segwit
        )

        withdraw = create_withdraw_request(
            user=self.user, currency=Currencies.btc, address=address_2, amount=Decimal('0.1'),
            status=3, created_at=now(), network='BTC',
        )
        WithdrawProcessor[Currencies.btc].process_withdraws([withdraw], withdraw.status)

        with patch.object(BlockchainExplorer, 'get_transactions_values_by_address', return_value='Deposit has diff') as mocked_explorer:
            DepositDiffChecker.recheck_confirmed_deposits()
            mocked_explorer.assert_called_once()
