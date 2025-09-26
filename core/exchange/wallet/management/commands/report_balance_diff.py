import math
import pprint
from collections import defaultdict
from decimal import Decimal
from typing import ClassVar

from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.db.models.functions import Coalesce
from tqdm import tqdm

from exchange.base.constants import ZERO
from exchange.base.models import Currencies
from exchange.base.serializers import serialize
from exchange.wallet.estimator import PriceEstimator
from exchange.wallet.models import Wallet


def cdd(tp):
    return lambda: defaultdict(tp)


class Command(BaseCommand):
    STATS: ClassVar[dict] = {
        'diff': defaultdict(cdd(cdd(cdd(int)))),
        'diff_price': defaultdict(cdd(cdd(int))),
        'negative_balance': defaultdict(cdd(cdd(int))),
        'negative_balance_price': defaultdict(cdd(int)),
    }

    def handle(self, **kwargs):
        wallets = Wallet.objects.values('id', 'currency', 'balance').annotate(
            real_balance=Coalesce(Sum('transactions__amount'), ZERO),
        )
        prominent_diff_wallet_ids = []
        for wallet in tqdm(wallets):
            diff = wallet['real_balance'] - wallet['balance']
            diff_price = PriceEstimator.get_rial_value_by_best_price(diff, wallet['currency'], 'buy', db_fallback=True)
            if diff:
                self.set_diff_stats(diff, wallet['currency'], diff_price)
                if diff_price > 50_000_0:
                    prominent_diff_wallet_ids.append(wallet['id'])
            if wallet['real_balance'] < 0:
                balance_price = PriceEstimator.get_rial_value_by_best_price(
                    wallet['real_balance'], wallet['currency'], 'buy'
                )
                self.set_wallet_stats(wallet['real_balance'], wallet['currency'], balance_price)
        print(self.style.SUCCESS('Report:'))
        pprint.pprint(serialize(self.STATS), width=120)
        if prominent_diff_wallet_ids:
            wallets = Wallet.objects.filter(id__in=prominent_diff_wallet_ids).values_list('id', 'user__email')
            print(self.style.WARNING('Prominent diff wallet IDs:'))
            pprint.pprint([('wallet ID', 'User email'), *wallets])

    def set_diff_stats(self, diff: Decimal, currency: int, diff_price: int):
        side = 'positive' if diff > 0 else 'negative'
        self.STATS['diff'][Currencies[currency]][side][f'1E{diff.adjusted()}:0>2']['count'] += 1
        self.STATS['diff'][Currencies[currency]][side][f'1E{diff.adjusted()}:0>2']['amount'] += diff
        if diff_price:
            self.STATS['diff_price'][side][f'1E{math.log10(abs(diff_price)):0>2.0f}']['count'] += 1
            self.STATS['diff_price'][side][f'1E{math.log10(abs(diff_price)):0>2.0f}']['amount'] += diff_price

    def set_wallet_stats(self, balance: Decimal, currency: int, balance_price: int):
        self.STATS['negative_balance'][Currencies[currency]][f'1E{balance.adjusted()}:0>2']['count'] += 1
        self.STATS['negative_balance'][Currencies[currency]][f'1E{balance.adjusted()}:0>2']['amount'] += balance
        if balance_price:
            self.STATS['negative_balance_price'][f'1E{math.log10(abs(balance_price)):0>2.0f}']['count'] += 1
            self.STATS['negative_balance_price'][f'1E{math.log10(abs(balance_price)):0>2.0f}'][
                'amount'
            ] += balance_price
