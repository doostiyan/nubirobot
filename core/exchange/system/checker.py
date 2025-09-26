"""Online System Checker"""
import datetime
import time
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Tuple

from django.conf import settings
from django.core.cache import cache
from django.db.models import F, Func, Min, Q, Subquery, Sum
from django.utils.timezone import now

from exchange.accounts.models import Notification
from exchange.base.constants import MAX_POSITIVE_32_INT
from exchange.base.decorators import measure_time
from exchange.base.models import RIAL
from exchange.base.money import money_is_close, money_is_zero
from exchange.market.constants import MARKET_ORDER_MAX_PRICE_DIFF
from exchange.market.models import OrderMatching
from exchange.shetab.models import ShetabDeposit
from exchange.wallet.models import (
    AutomaticWithdraw,
    BankDeposit,
    ConfirmedWalletDeposit,
    Transaction,
    Wallet,
    WithdrawRequest,
)


class BaseChecker(ABC):
    send_telegram = not settings.DEBUG
    telegram_title = 'Checker'
    telegram_channel = 'system_diff'

    @classmethod
    def is_close(cls, a, b):
        """Compare values ignoring small diffs."""
        if isinstance(a, (int, float)):
            a = Decimal(a)
        if isinstance(b, (int, float)):
            b = Decimal(b)
        return (a - b).copy_abs() < Decimal('1E-7')

    def notif(self, obj, message, details=''):
        """Send a Telegram notif and also print it."""
        notification = message + f': #{obj.id}'
        if details:
            notification += ' ' + details
        print('  ==> ' + notification)
        if self.send_telegram:
            Notification.notify_admins(
                notification,
                title=f'⭕️ [{self.telegram_title}] Check Failed',
                channel=f'{self.telegram_channel}',
            )

    def send_startup_notice(self):
        """Send start notifications."""
        if not settings.IS_PROD:
            return
        if self.send_telegram:
            Notification.notify_admins(
                f'Started on {settings.SERVER_NAME} {settings.RELEASE_VERSION}-{settings.CURRENT_COMMIT}',
                title=f'🏁 {self.telegram_title}',
                channel=f'{self.telegram_channel}',
            )

    def send_shutdown_notice(self):
        """Send shutdown notifications."""
        if not settings.IS_PROD:
            return
        if self.send_telegram:
            Notification.notify_admins(
                'Done',
                title=f'🏁 {self.telegram_title}',
                channel=f'{self.telegram_channel}',
            )

    @abstractmethod
    def load_state(self):
        raise NotImplementedError

    @abstractmethod
    def save_state(self):
        raise NotImplementedError

    @abstractmethod
    def check_all(self):
        raise NotImplementedError

    def run(self):
        """Run Checker."""
        self.send_startup_notice()
        self.load_state()
        try:
            while True:
                self.check_all()
                self.save_state()
                print('')
                time.sleep(5 if settings.IS_PROD else 120)
        except KeyboardInterrupt:
            pass
        self.save_state()
        self.send_shutdown_notice()
        print('\nDone.')


