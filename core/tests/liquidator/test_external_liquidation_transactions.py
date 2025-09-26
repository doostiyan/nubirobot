from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.models import Currencies
from exchange.liquidator.models import Liquidation, LiquidationRequest
from exchange.liquidator.tasks import (
    task_retry_liquidation_requests_failed_wallet_transactions,
    task_submit_liquidation_requests_external_wallet_transactions,
    task_update_liquidation_request,
)
from exchange.wallet.models import Transaction, Wallet


@patch('exchange.liquidator.services.liquidation_creator.LIQUIDATOR_EXTERNAL_CURRENCIES', {Currencies.btc})
class TestExternalLiquidationTransactions(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.marketmaker_user = Liquidation.get_marketmaker_user()
        cls.pool_manager = User.objects.get(pk=410)
        cls.pool_btc_wallet = Wallet.get_user_wallet(cls.pool_manager, Currencies.btc)
        cls.pool_usdt_wallet = Wallet.get_user_wallet(cls.pool_manager, Currencies.usdt)

    def setUp(self):
        cache.clear()

        self.liquidation_requests = [
            LiquidationRequest.objects.create(
                src_wallet=self.pool_btc_wallet,
                dst_wallet=self.pool_usdt_wallet,
                side=LiquidationRequest.SIDES.sell,
                status=LiquidationRequest.STATUS.in_progress,
                amount=Decimal('1'),
            ),
            LiquidationRequest.objects.create(
                src_wallet=self.pool_btc_wallet,
                dst_wallet=self.pool_usdt_wallet,
                side=LiquidationRequest.SIDES.buy,
                status=LiquidationRequest.STATUS.in_progress,
                amount=Decimal('2'),
            ),
        ]

        self.liquidations = [
            Liquidation.objects.create(
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                side=Liquidation.SIDES.sell,
                amount=Decimal('0.5'),
                primary_price=Decimal('10'),
                status=Liquidation.STATUS.ready_to_share,
                market_type=Liquidation.MARKET_TYPES.external,
                filled_amount=Decimal('0.5'),
                filled_total_price=Decimal('5'),
            ),
            Liquidation.objects.create(
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                side=Liquidation.SIDES.sell,
                amount=Decimal('0.5'),
                primary_price=Decimal('10'),
                status=Liquidation.STATUS.ready_to_share,
                market_type=Liquidation.MARKET_TYPES.external,
                filled_amount=Decimal('0.5'),
                filled_total_price=Decimal('5'),
            ),
            Liquidation.objects.create(
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                side=Liquidation.SIDES.buy,
                amount=Decimal('1'),
                primary_price=Decimal('10'),
                status=Liquidation.STATUS.ready_to_share,
                market_type=Liquidation.MARKET_TYPES.external,
                filled_amount=Decimal('1'),
                filled_total_price=Decimal('10'),
            ),
            Liquidation.objects.create(
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                side=Liquidation.SIDES.buy,
                amount=Decimal('1'),
                primary_price=Decimal('10'),
                status=Liquidation.STATUS.ready_to_share,
                market_type=Liquidation.MARKET_TYPES.external,
                filled_amount=Decimal('1'),
                filled_total_price=Decimal('10'),
            ),
        ]
        self.liquidations[0].liquidation_requests.add(self.liquidation_requests[0])
        self.liquidations[1].liquidation_requests.add(self.liquidation_requests[0])
        self.liquidations[2].liquidation_requests.add(self.liquidation_requests[1])
        self.liquidations[3].liquidation_requests.add(self.liquidation_requests[1])

        self._charge_wallet(self.pool_btc_wallet, Decimal('3'))
        self._charge_wallet(self.pool_usdt_wallet, Decimal('100'))

    def tearDown(self) -> None:
        cache.clear()

    @staticmethod
    def _charge_wallet(wallet: Wallet, final_balance: Decimal):
        balance = wallet.balance
        wallet.create_transaction('manual', (final_balance - balance)).commit()

    def test_wallet_transactions_successfully_applied(self):
        task_update_liquidation_request()
        task_submit_liquidation_requests_external_wallet_transactions()

        for instance in self.liquidation_requests + self.liquidations:
            instance.refresh_from_db()

        transactions = Transaction.objects.filter(
            wallet__user=self.marketmaker_user,
            tp=Transaction.TYPE.external_liquidation,
        )

        assert transactions.count() == len(self.liquidations) * 2

        assert transactions.filter(wallet__currency=Currencies.btc, amount=Decimal('0.5')).count() == 2  # sell
        assert transactions.filter(wallet__currency=Currencies.btc, amount=Decimal('-1')).count() == 2  # buy
        assert transactions.filter(wallet__currency=Currencies.usdt, amount=Decimal('-5')).count() == 2  # sell
        assert transactions.filter(wallet__currency=Currencies.usdt, amount=Decimal('10')).count() == 2  # buy

        pool_transactions = Transaction.objects.filter(
            wallet__user=self.pool_manager,
            tp=Transaction.TYPE.external_liquidation,
        )

        assert pool_transactions.count() == len(self.liquidation_requests) * 2

        assert pool_transactions.filter(wallet__currency=Currencies.btc, amount=Decimal('-1')).exists()
        assert pool_transactions.filter(wallet__currency=Currencies.btc, amount=Decimal('2')).exists()
        assert pool_transactions.filter(wallet__currency=Currencies.usdt, amount=Decimal('10')).exists()
        assert pool_transactions.filter(wallet__currency=Currencies.usdt, amount=Decimal('-20')).exists()

    @patch(
        'exchange.liquidator.services.liquidation_request_processor.Notification.notify_admins', new_callable=MagicMock
    )
    def test_liquidation_request_failed_transaction_and_retry(self, mocked_notification):
        self._charge_wallet(self.pool_btc_wallet, final_balance=Decimal('0'))
        self._charge_wallet(self.pool_usdt_wallet, final_balance=Decimal('0'))

        task_update_liquidation_request()
        task_submit_liquidation_requests_external_wallet_transactions()

        assert LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.transactions_failed).count() == 2
        mocked_notification.assert_called()

        self._charge_wallet(self.pool_btc_wallet, final_balance=Decimal('3'))
        self._charge_wallet(self.pool_usdt_wallet, final_balance=Decimal('100'))
        task_retry_liquidation_requests_failed_wallet_transactions()

        assert LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.transactions_failed).count() == 0
        assert LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.done).count() == 2
