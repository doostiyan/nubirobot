import sys
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from exchange.accounts.models import User
from exchange.base.models import ADDRESS_TYPE
from exchange.wallet.estimator import PriceEstimator
from exchange.wallet.models import Wallet, ConfirmedWalletDeposit, WalletDepositAddress
from exchange.base.formatting import f_m


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('currency', type=int)

    @transaction.atomic
    def handle(self, *args, currency=None, **kwargs):
        print('Please enter deposits:')
        for l in sys.stdin:
            a = l.strip().split(',')
            if len(a) != 4:
                print('Invalid data:', a)
                break
            user = User.objects.get(username=a[0])
            tx_hash = a[1]
            amount = Decimal(a[2])
            dst_address = a[3]
            wallet = Wallet.get_user_wallet(user, currency)
            try:
                address = WalletDepositAddress.objects.get(
                    wallet=wallet,
                    currency=currency,
                    address=dst_address,
                    network='BSC',
                )
            except WalletDepositAddress.DoesNotExist:
                address = WalletDepositAddress.objects.create(
                    wallet=wallet,
                    currency=currency,
                    address=dst_address,
                    network='BSC',
                    type=ADDRESS_TYPE.standard,
                    is_disabled=True,
                )
            t = wallet.create_transaction(
                tp='deposit',
                amount=amount,
                description='ثبت سیستمی واریز رمزارز به مقدار {} برای تراکنش {}'.format(
                    f_m(amount, c=currency, show_c=True),
                    tx_hash,
                ),
            )
            t.commit()
            rial_value = PriceEstimator.get_rial_value_by_best_price(t.amount, wallet.currency, 'sell')
            deposit = ConfirmedWalletDeposit.objects.create(
                address=address,
                _wallet=wallet,
                tx_hash=tx_hash,
                transaction=t,
                confirmed=True,
                confirmations=1000,
                amount=t.amount,
                rial_value=rial_value
            )
            print(f'Created deposit#{deposit.id}: {amount} {wallet.get_currency_display()}')
        print('Done')