class OnlineChecker(BaseChecker):
    """Regular checks of Matching engine output"""

    def __init__(self, recheck_balances=False, recheck_balances_fast=True, do_check_wallets=True):
        self.last_checked_trade = 0
        self.last_checked_transaction = 0
        self.wallets_to_check = set()
        self.wallets_last_check = {}
        self.wallets_last_balance: Dict[int, Tuple[Decimal, int]] = {}
        # Options
        self.recheck_balances = recheck_balances
        self.recheck_balances_fast = recheck_balances_fast
        self.do_check_wallets = do_check_wallets

    def load_state(self):
        """Load important local variables from cache."""
        self.last_checked_trade = cache.get('checker_trades_last_checked_id') or 0
        self.last_checked_transaction = cache.get('checker_transactions_last_checked_id') or 0
        self.wallets_to_check = cache.get('checker_wallets_to_check') or set()

    def save_state(self):
        """Save important local variables to cache."""
        cache.set('checker_trades_last_checked_id', self.last_checked_trade, 3600)
        cache.set('checker_transactions_last_checked_id', self.last_checked_transaction, 3600)
        cache.set('checker_wallets_to_check', self.wallets_to_check, 3600)

    def enqueue_wallet(self, wallet):
        """Add a wallet to check queue."""
        if not self.do_check_wallets:
            return
        wallet_id = wallet if isinstance(wallet, int) else wallet.id
        self.wallets_to_check.add(wallet_id)

    @measure_time(metric='checker_check_recent_trades')
    def check_recent_trades(self):
        """Check recent trades to be correct."""
        print('Checking recent trades...')
        nw = now()
        recent_trades = OrderMatching.objects.filter(
            id__gt=self.last_checked_trade,
            created_at__gte=nw - datetime.timedelta(minutes=15),
            created_at__lte=nw - datetime.timedelta(minutes=1),
        ).select_related(
            'seller', 'sell_order', 'sell_deposit', 'sell_withdraw', 'sell_deposit__wallet', 'sell_withdraw__wallet',
            'buyer', 'buy_order', 'buy_deposit', 'buy_withdraw', 'buy_deposit__wallet', 'buy_withdraw__wallet',
            'market',
        ).order_by('id')[:100]
        checks = 0
        for trade in recent_trades:
            checks += 1
            self.last_checked_trade = trade.id
            # Useful variables
            total_price = (trade.matched_amount * trade.matched_price).quantize(Decimal('1e-10'))
            src, dst = trade.market.src_currency, trade.market.dst_currency
            sell, buy = trade.sell_order, trade.buy_order
            # General trade checks
            if not all([trade.sell_deposit, trade.sell_withdraw, trade.buy_deposit, trade.buy_withdraw]):
                self.notif(trade, 'Trade misses transactions')
                continue
            if money_is_zero(trade.matched_amount) or money_is_zero(trade.matched_price):
                self.notif(trade, 'Very small trade')
                continue
            # Check transaction amount
            tx_diffs = [
                trade.sell_withdraw.amount + trade.matched_amount,
                trade.sell_deposit.amount - (total_price - trade.sell_fee_amount),
                trade.buy_withdraw.amount + total_price,
                trade.buy_deposit.amount - (trade.matched_amount - trade.buy_fee_amount),
            ]
            for diff in tx_diffs:
                if not money_is_zero(abs(diff)):
                    self.notif(trade, 'Transaction values diff')
                    continue
            # Check transaction wallets with orders
            if not all(
                [
                    (trade.sell_withdraw.wallet.user_id == trade.seller_id) ^ trade.sell_order.is_margin,
                    (trade.sell_deposit.wallet.user_id == trade.seller_id) ^ trade.sell_order.is_margin,
                    (trade.buy_withdraw.wallet.user_id == trade.buyer_id) ^ trade.buy_order.is_margin,
                    (trade.buy_deposit.wallet.user_id == trade.buyer_id) ^ trade.buy_order.is_margin,
                    trade.sell_withdraw.wallet.currency == src,
                    trade.sell_deposit.wallet.currency == dst,
                    trade.buy_withdraw.wallet.currency == dst,
                    trade.buy_deposit.wallet.currency == src,
                ]
            ):
                self.notif(trade, 'Transaction wallet invalid')
                continue
            # Check order increased values
            if not all([
                sell.amount >= sell.matched_amount >= trade.matched_amount,
                sell.matched_total_price >= total_price,
                sell.fee >= trade.sell_fee_amount,
                buy.amount >= buy.matched_amount >= trade.matched_amount,
                buy.matched_total_price >= total_price,
                buy.fee >= trade.buy_fee_amount,
            ]):
                self.notif(trade, 'Order matched values diff')
                continue
            # Check matched price range
            max_buy_price = buy.price
            if buy.is_market:
                max_buy_price += max_buy_price * MARKET_ORDER_MAX_PRICE_DIFF
            if not max_buy_price:
                max_buy_price = trade.matched_price
            min_sell_price = sell.price
            if sell.is_market:
                min_sell_price -= min_sell_price * MARKET_ORDER_MAX_PRICE_DIFF
            if not min_sell_price <= trade.matched_price <= max_buy_price:
                self.notif(trade, 'Bad matched price')
                continue
            # Check fee amounts
            max_sell_fee = (total_price * Decimal('0.0035')).quantize(Decimal('1e-10'))
            max_buy_fee = (trade.matched_amount * Decimal('0.0035')).quantize(Decimal('1e-10'))
            if not all([
                0 <= trade.sell_fee_amount <= max_sell_fee,
                0 <= trade.buy_fee_amount <= max_buy_fee,
            ]):
                self.notif(trade, 'Bad match fee values')
                continue
            # Add related wallets to check queue
            self.enqueue_wallet(trade.sell_deposit.wallet_id)
            self.enqueue_wallet(trade.sell_withdraw.wallet_id)
            self.enqueue_wallet(trade.buy_deposit.wallet_id)
            self.enqueue_wallet(trade.buy_withdraw.wallet_id)
        print(f'Checked {checks} trades.')

    @measure_time(metric='checker_check_wallets')
    def check_wallets(self):
        """Check queued wallets to be correct."""
        if not self.do_check_wallets:
            return
        print(f'Checking {len(self.wallets_to_check)} wallets...')
        remaining_wallets = set()
        recently_checked_date = now() - datetime.timedelta(minutes=5)
        checks = 0
        for wallet_id in self.wallets_to_check:
            # Skips recently checked wallets
            last_check = self.wallets_last_check.get(wallet_id)
            if last_check and last_check >= recently_checked_date:
                remaining_wallets.add(wallet_id)
                continue
            # Check wallet balance
            checks += 1
            wallet = Wallet.objects.get(id=wallet_id)
            if wallet.balance < Decimal('0'):
                self.notif(wallet, f'Negative balance in {wallet.user.username} wallet')
            # Recheck balance with sum of all wallet's transactions
            if self.recheck_balances:
                large_wallet_cache_key = f'checker_wallets_is_large_{wallet_id}'
                if not cache.get(large_wallet_cache_key):
                    t0 = time.time()
                    real_balance = wallet.transactions.aggregate(s=Sum('amount'))['s'] or Decimal('0')
                    duration = time.time() - t0
                    if duration > 60:
                        print(f'Many transactions for Wallet#{wallet_id}')
                        cache.set(large_wallet_cache_key, True, 24 * 3600)
                    if not self.is_close(real_balance, wallet.balance):
                        self.notif(wallet, f'Balance mismatch: {wallet.balance} != {real_balance} in',
                            f'C{wallet.currency} {wallet.user.username}')
            elif self.recheck_balances_fast:
                if last_check:
                    last_check = last_check - datetime.timedelta(minutes=1)

                last_txs = (
                    wallet.transactions.filter(
                        created_at__gte=last_check or settings.LAST_RECENT_TRANSACTION_DATE,
                    )
                    .values('id', 'balance', 'wallet__balance')
                    .order_by('-created_at', '-id')[:5]
                )
                if len(last_txs) != 0:
                    last_tx = sorted(
                        last_txs,
                        key=lambda t: t['id'] if t['id'] > 0 else t['id'] + MAX_POSITIVE_32_INT,
                        reverse=True,
                    )[0]

                    if last_tx['balance'] and not self.is_close(last_tx['balance'], last_tx['wallet__balance']):
                        self.notif(
                            wallet,
                            f'Wallet balance mismatch last tx: '
                            f'{last_tx["wallet__balance"].normalize():f} != {last_tx["balance"].normalize():f} in',
                            f'C{wallet.currency} {wallet.user.username}',
                        )

            self.wallets_last_check[wallet_id] = now()
        self.wallets_to_check = remaining_wallets
        print(f'Checked {checks} wallets.')

    @staticmethod
    def is_negative_balance_forbidden(transaction: Transaction) -> bool:
        return transaction.amount <= 0 and transaction.ref_module not in (
            Transaction.REF_MODULES['ExchangeSystemSrc'],
            Transaction.REF_MODULES['ExchangeSystemDst'],
        )

    @measure_time(metric='checker_check_recent_transactions')
    def check_recent_transactions(self):
        """Check recent transactions to be correct."""
        print('Checking recent transactions...')
        nw = now()

        if self.last_checked_transaction >= 0:
            id_gt_q = Q(id__lte=0) | Q(id__gt=self.last_checked_transaction)
        else:
            id_gt_q = Q(id__lte=0) & Q(id__gt=self.last_checked_transaction)

        recent_transactions = Transaction.objects.filter(
            id_gt_q,
            created_at__gte=nw - datetime.timedelta(minutes=15),
            created_at__lte=nw - datetime.timedelta(minutes=1),
        ).order_by('created_at', 'id')[:200]

        # Sort by id instead of created_at because order of id and created_at are not consistent in some cases
        # So we using id as reference to logical order. Also pushing the negative ids to the end.
        recent_transactions = sorted(
            recent_transactions,
            key=lambda t: t.pk if t.pk > 0 else t.pk + MAX_POSITIVE_32_INT,
        )

        checks = 0
        for transaction in recent_transactions:
            checks += 1
            # Generic balance check and store
            self.last_checked_transaction = transaction.id
            # Check empty balance
            if transaction.balance is None:
                self.notif(transaction, 'None transaction balance')
                if transaction.wallet_id in self.wallets_last_balance:
                    del self.wallets_last_balance[transaction.wallet_id]
                continue
            last_balance, last_tx_id = self.wallets_last_balance.get(transaction.wallet_id, (None, None))
            self.wallets_last_balance[transaction.wallet_id] = transaction.balance, transaction.id
            # Check negative balance
            if transaction.balance < Decimal('0') and self.is_negative_balance_forbidden(transaction):
                message = f'Negative transaction balance\ntp: {transaction.get_tp_display()} {transaction.description}'
                self.notif(transaction, message.rstrip())
                continue
            # Check balance change from last known balance
            if last_balance is None:
                continue
            if money_is_close(transaction.balance, last_balance + transaction.amount):
                continue

            if transaction.id > 0:
                id_lt_q = Q(id__gte=0) & Q(id__lt=transaction.id)
            else:
                id_lt_q = Q(id__gt=0) | Q(id__lt=transaction.id)

            if last_tx_id > 0:
                id_gte_q = Q(id__lte=0) | Q(id__gte=last_tx_id)
            else:
                id_gte_q = Q(id__lte=0) & Q(id__gte=last_tx_id)

            # Just to make sure we get last tx by id and not by created_at
            # Get last 5 txs and use id to sort them, then pick the last
            last_transactions = (
                Transaction.objects.filter(
                    id_lt_q,
                    id_gte_q,
                    wallet_id=transaction.wallet_id,
                )
                .order_by('-created_at', '-id')
            )[:5]
            if len(last_transactions) == 0:
                self.notif(transaction, 'Deleted previous transaction', f'W#{transaction.wallet_id} TX#{last_tx_id}')
                continue

            last_transaction = sorted(
                last_transactions,
                key=lambda t: t.pk if t.pk > 0 else t.pk + MAX_POSITIVE_32_INT,
                reverse=True,
            )[0]

            if not money_is_close(transaction.balance, last_transaction.balance + transaction.amount):
                self.notif(transaction, 'Invalid transaction balance', f'W#{transaction.wallet_id} TP{transaction.tp}')

        print(f'Checked {checks} transactions.')

    def check_all(self):
        self.check_recent_trades()
        self.check_recent_transactions()
        self.check_wallets()


