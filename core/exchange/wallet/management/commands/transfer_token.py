import argparse
import json
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from tqdm import tqdm

from exchange.base.cache import CacheManager
from exchange.base.helpers import batcher
from exchange.base.models import CURRENCY_CODENAMES, Currencies
from exchange.base.serializers import normalize_number
from exchange.market.models import Order
from exchange.wallet.models import Wallet, WithdrawRequest


class Command(BaseCommand):
    help = 'Transfer whole token balances to another.'

    def add_arguments(self, parser):
        parser.add_argument('--src', type=str, help='Source token. Ex: agix', required=True)
        parser.add_argument('--dst', type=str, help='Destination token. Ex: fet', required=True)
        parser.add_argument(
            '--ratio',
            type=str,
            help='Source token * ratio => destination | Ex: 0.433350',
            required=True,
        )
        parser.add_argument('--yes', action='store_true', default=False)


    def handle(self, *args, src, dst, ratio, yes, **kwargs):
        try:
            ratio = Decimal(ratio)
        except InvalidOperation as e:
            raise argparse.ArgumentTypeError('Invalid ratio') from e

        logs = []
        src_currency = getattr(Currencies, src)
        dst_currency = getattr(Currencies, dst)

        if not yes:
            ok = input(
                f'Transferring {CURRENCY_CODENAMES[src_currency]} to {CURRENCY_CODENAMES[dst_currency]} with ratio {ratio}. Correct? [N/y] '
            )
            if ok.lower() != 'y':
                print('Abort.')
                return

        self.backup_data(src_currency, dst_currency)

        with transaction.atomic():
            print(f'Cancelling open orders of {CURRENCY_CODENAMES[src_currency]}...')
            src_orders = Order.objects.filter(status__in=Order.OPEN_STATUSES, src_currency=src_currency)
            for order in tqdm(src_orders):
                cancelled = order.do_cancel()
                msg = f'[{timezone.now()}] {order.id=} with {order.status=} ' + (
                    'could not be cancelled\n' if not cancelled else 'cancelled\n'
                )
                logs.append(msg)

            print(f'Cancelling open withdraw requests of {CURRENCY_CODENAMES[src_currency]}...')
            src_withdraws = WithdrawRequest.objects.filter(
                wallet__currency=src_currency,
                status__in=WithdrawRequest.STATUSES_CANCELABLE,
            )
            for withdraw_request in tqdm(src_withdraws):
                if rejected := withdraw_request.is_cancelable:
                    withdraw_request.system_reject_request()

                status = WithdrawRequest.status_display(withdraw_request.status)
                msg = f'[{timezone.now()}] {withdraw_request.id=} {status=} ' + (
                    'could not be rejected\n' if not rejected else 'rejected'
                )
                logs.append(msg)

        print(f'Pre-creating wallets for {CURRENCY_CODENAMES[dst_currency]}')
        src_wallets = Wallet.objects.filter(balance__gt=0, currency=src_currency)

        new_dst_wallets = [
            Wallet(currency=dst_currency, user_id=wallet.user_id, type=wallet.type) for wallet in src_wallets
        ]

        counter = 0
        for chunk in batcher(new_dst_wallets, batch_size=1000):
            chunk_wallets = Wallet.objects.bulk_create(chunk, ignore_conflicts=True)
            for w in chunk_wallets:
                CacheManager.invalidate_user_wallets(w.user_id)
            counter += len(chunk_wallets)
            print(f'{counter} Wallets created.')

        print(
            f'Transfer tokens from {CURRENCY_CODENAMES[src_currency]} '
            f'wallets to {CURRENCY_CODENAMES[dst_currency]} wallets...'
        )
        src_wallets = Wallet.objects.filter(balance__gt=0, currency=src_currency).select_related('user').order_by('id')
        dst_wallets = {}
        for chunk in batcher(src_wallets, batch_size=5000):
            criteria = Q()
            for wallet in chunk:
                criteria |= Q(
                    user_id=wallet.user_id,
                    type=wallet.type,
                )

            dst_wallets.update(
                {
                    (wallet.user_id, wallet.type): wallet
                    for wallet in (Wallet.objects.filter(criteria, currency=dst_currency).select_related('user'))
                }
            )

        for src_wallet in tqdm(src_wallets):
            with transaction.atomic():
                if src_wallet.blocked_balance > 0:
                    msg = f'[{timezone.now()}] | {src_wallet=} {src_wallet.id=} | has a blocked balance - skipping this wallet'
                    logs.append(msg)
                    continue
                if src_wallet.type not in [
                    Wallet.WALLET_TYPE.spot,
                    Wallet.WALLET_TYPE.credit,
                    Wallet.WALLET_TYPE.debit,
                ]:
                    msg = (
                        f'[{timezone.now()}] | {src_wallet=} {src_wallet.id=} | type of wallet should be either spot, '
                        f'credit, or debit; while it\'s "{Wallet.WALLET_TYPE[src_wallet.type]}" - skipping this wallet'
                    )
                    logs.append(msg)
                    continue

                if not (dst_wallet := dst_wallets.get((src_wallet.user_id, src_wallet.type))):
                    dst_wallet = Wallet.get_user_wallet(src_wallet.user_id, dst_currency)
                    dst_wallet.user = src_wallet.user

                amount = src_wallet.balance
                norm_amount = normalize_number(amount)
                dst_amount = amount * ratio
                norm_dst_amount = normalize_number(dst_amount)
                src_currency_code = CURRENCY_CODENAMES[src_wallet.currency]
                dst_currency_code = CURRENCY_CODENAMES[dst_wallet.currency]
                description = (
                    f'تبدیل {norm_amount} {src_currency_code} به {norm_dst_amount} {dst_currency_code} در فرآیند ادغام'
                )
                src_wallet.create_transaction(tp='manual', amount=-amount, description=description).commit()
                dst_wallet.create_transaction(tp='manual', amount=dst_amount, description=description).commit()

            msg = f'[{timezone.now()}] {dst_wallet=} {dst_wallet.id=} {dst_wallet.balance=} {src_wallet.id=}'
            logs.append(msg)

        self.persist_logs(logs)

    @staticmethod
    def persist_logs(logs):
        print('\nLogs file: transfer_token.log')
        with open('./transfer_token.log', 'w') as log:
            log.writelines(logs)

    @staticmethod
    def backup_data(src_currency, dst_currency):
        backup_filename = (
            f'backup_transfer_token_{src_currency}_{dst_currency}_{timezone.now().strftime("%Y%m%d%H%M%S")}.json'
        )
        print(f'Backing up data in {backup_filename}')
        backup = {
            'orders': list(Order.objects.filter(status__in=Order.OPEN_STATUSES, src_currency=src_currency).values()),
            'withdraw_requests': list(
                WithdrawRequest.objects.filter(
                    wallet__currency=src_currency,
                    status__in=WithdrawRequest.STATUSES_CANCELABLE,
                ).values(),
            ),
            'wallets': list(Wallet.objects.filter(balance__gt=0, currency=src_currency).values()),
        }

        with open(backup_filename, 'w') as backup_file:
            json.dump(backup, backup_file, default=str)
