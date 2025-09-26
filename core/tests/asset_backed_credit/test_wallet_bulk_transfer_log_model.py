import unittest
from decimal import Decimal

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import InternalUser, WalletTransferLog
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.wallet.models import Wallet as ExchangeWallet


class WalletTransferLogTest(unittest.TestCase):
    def setUp(self):
        self.user = User.objects.get(id=201)
        self.internal_user = InternalUser.objects.create(uid=self.user.uid, user_type=self.user.user_type)
        self.transfer_item = {Currencies.usdt: Decimal('10'), Currencies.btc: Decimal('100')}
        self.src_wallet_type = ExchangeWallet.WALLET_TYPE.spot
        self.dst_wallet_type = ExchangeWallet.WALLET_TYPE.credit
        self.status = WalletTransferLog.STATUS.done

    def test_create_wallet_transfer_log_successfully(self):
        WalletTransferLog.create(
            user=self.user,
            internal_user=self.internal_user,
            src_wallet_type=self.src_wallet_type,
            dst_wallet_type=self.dst_wallet_type,
            transfer_items=self.transfer_item,
            status=self.status,
        )

        transfer_log = WalletTransferLog.objects.filter(
            user=self.user,
            src_wallet_type=self.src_wallet_type,
            dst_wallet_type=self.dst_wallet_type,
            status=self.status,
            response_body__isnull=True,
            response_code__isnull=True,
            api_called_at__isnull=True,
        ).first()

        assert transfer_log

    def test_update_wallet_transfer_api_data_successfully(self):
        log = WalletTransferLog.create(
            user=self.user,
            internal_user=self.internal_user,
            src_wallet_type=self.src_wallet_type,
            dst_wallet_type=self.dst_wallet_type,
            transfer_items=self.transfer_item,
            status=self.status,
        )

        log.update_api_data(
            response_body={'test': 'test'},
            response_code=200,
            external_transfer_id=10,
        )

        log.refresh_from_db()
        assert log.response_code == 200
        assert log.response_body == {'test': 'test'}
        assert log.retry == 0
        assert log.external_transfer_id == 10

    def test_update_wallet_transfer_api_data_when_api_called_is_not_none_then_updates_retry(self):
        log = WalletTransferLog.create(
            user=self.user,
            internal_user=self.internal_user,
            src_wallet_type=self.src_wallet_type,
            dst_wallet_type=self.dst_wallet_type,
            transfer_items=self.transfer_item,
            status=self.status,
            api_called_at=ir_now(),
        )

        log.update_api_data(
            response_body={},
            response_code=200,
        )

        log.refresh_from_db()
        assert log.retry == 1
        assert log.external_transfer_id is None

    def test_has_pending_transfer_when_user_has_new_logs(self):
        WalletTransferLog.create(
            user=self.user,
            internal_user=self.internal_user,
            src_wallet_type=self.src_wallet_type,
            dst_wallet_type=self.dst_wallet_type,
            transfer_items=self.transfer_item,
            status=WalletTransferLog.STATUS.new,
        )

        assert WalletTransferLog.has_pending_transfer(self.user, self.src_wallet_type) == True

    def test_has_pending_transfer_when_user_has_retry_logs(self):
        WalletTransferLog.create(
            user=self.user,
            internal_user=self.internal_user,
            src_wallet_type=self.src_wallet_type,
            dst_wallet_type=self.dst_wallet_type,
            transfer_items=self.transfer_item,
            status=WalletTransferLog.STATUS.pending_to_retry,
            api_called_at=ir_now(),
        )

        assert WalletTransferLog.has_pending_transfer(self.user, self.src_wallet_type) == True

    def test_test_has_pending_transfer_when_user_has_no_log_returns_false(self):
        WalletTransferLog.objects.filter(user=self.user).delete()
        assert WalletTransferLog.has_pending_transfer(self.user, self.src_wallet_type) == False