class DiffChecker(BaseChecker):
    telegram_title = 'Diff Checker'

    def __init__(self, recheck_diff=True, do_check_wallets=True):
        self.last_checked_withdraw = 0
        self.last_checked_transaction = 0
        self.wallets_to_check = set()
        self.wallets_last_check = {}
        self.wallets_last_balance = {}
        # Options
        self.recheck_diff = recheck_diff
        self.do_check_wallets = do_check_wallets

    def load_state(self):
        """Load important local variables from cache."""
        self.last_checked_withdraw = cache.get('diff_checker_withdraw_last_checked_id') or 0

    def save_state(self):
        """Save important local variables to cache."""
        cache.set('diff_checker_withdraw_last_checked_id', self.last_checked_withdraw, 3600)

    @classmethod
    def check_wallet_diff(cls, wallet, check_until_tx=None):
        if not check_until_tx:
            check_until_tx = (
                Transaction.objects.filter(
                    created_at__gte=settings.LAST_RECENT_TRANSACTION_DATE,
                    wallet_id=wallet.id,
                )
                .order_by('-created_at', '-id')
                .first()
            )
            if not check_until_tx:
                return Decimal('0')
        user = wallet.user
        last_tx_id_cache_key = f'diff_checker_wallets_last_transaction_{wallet.id}'
        last_cache_transaction = cache.get(last_tx_id_cache_key)
        if not last_cache_transaction or not last_cache_transaction.get('created_at'):
            last_wallet_transaction_checked = check_until_tx.created_at - datetime.timedelta(minutes=30)
            last_wallet_transaction_diff = Decimal('0')
        else:
            last_wallet_transaction_checked = last_cache_transaction['created_at']
            last_wallet_transaction_diff = last_cache_transaction['diff']

        if check_until_tx.created_at <= last_wallet_transaction_checked:
            return last_wallet_transaction_diff
        tx_gt = max(settings.LAST_RECENT_TRANSACTION_DATE, last_wallet_transaction_checked)
        deposit_crypto_sum_internal = Decimal('0')
        if wallet.currency == RIAL:
            q_is_card_valid = Q(user_card_number__isnull=False) & ~Q(user_card_number='0000-0000-0000-0000')
            q_is_requested = Q(nextpay_id__isnull=False) & ~Q(nextpay_id='0')
            q_is_status_valid_success = Q(status_code=ShetabDeposit.STATUS.pay_success)
            q_is_status_valid_failure = Q(
                status_code__in=[ShetabDeposit.STATUS.invalid_card, ShetabDeposit.STATUS.refunded]
            )
            q_is_status_valid = q_is_status_valid_success | q_is_status_valid_failure
            shetab_deposit_sum = (
                ShetabDeposit.objects.filter(q_is_card_valid, q_is_requested, q_is_status_valid)
                .filter(
                    user=user,
                    # created_at__gt=nw - datetime.timedelta(days=10),
                    transaction__created_at__gt=tx_gt,
                    transaction__created_at__lte=check_until_tx.created_at,
                )
                .aggregate(s=Sum(F('amount') - F('fee')))['s']
                or Decimal('0')
            )
            bank_deposit_sum = BankDeposit.objects.filter(
                user=user,
                # created_at__gt=nw - datetime.timedelta(days=10),
                transaction__created_at__gt=tx_gt,
                transaction__created_at__lte=check_until_tx.created_at,
                confirmed=True
            ).aggregate(s=Sum(F('amount') - F('fee')))['s'] or Decimal('0')
            c_deposit = shetab_deposit_sum + bank_deposit_sum
        else:
            # TODO: extract fee when applying fee on deposit
            crypto_sum_info = ConfirmedWalletDeposit.objects.filter(
                _wallet=wallet,
                # created_at__gt=nw - datetime.timedelta(days=10),
                transaction__created_at__gt=tx_gt,
                transaction__created_at__lte=check_until_tx.created_at,
                validated=True,
                confirmed=True
            ).aggregate(
                s_non_internal=Sum('amount', filter=~Q(tx_hash__icontains='nobitex-internal-W')),
                s_internal=Sum('amount', filter=Q(tx_hash__icontains='nobitex-internal-W')),
            )
            crypto_sum_non_internal = crypto_sum_info['s_non_internal'] or Decimal('0')
            deposit_crypto_sum_internal = crypto_sum_info['s_internal'] or Decimal('0')
            c_deposit = crypto_sum_non_internal + deposit_crypto_sum_internal

        withdraw_sum = (
            WithdrawRequest.objects.filter(
                wallet=wallet,
                # created_at__gt=nw - datetime.timedelta(days=10),
                transaction__created_at__gt=tx_gt,
                transaction__created_at__lte=check_until_tx.created_at,
            ).aggregate(s=Sum('amount'))['s']
            or Decimal('0')
        )

        internal_withdraws_to_transaction = Transaction.objects.filter(
            created_at__gt=tx_gt,
            created_at__lte=check_until_tx.created_at,
            wallet=wallet,
            ref_module=Transaction.REF_MODULES['InternalTransferDeposit'],
        )
        withdraw_internal_to_sum = WithdrawRequest.objects.filter(
            id__in=Subquery(internal_withdraws_to_transaction.values_list('ref_id', flat=True)),
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0')

        c_buys = Func(Sum('amount', filter=Q(tp=Transaction.TYPE.buy)), function='ABS')
        c_sells = Func(Sum('amount', filter=Q(tp=Transaction.TYPE.sell)), function='ABS')
        c_manual = Sum('amount', filter=Q(tp=Transaction.TYPE.manual))
        c_refund = Sum('amount', filter=Q(tp=Transaction.TYPE.refund))
        c_gateway = Sum('amount', filter=Q(tp=Transaction.TYPE.gateway))
        tx_info = Transaction.objects.filter(
            created_at__gt=tx_gt,
            created_at__lte=check_until_tx.created_at,
            wallet=wallet,
            # created_at__gt=nw - datetime.timedelta(days=10),
        ).aggregate(
            c_buys=c_buys,
            c_sells=c_sells,
            c_manual=c_manual,
            c_gateway=c_gateway,
            c_refund=c_refund,
            min_tx_id=Min('id')
        )
        c_buys_sum = tx_info['c_buys'] or Decimal('0')
        c_sells_sum = tx_info['c_sells'] or Decimal('0')
        c_manual_sum = tx_info['c_manual'] or Decimal('0')
        c_gateway_sum = tx_info['c_gateway'] or Decimal('0')
        c_refund_sum = tx_info['c_refund'] or Decimal('0')
        tx_diffs = c_buys_sum - c_sells_sum + c_gateway_sum + c_manual_sum + c_refund_sum
        tx_min_id = tx_info['min_tx_id'] or Decimal('0')
        initial_balance = Decimal('0')
        initial_amount = Decimal('0')
        if tx_min_id:
            tx_min = Transaction.objects.get(id=tx_min_id)
            initial_balance = tx_min.balance
            initial_amount = tx_min.amount
        diff_balance = check_until_tx.balance - initial_balance + initial_amount
        net = c_deposit - withdraw_sum + tx_diffs
        diff = diff_balance - net
        diff_internal = deposit_crypto_sum_internal - withdraw_internal_to_sum
        final_diff = diff + last_wallet_transaction_diff + diff_internal
        cache.set(
            last_tx_id_cache_key,
            {'id': check_until_tx.id, 'created_at': check_until_tx.created_at, 'diff': final_diff},
            10 * 24 * 3600,
        )
        return final_diff

    def check_recent_withdraws(self):
        """Check recent withdraw to be correct."""
        print('Checking recent withdraw...')
        nw = now()
        recent_withdraw = WithdrawRequest.objects.filter(
            id__gt=self.last_checked_withdraw,
            created_at__gte=nw - datetime.timedelta(minutes=15),
            created_at__lte=nw - datetime.timedelta(minutes=1),
        ).select_related(
            'wallet__user', 'transaction'
        ).prefetch_related(
            'auto_withdraw'
        ).order_by('id')[:100]
        checks = 0
        for withdraw in recent_withdraw:
            checks += 1
            self.last_checked_withdraw = withdraw.id
            # Useful variables
            wallet = withdraw.wallet
            # General trade checks
            if settings.WITHDRAW_CREATE_TX_VERIFY:
                must_have_transaction = withdraw.status in WithdrawRequest.STATUSES_ACTIVE
            else:
                must_have_transaction = withdraw.status in WithdrawRequest.STATUSES_COMMITED or (
                    withdraw.status == WithdrawRequest.STATUS.processing and withdraw.auto_withdraw.status in AutomaticWithdraw.STATUSES_COMMITED
                )
            if must_have_transaction and not all([withdraw.transaction, withdraw.transaction.id]):
                self.notif(withdraw, 'Missing transaction')
                continue

            last_transaction = (
                Transaction.objects.filter(
                    created_at__gte=settings.LAST_RECENT_TRANSACTION_DATE,
                    wallet_id=wallet.id,
                )
                .order_by('-created_at', '-id')
                .first()
            )
            if last_transaction and last_transaction.balance:
                if last_transaction.balance < Decimal('0'):
                    self.notif(withdraw, 'Negative withdraw balance')
                    continue
                if self.recheck_diff:
                    diff = self.check_wallet_diff(wallet=wallet, check_until_tx=last_transaction)
                    if not money_is_zero(diff):
                        self.notif(withdraw, f'Diff non-zero: {diff}')
                        continue

        print(f'Checked {checks} withdraws.')

    def check_all(self):
        self.check_recent_withdraws()
